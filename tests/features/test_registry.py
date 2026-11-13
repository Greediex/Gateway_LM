"""FND-05: metadata/flags cannot grant runtime capabilities or health claims."""
import copy
import json
import tempfile
import unittest
import contextlib
import io
from pathlib import Path

from gateway_pilot.core import ROOT, PlanError
from gateway_pilot.command_catalog.loader import load_catalog, read_json, digest, canonical_bytes
from gateway_pilot.command_catalog.builder import build_registry
from gateway_pilot.adapters.bindings import TargetContext
from gateway_pilot.features.registry import FeatureRegistry, read_feature_manifests, read_feature_flags
from gateway_pilot.application.feature_availability import AvailabilityService, CapabilitySnapshot, FunctionCapability


class FeatureRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.policy = read_json(ROOT / "config/catalog_policy.example.json")
        self.artifact = build_registry(load_catalog(ROOT / "catalog"),
                                      read_json(ROOT / "config/catalog_selection.example.json"),
                                      self.policy, Path(self.tmp.name) / "registry.json")
        self.manifests = read_feature_manifests(ROOT / "examples/features.replay.json")
        self.flags = read_feature_flags(ROOT / "config/feature_flags.example.json")
        self.context = TargetContext("client", "synthetic-client", "a" * 64)
        self.permissions = frozenset({"network.read"})
        self.policy_context = "b" * 64

    def registry(self, manifests=None, flags=None):
        return FeatureRegistry(self.artifact, self.policy,
                               self.manifests if manifests is None else manifests,
                               self.flags if flags is None else flags)

    def snapshot(self, statuses=None, **changes):
        statuses = {} if statuses is None else statuses
        fields = dict(registry_digest=self.artifact["content_digest"], context=self.context,
                      permissions=self.permissions, policy_context_id=self.policy_context,
                      checked_at=90.0, expires_at=120.0,
                      functions=tuple(FunctionCapability(f["function_id"], f["version"], digest(f),
                                                         statuses.get(f["function_id"], "AVAILABLE"))
                                      for f in self.artifact["functions"]))
        fields.update(changes)
        return CapabilitySnapshot(**fields)

    def evaluate(self, snapshot=None, *, feature_id="network.client.connectivity", registry=None, **changes):
        service = AvailabilityService(self.registry() if registry is None else registry, clock=lambda: 100.0)
        fields = dict(context=self.context, permissions=self.permissions,
                      policy_context_id=self.policy_context, capabilities=snapshot)
        fields.update(changes)
        return service.evaluate(feature_id, **fields)

    def rebuild_catalog(self, catalog, selection=None):
        source = Path(self.tmp.name) / "synthetic-source"
        for group, key in (("functions", "function_id"), ("ports", "port_id"), ("skills", "skill_id")):
            for row in catalog[group]:
                folder = source / group / row["domain"] if group == "functions" else source / group
                folder.mkdir(parents=True, exist_ok=True)
                (folder / (row[key]+".json")).write_bytes(canonical_bytes(row))
        selected = read_json(ROOT / "config/catalog_selection.example.json") if selection is None else selection
        self.artifact = build_registry(load_catalog(source), selected, self.policy, Path(self.tmp.name) / "synthetic.json")

    def test_four_states_and_missing_required_vs_optional(self):
        ready = self.evaluate(self.snapshot())
        self.assertEqual(ready["status"], "READY")
        self.assertFalse(ready["authorizes_execution"])
        self.assertFalse(ready["health_evaluated"])
        degraded = self.evaluate(self.snapshot({"wifi.station": "UNSUPPORTED"}))
        self.assertEqual(degraded["status"], "DEGRADED")
        self.assertEqual(self.evaluate(self.snapshot({"client.ipv4": "UNSUPPORTED"}))["status"], "UNAVAILABLE")
        flags = {**self.flags, "network.client.connectivity": False}
        self.assertEqual(self.evaluate(self.snapshot(), registry=self.registry(flags=flags))["status"], "DISABLED")

    def test_absent_runtime_and_conformance_report_cannot_mark_ready(self):
        self.assertEqual(self.evaluate()["reason"], "RUNTIME_NOT_CONNECTED")
        conformance = {"status": "CONFORMANT", "execution_enabled": False, "evidence_admitted": False}
        result = self.evaluate(conformance)
        self.assertEqual(result["status"], "UNAVAILABLE")
        self.assertEqual(result["reason"], "INVALID_CAPABILITY_SNAPSHOT")

    def test_permissions_scope_environment_registry_and_policy_are_bound(self):
        variants = (
            (self.snapshot(), {"permissions": frozenset()}),
            (self.snapshot(), {"context": TargetContext("gateway", "synthetic-client", "a" * 64)}),
            (self.snapshot(), {"context": TargetContext("client", "other-client", "a" * 64)}),
            (self.snapshot(), {"context": TargetContext("client", "synthetic-client", "c" * 64)}),
            (self.snapshot(registry_digest="0" * 64), {}),
            (self.snapshot(policy_context_id="c" * 64), {}),
            (self.snapshot(permissions=frozenset({"network.read", "system.read"})), {}),
        )
        for snapshot, overrides in variants:
            with self.subTest(overrides=overrides):
                self.assertEqual(self.evaluate(snapshot, **overrides)["status"], "UNAVAILABLE")

    def test_expired_future_wrong_function_version_or_digest_fail_closed(self):
        variants = [self.snapshot(checked_at=10, expires_at=20), self.snapshot(checked_at=101, expires_at=120)]
        f = self.artifact["functions"][0]
        variants.extend([
            self.snapshot(functions=(FunctionCapability(f["function_id"], "99.0.0", digest(f), "AVAILABLE"),)),
            self.snapshot(functions=(FunctionCapability(f["function_id"], f["version"], "0" * 64, "AVAILABLE"),)),
            self.snapshot(functions=(FunctionCapability("unknown.function", "1.0.0", "0" * 64, "AVAILABLE"),)),
        ])
        for snapshot in variants:
            self.assertEqual(self.evaluate(snapshot)["status"], "UNAVAILABLE")

    def test_indirect_dependencies_must_be_available(self):
        result = self.evaluate(self.snapshot({"clients.resolve": "TEMPORARILY_UNAVAILABLE"}))
        self.assertEqual(result["status"], "UNAVAILABLE")
        ipv4 = next(p for p in result["required"] if p["port_id"] == "client.ipv4")
        self.assertEqual(ipv4["reason"], "DEPENDENCY_UNAVAILABLE")

    def test_flags_default_disabled_and_reject_unknown_or_non_boolean(self):
        self.assertEqual(self.evaluate(self.snapshot(), registry=self.registry(flags={}))["status"], "DISABLED")
        for flags in ({"unknown.feature": True}, {"network.client.connectivity": 1}):
            with self.assertRaises(PlanError):
                self.registry(flags=flags)

    def test_manifest_unknown_fields_duplicate_id_or_bad_references_rejected(self):
        for changes in ({"permission": "network.write"}, {"capabilities": ["wifi.station"]},
                        {"backend": "linux.local"}, {"enabled": True},
                        {"required_ports": {"missing.port": "1.0.0"}},
                        {"required_ports": {"client.ipv4": "99.0.0"}}, {"required_ports": {}},
                        {"scope": "gateway"}):
            rows = copy.deepcopy(self.manifests)
            rows[0].update(changes)
            with self.subTest(changes=changes), self.assertRaises(PlanError):
                self.registry(manifests=rows)
        with self.assertRaises(PlanError):
            self.registry(manifests=self.manifests + [copy.deepcopy(self.manifests[0])])

    def test_registry_and_flags_are_snapshots_and_do_not_mutate_catalog(self):
        before = copy.deepcopy(self.artifact)
        registry = self.registry()
        self.flags["network.client.connectivity"] = False
        self.manifests[0]["required_ports"] = {}
        exported = registry.describe()
        exported[0]["name"] = "mutated"
        self.assertEqual(self.evaluate(self.snapshot(), registry=registry)["status"], "READY")
        self.assertEqual(self.artifact, before)
        self.assertNotEqual(registry.describe()[0]["name"], "mutated")

    def test_file_readers_reject_embedded_status_and_duplicate_json_keys(self):
        path = Path(self.tmp.name) / "features.json"
        path.write_text(json.dumps({"schema_version": "0.2.0", "features": self.manifests, "status": "READY"}))
        with self.assertRaises(PlanError):
            read_feature_manifests(path)
        path.write_text('{"schema_version":"0.2.0","enabled":{},"enabled":{}}')
        with self.assertRaises(PlanError):
            read_feature_flags(path)

    def test_snapshot_types_and_bounds(self):
        for changes in ({"checked_at": float("nan")}, {"expires_at": 200}, {"functions": []},
                        {"functions": self.snapshot().functions * 2}):
            with self.subTest(changes=changes), self.assertRaises(PlanError):
                self.snapshot(**changes)
        f = self.artifact["functions"][0]
        with self.assertRaises(PlanError):
            FunctionCapability(f["function_id"], f["version"], digest(f), "CONFORMANT")

    def test_alternative_producer_can_satisfy_required_port(self):
        # Independent synthetic fixture; checked-in catalog and v0.1 stay intact.
        catalog = load_catalog(ROOT / "catalog")
        backup = copy.deepcopy(next(f for f in catalog["functions"] if f["function_id"] == "client.ipv4"))
        backup["function_id"] = "client.ipv4.backup"
        catalog["functions"].append(backup)
        skill = next(s for s in catalog["skills"] if "client.ipv4" in s["function_refs"])
        skill["function_refs"]["client.ipv4.backup"] = "4.0.0"
        selected = read_json(ROOT / "config/catalog_selection.example.json")
        selected["functions"]["client.ipv4.backup"] = "4.0.0"
        self.rebuild_catalog(catalog, selected)
        result = self.evaluate(self.snapshot({"client.ipv4": "UNSUPPORTED"}))
        self.assertEqual(result["status"], "READY")
        ipv4 = next(p for p in result["required"] if p["port_id"] == "client.ipv4")
        self.assertTrue(ipv4["available"])
        self.assertEqual(ipv4["function_reasons"]["client.ipv4"], "UNSUPPORTED")
        self.assertEqual(ipv4["function_reasons"]["client.ipv4.backup"], "AVAILABLE")

    def test_cli_preview_does_not_connect_or_self_assert_capabilities(self):
        from scripts.features import main
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(["--registry", str(Path(self.tmp.name) / "registry.json")]), 0)
        result = json.loads(output.getvalue())
        self.assertFalse(result["runtime_connected"])
        self.assertTrue(all(f["reason"] == "RUNTIME_NOT_CONNECTED" for f in result["features"]))

    def test_laptop_manifest_matches_linux_port_versions(self):
        policy = read_json(ROOT / "config/catalog_policy.laptop.example.json")
        artifact = build_registry(load_catalog(ROOT / "examples/catalog_laptop"),
                                  read_json(ROOT / "config/catalog_selection.laptop.example.json"), policy,
                                  Path(self.tmp.name) / "laptop.json")
        registry = FeatureRegistry(artifact, policy, read_feature_manifests(ROOT / "examples/features.laptop.json"),
                                   read_feature_flags(ROOT / "config/feature_flags.laptop.example.json"))
        result = self.evaluate(registry=registry)
        self.assertEqual(result["reason"], "RUNTIME_NOT_CONNECTED")
        with self.assertRaises(PlanError):
            FeatureRegistry(artifact, policy, self.manifests, self.flags)

    def test_schema_self_check_overlap_and_unsupported_flags_fields(self):
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(read_json(ROOT / "docs/contracts/catalog-v02/feature.schema.json"))
        rows = copy.deepcopy(self.manifests)
        rows[0]["optional_ports"]["client.identity"] = "2.0.0"
        with self.assertRaises(PlanError):
            self.registry(manifests=rows)
        path = Path(self.tmp.name) / "flags.json"
        path.write_text(json.dumps({"schema_version": "0.2.0", "enabled": self.flags, "capabilities": ["client.ipv4"]}))
        with self.assertRaises(PlanError):
            read_feature_flags(path)

    def test_order_dependency_and_indirect_permissions_are_not_bypassed(self):
        for gate in ("order", "permission"):
            with self.subTest(gate=gate):
                catalog = load_catalog(ROOT / "catalog")
                if gate == "order":
                    f = next(f for f in catalog["functions"] if f["function_id"] == "client.ipv4")
                    f["order_after"] = ["wifi.station"]
                else:
                    f = next(f for f in catalog["functions"] if f["function_id"] == "clients.resolve")
                    f["permission"] = "system.read"
                self.rebuild_catalog(catalog)
                result = self.evaluate(self.snapshot({"wifi.station": "UNSUPPORTED"}))
                self.assertEqual(result["status"], "UNAVAILABLE")
                ipv4 = next(p for p in result["required"] if p["port_id"] == "client.ipv4")
                self.assertEqual(ipv4["reason"], "DEPENDENCY_UNAVAILABLE")

    def test_one_service_does_not_cache_availability_between_targets(self):
        service = AvailabilityService(self.registry(), clock=lambda: 100.0)
        second = TargetContext("client", "second-synthetic-client", "c" * 64)
        args = {"permissions": self.permissions, "policy_context_id": self.policy_context}
        self.assertEqual(service.evaluate("network.client.connectivity", context=self.context,
                                         capabilities=self.snapshot(), **args)["status"], "READY")
        self.assertEqual(service.evaluate("network.client.connectivity", context=second,
                                         capabilities=self.snapshot(), **args)["status"], "UNAVAILABLE")
        second_frame = self.snapshot({"client.ipv4": "UNSUPPORTED"}, context=second)
        self.assertEqual(service.evaluate("network.client.connectivity", context=second,
                                         capabilities=second_frame, **args)["status"], "UNAVAILABLE")
        self.assertEqual(service.evaluate("network.client.connectivity", context=self.context,
                                         capabilities=self.snapshot(), **args)["status"], "READY")


if __name__ == "__main__":
    unittest.main()
