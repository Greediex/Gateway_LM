"""FND-03: catalog trust boundary, reproducibility and metadata-only artifacts."""
import copy
import json
import tempfile
import unittest
import contextlib
import io
import sys
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.core import ROOT, PlanError
from gateway_pilot.command_catalog.loader import load_catalog, read_json, canonical_bytes
from gateway_pilot.command_catalog.validator import validate_catalog
from gateway_pilot.command_catalog.builder import build_registry, read_registry, report_registry
from gateway_pilot.command_catalog.indexes import discover, dependency_closure


class CatalogBuilderTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_catalog(ROOT / "catalog")
        self.policy = read_json(ROOT / "config/catalog_policy.example.json")
        self.selection = read_json(ROOT / "config/catalog_selection.example.json")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = Path(self.tmp.name) / "registry.json"

    def build(self, catalog=None, selection=None):
        return build_registry(self.catalog if catalog is None else catalog,
                              self.selection if selection is None else selection,
                              self.policy, self.output)

    def test_seed_build_read_report_and_cross_domain_dependency_closure(self):
        artifact = self.build()
        self.assertEqual(read_registry(self.output, self.policy), artifact)
        report = report_registry(artifact)
        self.assertEqual(report["selected_function_count"], 3)
        self.assertEqual(report["target_verified_executable_count"], 0)
        self.assertFalse(artifact["execution_enabled"])
        index = artifact["indexes"]
        self.assertEqual(discover(index, domain="wifi"), ["wifi.station"])
        self.assertEqual(dependency_closure(index, ["wifi.station"]), ["clients.resolve", "wifi.station"])

    def test_build_is_byte_identical_and_does_not_mutate_sources(self):
        before = copy.deepcopy(self.catalog)
        first = self.build()
        raw = self.output.read_bytes()
        for group in ("functions", "ports", "skills"):
            self.catalog[group].reverse()
        second = self.build()
        self.assertEqual(first, second)
        self.assertEqual(raw, self.output.read_bytes())
        for group in ("functions", "ports", "skills"):
            self.catalog[group].reverse()
        self.assertEqual(self.catalog, before)
        self.assertNotIn(str(ROOT), raw.decode())

    def test_strict_json_rejects_duplicate_keys_nonfinite_bad_unicode_and_size(self):
        path = Path(self.tmp.name) / "bad.json"
        for raw in (b'{"a":1,"a":2}', b'{"nested":{"a":1,"a":2}}',
                    b'{"a":NaN}', b'{"a":1e999}', b'\xff', b'[' * 2000):
            with self.subTest(raw=raw[:40]):
                path.write_bytes(raw)
                with self.assertRaises(PlanError):
                    read_json(path)
        path.write_bytes(b' ' * 65537)
        with self.assertRaises(PlanError):
            read_json(path)

    def test_source_loader_rejects_symlinks_unknown_layout_and_wrong_domain(self):
        root = Path(self.tmp.name) / "catalog"
        root.mkdir()
        (root / "ports").symlink_to(ROOT / "catalog/ports", target_is_directory=True)
        with self.assertRaises(PlanError):
            load_catalog(root)
        (root / "ports").unlink()
        (root / "unknown.json").write_text('{}')
        with self.assertRaises(PlanError):
            load_catalog(root)
        (root / "unknown.json").unlink()
        path = root / "functions/wrong/wifi.station.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(next(f for f in self.catalog["functions"] if f["function_id"] == "wifi.station")))
        with self.assertRaises(PlanError):
            load_catalog(root)

    def test_duplicate_identity_and_unknown_exact_port_or_skill_are_rejected(self):
        self.catalog["functions"].append(copy.deepcopy(self.catalog["functions"][0]))
        with self.assertRaises(PlanError):
            validate_catalog(self.catalog, self.policy)
        self.catalog["functions"].pop()
        f = next(f for f in self.catalog["functions"] if f["inputs"])
        f["inputs"]["client.identity"] = "99.0.0"
        with self.assertRaises(PlanError):
            validate_catalog(self.catalog, self.policy)
        f["inputs"]["client.identity"] = "2.0.0"
        f["skill_refs"][0]["version"] = "99.0.0"
        with self.assertRaises(PlanError):
            validate_catalog(self.catalog, self.policy)

    def test_scope_missing_field_argument_type_and_numeric_predicate_checks(self):
        for change in ("scope", "field", "type", "predicate", "format", "optional", "input_scope"):
            with self.subTest(change=change):
                source = copy.deepcopy(self.catalog)
                f = next(f for f in source["functions"] if f["function_id"] == "wifi.station")
                if change == "scope":
                    f["scope"] = "gateway"
                elif change == "field":
                    f["argument_sources"]["client_id"][1] = "missing"
                elif change == "type":
                    f["arguments_schema"]["properties"]["client_id"] = {"type": "number"}
                elif change == "predicate":
                    f["preconditions"] = [{"port": "client.identity", "field": "client_id", "op": "gt", "value": 1}]
                elif change == "format":
                    f["arguments_schema"]["properties"]["client_id"]["format"] = "ipv4"
                elif change == "input_scope":
                    f["scope"] = "gateway"
                    next(p for p in source["ports"] if p["port_id"] == "wifi.station")["scope"] = "gateway"
                else:
                    next(p for p in source["ports"] if p["port_id"] == "client.identity")["schema"]["required"] = []
                with self.assertRaises(PlanError):
                    validate_catalog(source, self.policy)

    def test_skill_membership_and_produced_port_consistency(self):
        skill = next(s for s in self.catalog["skills"] if "wifi.station" in s["function_refs"])
        skill["function_refs"]["wifi.station"] = "99.0.0"
        with self.assertRaises(PlanError):
            validate_catalog(self.catalog, self.policy)
        skill["function_refs"]["wifi.station"] = "4.0.0"
        skill["produces"]["client.identity"] = "2.0.0"
        with self.assertRaises(PlanError):
            validate_catalog(self.catalog, self.policy)

    def test_unknown_probe_and_write_contract_fail_closed(self):
        f = self.catalog["functions"][0]
        f["capability_probe"] = "unknown.probe"
        with self.assertRaises(PlanError):
            validate_catalog(self.catalog, self.policy)
        f["capability_probe"] = self.policy["allowed_probe_ids"][0]
        f.update(risk="WRITE", permission="network.write")
        with self.assertRaises(PlanError):
            validate_catalog(self.catalog, self.policy)

    def test_order_cycle_and_missing_producer_are_rejected(self):
        root = next(f for f in self.catalog["functions"] if f["function_id"] == "clients.resolve")
        root["order_after"] = ["wifi.station"]
        with self.assertRaisesRegex(PlanError, "dependency"):
            validate_catalog(self.catalog, self.policy)
        root["order_after"] = []
        root["inputs"] = {"client.identity": "2.0.0"}
        with self.assertRaisesRegex(PlanError, "dependency"):
            validate_catalog(self.catalog, self.policy)

    def test_selection_rejects_wrong_versions_missing_dependencies_and_retired(self):
        for change in ("version", "port", "member", "retired"):
            with self.subTest(change=change):
                selection = copy.deepcopy(self.selection)
                catalog = copy.deepcopy(self.catalog)
                if change == "version":
                    selection["functions"]["wifi.station"] = "99.0.0"
                elif change == "port":
                    del selection["ports"]["client.identity"]
                elif change == "member":
                    del selection["functions"]["client.ipv4"]
                else:
                    catalog["functions"][0]["lifecycle"] = "RETIRED"
                with self.assertRaises(PlanError):
                    self.build(catalog, selection)
                self.assertFalse(self.output.exists())

    def test_validation_and_replace_failure_preserve_existing_artifact(self):
        self.build()
        original = self.output.read_bytes()
        self.selection["functions"]["wifi.station"] = "99.0.0"
        with self.assertRaises(PlanError):
            self.build()
        self.assertEqual(self.output.read_bytes(), original)
        self.selection["functions"]["wifi.station"] = "4.0.0"
        with patch("gateway_pilot.command_catalog.builder.os.replace", side_effect=OSError("test failure")):
            with self.assertRaises(PlanError):
                self.build()
        self.assertEqual(self.output.read_bytes(), original)
        self.assertEqual(list(self.output.parent.iterdir()), [self.output])

    def test_artifact_rejects_tampering_even_when_digest_is_recomputed(self):
        from gateway_pilot.command_catalog.loader import digest
        artifact = self.build()
        for field in ("digest", "indexes", "execution", "policy", "schema"):
            with self.subTest(field=field):
                broken = copy.deepcopy(artifact)
                if field == "digest":
                    broken["functions"][0]["description"] = "modified"
                elif field == "indexes":
                    broken["indexes"]["by_domain"] = {}
                elif field == "execution":
                    broken["execution_enabled"] = True
                elif field == "policy":
                    broken["manifest"]["policy_digest"] = "0" * 64
                else:
                    broken["manifest"]["contract_schema_digest"] = "0" * 64
                if field != "digest":
                    broken["content_digest"] = digest({k: v for k, v in broken.items() if k != "content_digest"})
                self.output.write_bytes(canonical_bytes(broken))
                with self.assertRaises(PlanError):
                    read_registry(self.output, self.policy)

    def test_alternative_producer_breaks_a_union_graph_cycle(self):
        # identity root is still available, so a later IPv4-based refresh of
        # the same port does not make the metadata dependency set impossible.
        root = next(f for f in self.catalog["functions"] if f["function_id"] == "clients.resolve")
        refresh = copy.deepcopy(root)
        refresh.update(function_id="clients.refresh", inputs={"client.ipv4": "2.0.0"},
                       order_after=[])
        self.catalog["functions"].append(refresh)
        skill = next(s for s in self.catalog["skills"] if s["skill_id"] == "client.identity.inspect")
        skill["function_refs"]["clients.refresh"] = "4.0.0"
        skill["requires"] = {"client.ipv4": "2.0.0"}
        validate_catalog(self.catalog, self.policy)
        from gateway_pilot.command_catalog.indexes import build_indexes
        index = build_indexes(self.catalog["functions"])
        self.assertEqual(dependency_closure(index, ["clients.refresh"]),
                         ["clients.resolve", "client.ipv4", "clients.refresh"])

    def test_multiple_versions_require_exact_selection_and_immutable_source_snapshot(self):
        root = next(f for f in self.catalog["functions"] if f["function_id"] == "clients.resolve")
        newer = copy.deepcopy(root)
        newer["version"] = "5.0.0"
        newer["skill_refs"][0]["version"] = "2.0.0"
        skill = copy.deepcopy(next(s for s in self.catalog["skills"] if s["skill_id"] == "client.identity.inspect"))
        skill.update(version="2.0.0", function_refs={"clients.resolve": "5.0.0"})
        self.catalog["functions"].append(newer)
        self.catalog["skills"].append(skill)
        validate_catalog(self.catalog, self.policy)
        # Materialize a distinct trusted source snapshot, using versioned names.
        source = Path(self.tmp.name) / "source"
        for group, key in (("functions", "function_id"), ("ports", "port_id"), ("skills", "skill_id")):
            for row in self.catalog[group]:
                parent = source / group / row["domain"] if group == "functions" else source / group
                parent.mkdir(parents=True, exist_ok=True)
                (parent / f"{row[key]}@{row['version']}.json").write_bytes(canonical_bytes(row))
        loaded = load_catalog(source)
        self.selection["functions"]["clients.resolve"] = "5.0.0"
        artifact = self.build(loaded)
        self.assertEqual(len(artifact["functions"]), 3)
        self.assertEqual(artifact["selection"]["functions"]["clients.resolve"], "5.0.0")
        self.assertEqual(report_registry(artifact)["declared_function_version_count"], 4)
        loaded["functions"][0]["description"] = "changed in memory"
        with self.assertRaisesRegex(PlanError, "source_records_changed"):
            self.build(loaded)

    def test_read_rejects_rehashed_wrong_source_counts_and_policy_shape(self):
        from gateway_pilot.command_catalog.loader import digest
        artifact = self.build()
        artifact["manifest"]["catalog_counts"]["functions"] = 1
        artifact["content_digest"] = digest({k: v for k, v in artifact.items() if k != "content_digest"})
        self.output.write_bytes(canonical_bytes(artifact))
        with self.assertRaises(PlanError):
            read_registry(self.output, self.policy)
        for policy in ({"schema_version": "0.2.0", "allowed_probe_ids": ["bad"]},
                       {**self.policy, "execute": True},
                       {**self.policy, "allowed_probe_ids": [self.policy["allowed_probe_ids"][0]] * 2}):
            with self.assertRaises(PlanError):
                validate_catalog(self.catalog, policy)

    def test_source_and_baseline_output_are_protected(self):
        for path in (ROOT / "data/registry_v01.json", ROOT / "benchmarks/no-output.json",
                     ROOT / "catalog/registry.json"):
            with self.subTest(path=path), self.assertRaises(PlanError):
                build_registry(self.catalog, self.selection, self.policy, path)

    def test_cli_validate_build_report_and_failure_status(self):
        from scripts.catalog import main
        commands = (["validate", "--source", str(ROOT / "catalog")],
                    ["build", "--source", str(ROOT / "catalog"), "--output", str(self.output)],
                    ["report", "--registry", str(self.output)])
        for command in commands:
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(command), 0)
            self.assertFalse(json.loads(out.getvalue())["execution_enabled"])
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(main(["report", "--registry", str(self.output.parent / "missing.json")]), 2)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(json.loads(err.getvalue())["validation"], "FAIL")

    def test_discovery_bounds_and_unknown_closure_goal(self):
        index = self.build()["indexes"]
        self.assertEqual(discover(index, domain="not-known"), [])
        for limit in (0, 1001, True):
            with self.assertRaises(PlanError):
                discover(index, limit=limit)
        with self.assertRaises(PlanError):
            dependency_closure(index, ["missing.function"])

    @unittest.skipIf(sys.platform == "win32", "RSS benchmark requires Unix resource")
    def test_synthetic_benchmark_generator_and_measurements_are_metadata_only(self):
        from scripts.analysis.benchmark_catalog import measure
        result = measure(3)
        self.assertEqual(result["function_count"], 3)
        self.assertEqual(result["source_documents"], 9)
        self.assertTrue(result["dependency_closure_correct"])
        self.assertFalse(result["runtime_compile_measured"])
        self.assertEqual(result["target_verified_executable_count"], 0)
        self.assertGreater(result["artifact_bytes"], 0)


if __name__ == "__main__":
    unittest.main()
