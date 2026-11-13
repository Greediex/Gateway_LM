"""FND-04 does not turn conformance samples into runtime evidence."""
import copy
import tempfile
import unittest
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gateway_pilot.core import ROOT, PlanError
from gateway_pilot.command_catalog.builder import build_registry
from gateway_pilot.command_catalog.loader import load_catalog, read_json
from gateway_pilot.adapters.bindings import BindingSelection, TargetContext, binding_digest, declare_binding, read_binding_declarations
from gateway_pilot.adapters.read_backends import ReplayReadBackend
from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.adapters.conformance import ConformanceHarness


VALUES = {
    "clients.resolve": {"client.identity": {"client_id": "synthetic-client"}},
    "client.ipv4": {"client.ipv4": {"configured": True, "address": "192.0.2.10"}},
    "wifi.station": {"wifi.station": {"associated": True, "rssi_dbm": -60}},
}


class FaultBackend(ReplayReadBackend):
    def __init__(self):
        super().__init__(VALUES, client_id="synthetic-client")
        self.probes = self.calls = 0
        self.supported = True
        self.mutate = lambda result: result

    def supports(self, fid, context):
        self.probes += 1
        return self.supported and super().supports(fid, context)

    def sample(self, function, arguments, context):
        self.calls += 1
        result = super().sample(function, arguments, context)
        return self.mutate(result)


class BindingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.policy = read_json(ROOT / "config/catalog_policy.example.json")
        self.artifact = build_registry(load_catalog(ROOT / "catalog"),
                                       read_json(ROOT / "config/catalog_selection.example.json"),
                                       self.policy, Path(self.temp.name) / "registry.json")
        self.backend = FaultBackend()
        self.context = TargetContext("client", "synthetic-client", self.backend.environment_id)
        self.rows = [declare_binding(self.artifact, fid, "test." + fid, "replay.seed", self.backend, self.context)
                     for fid in VALUES]
        self.permissions = frozenset({"network.read"})

    def select(self, rows=None, pins=None, backend=None, artifact=None):
        rows = self.rows if rows is None else rows
        return BindingSelection(self.artifact if artifact is None else artifact, self.policy, rows,
                                approved_digests=frozenset(binding_digest(r) for r in rows) if pins is None else pins,
                                backends={"replay.seed": self.backend if backend is None else backend}, context=self.context)

    def check(self, **kwargs):
        harness = ConformanceHarness(self.select())
        return harness.check("test.client.ipv4", {"client_id": "synthetic-client"},
                             kwargs.get("context", self.context), kwargs.get("permissions", self.permissions))

    def test_selection_is_explicit_unique_and_has_no_backend_io(self):
        selection = self.select()
        self.assertEqual(selection.assignments(), {fid: "replay.seed" for fid in VALUES})
        self.assertEqual((self.backend.probes, self.backend.calls), (0, 0))
        self.rows[0]["backend_id"] = "modified.after.selection"
        self.assertEqual(selection.assignments()["clients.resolve"], "replay.seed")
        result = ConformanceHarness(selection).check("test.clients.resolve", {}, self.context, self.permissions)
        self.assertEqual(result["status"], "CONFORMANT")
        self.assertFalse(result["execution_enabled"])
        self.assertFalse(result["evidence_admitted"])

    def test_missing_approval_or_self_approval_field_does_not_probe(self):
        with self.assertRaisesRegex(PlanError, "binding_not_approved"):
            self.select(pins=frozenset())
        rows = copy.deepcopy(self.rows)
        rows[0]["approved"] = True
        with self.assertRaises(PlanError):
            self.select(rows)
        self.assertEqual((self.backend.probes, self.backend.calls), (0, 0))

    def test_declaration_file_is_data_only_and_cannot_carry_approval(self):
        path = Path(self.temp.name) / "bindings.json"
        payload = {"schema_version": "0.2.0", "bindings": self.rows}
        path.write_text(json.dumps(payload))
        self.assertEqual(read_binding_declarations(path), self.rows)
        payload["approved_digests"] = [binding_digest(self.rows[0])]
        path.write_text(json.dumps(payload))
        with self.assertRaises(PlanError):
            read_binding_declarations(path)
        path.write_text('{"schema_version":"0.2.0","bindings":[],"bindings":[]}')
        with self.assertRaises(PlanError):
            read_binding_declarations(path)

    def test_checked_in_replay_declarations_match_current_artifact(self):
        from jsonschema import Draft202012Validator
        Draft202012Validator.check_schema(read_json(ROOT / "docs/contracts/catalog-v02/binding.schema.json"))
        rows = read_binding_declarations(ROOT / "examples/binding_selection.replay.json")
        selection = self.select(rows)
        harness = ConformanceHarness(selection)
        for row in rows:
            arguments = {} if row["function_id"] == "clients.resolve" else {"client_id": self.context.target_id}
            self.assertEqual(harness.check(row["binding_id"], arguments, self.context, self.permissions)["status"], "CONFORMANT")

    def test_wrong_registry_version_digest_target_environment_or_backend_rejected(self):
        changes = {"registry_digest": "0" * 64, "function_version": "99.0.0", "function_digest": "0" * 64,
                   "target_id": "other-client", "environment_id": "0" * 64, "scope": "gateway",
                   "backend_id": "missing.backend", "backend_revision": "99.0.0"}
        for field, value in changes.items():
            with self.subTest(field=field):
                rows = copy.deepcopy(self.rows)
                rows[0][field] = value
                with self.assertRaises(PlanError):
                    self.select(rows)
        self.assertEqual((self.backend.probes, self.backend.calls), (0, 0))

    def test_duplicate_ownership_and_undeclared_write_are_rejected(self):
        rows = copy.deepcopy(self.rows)
        second = copy.deepcopy(rows[0]); second["binding_id"] = "other.backend"
        rows.append(second)
        with self.assertRaisesRegex(PlanError, "duplicate_binding_assignment"):
            self.select(rows)
        rows = copy.deepcopy(self.rows)
        rows[0]["command"] = "arbitrary command"
        with self.assertRaises(PlanError):
            self.select(rows)
        rows[0].pop("command"); rows[0]["function_id"] = "write.unknown"
        with self.assertRaises(PlanError):
            self.select(rows)

    def test_permission_target_environment_and_argument_gates_precede_io(self):
        for context, permissions in ((self.context, frozenset()),
                                     (TargetContext("client", "other", self.context.environment_id), self.permissions),
                                     (TargetContext("client", "synthetic-client", "0" * 64), self.permissions)):
            report = self.check(context=context, permissions=permissions)
            self.assertEqual(report["status"], "REJECTED")
        harness = ConformanceHarness(self.select())
        for arguments in ({}, {"client_id": "other"}, {"client_id": "synthetic-client", "cmd": "id"}):
            self.assertEqual(harness.check("test.client.ipv4", arguments, self.context, self.permissions)["status"], "REJECTED")
        self.assertEqual((self.backend.probes, self.backend.calls), (0, 0))

    def test_reprobe_and_no_fallback_on_support_loss_or_backend_failure(self):
        harness = ConformanceHarness(self.select())
        self.assertEqual(harness.check("test.client.ipv4", {"client_id": "synthetic-client"}, self.context, self.permissions)["status"], "CONFORMANT")
        calls = self.backend.calls
        self.backend.supported = False
        report = harness.check("test.client.ipv4", {"client_id": "synthetic-client"}, self.context, self.permissions)
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(self.backend.calls, calls)
        self.backend.supported = True
        def broken(_):
            raise KeyError("sensitive payload should not leak")
        self.backend.mutate = broken
        report = harness.check("test.client.ipv4", {"client_id": "synthetic-client"}, self.context, self.permissions)
        self.assertEqual(report["status"], "REJECTED")
        self.assertNotIn("sensitive", str(report))

    def test_bad_output_set_schema_target_source_time_and_error_result(self):
        def alter(field, value):
            def mutate(result):
                row = copy.deepcopy(result.observations[0]); row[field] = value
                return ToolResult(observations=(row,))
            return mutate
        mutations = [alter("target", "other-client"), alter("environment_id", "0" * 64),
                     alter("scope", "gateway"), alter("source", "linux_client/fake"),
                     alter("port", "foreign.port"), alter("function_version", "99.0.0"),
                     alter("value", {"configured": "yes", "address": "x"}),
                     alter("value", 42), alter("value", None), alter("value", []),
                     alter("observed_at", (datetime.now(UTC)-timedelta(minutes=2)).isoformat()),
                     alter("observed_at", (datetime.now(UTC)+timedelta(minutes=2)).isoformat()),
                     alter("age_s", float("nan")), alter("age_s", 10 ** 400), alter("ttl_s", 9999),
                     lambda r: ToolResult(observations=r.observations * 2),
                     lambda r: ToolResult(is_error=True, error_code="test_error"), lambda r: {}]
        for mutation in mutations:
            self.backend.mutate = mutation
            with self.subTest(mutation=mutation):
                report = self.check()
                self.assertEqual(report["status"], "REJECTED")
                self.assertFalse(report["execution_enabled"])
                self.assertFalse(report["evidence_admitted"])

    def test_elapsed_timeout_and_revision_change_fail_closed(self):
        harness = ConformanceHarness(self.select(), clock=iter([0, 3]).__next__)
        report = harness.check("test.client.ipv4", {"client_id": "synthetic-client"}, self.context, self.permissions)
        self.assertEqual(report["status"], "REJECTED")
        self.assertIn("timeout", report["reason"])
        selection = self.select()
        self.backend.revision = "2.0.0"
        self.assertEqual(ConformanceHarness(selection).check("test.client.ipv4", {"client_id": "synthetic-client"}, self.context, self.permissions)["status"], "REJECTED")

    def test_backend_planerror_is_sanitized_and_unknown_protocol_not_trusted(self):
        def broken(_):
            raise PlanError("sensitive credential detail")
        self.backend.mutate = broken
        result = self.check()
        self.assertEqual(result["reason"], "backend_failure")
        self.assertNotIn("sensitive", str(result))
        class NotAProvider:
            def supports(self, *args): return True
            def sample(self, *args): return None
        with self.assertRaises(PlanError):
            self.select(backend=NotAProvider())

    def test_backend_cannot_mutate_authoritative_function_or_caller_arguments(self):
        original = self.backend.sample
        def mutate(function, arguments, context):
            function["ttl_seconds"] = 10000
            arguments["client_id"] = "changed"
            return original(function, arguments, context)
        self.backend.sample = mutate
        arguments = {"client_id": "synthetic-client"}
        report = ConformanceHarness(self.select()).check("test.client.ipv4", arguments, self.context, self.permissions)
        self.assertEqual(report["status"], "REJECTED")
        self.assertEqual(arguments, {"client_id": "synthetic-client"})


if __name__ == "__main__":
    unittest.main()
