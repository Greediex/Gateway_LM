"""FND-06: selected READ metadata enters the shared Core, never legacy replay."""
import copy
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from gateway_pilot.core import ROOT, PlanError, execute
from gateway_pilot.adapters.bindings import BindingSelection, TargetContext, binding_digest, declare_binding
from gateway_pilot.adapters.read_backends import ReplayReadBackend
from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.application.feature_availability import AvailabilityService
from gateway_pilot.command_catalog.builder import build_registry
from gateway_pilot.command_catalog.compatibility import compile_registry, load_runtime_registry
from gateway_pilot.command_catalog.loader import load_catalog, read_json, digest, canonical_bytes
from gateway_pilot.command_catalog.runtime import ReadRuntime
from gateway_pilot.features.registry import FeatureRegistry, read_feature_flags, read_feature_manifests
from gateway_pilot.graph_v3.checkpoint import EvidenceCheckpoint
from gateway_pilot.graph_v3.execution_kernel import execute_ready_once
from gateway_pilot.graph_v3.planner import Compiler, NodeState
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState

VALUES = {
    "clients.resolve": {"client.identity": {"client_id": "synthetic-client"}},
    "client.ipv4": {"client.ipv4": {"configured": True, "address": "192.0.2.10"}},
    "wifi.station": {"wifi.station": {"associated": True, "rssi_dbm": -60}},
}


class Backend(ReplayReadBackend):
    def __init__(self, values=VALUES):
        super().__init__(values, client_id="synthetic-client")
        self.supported, self.calls, self.probes = True, 0, 0
        self.mutate = lambda r: r

    def supports(self, fid, context):
        self.probes += 1
        return self.supported and super().supports(fid, context)

    def sample(self, function, arguments, context):
        self.calls += 1
        return self.mutate(super().sample(function, arguments, context))


class RuntimeV02Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "registry.json"
        self.policy = read_json(ROOT / "config/catalog_policy.example.json")
        self.artifact = build_registry(load_catalog(ROOT / "catalog"),
                                      read_json(ROOT / "config/catalog_selection.example.json"), self.policy, self.path)
        self.backend = Backend()
        self.time = 100.0
        self.permissions = frozenset({"network.read"})
        self.context = TargetContext("client", "synthetic-client", self.backend.environment_id)
        self.policy_context = digest({"principal": "synthetic-operator", "acl_revision": 1})
        self.runtime = self.make_runtime()

    def make_runtime(self, *, artifact=None, backend=None, permissions=None, **changes):
        artifact = self.artifact if artifact is None else artifact
        backend = self.backend if backend is None else backend
        context = TargetContext("client", "synthetic-client", backend.environment_id)
        bindings = [declare_binding(artifact, fid, "test."+fid, "replay.seed", backend, context)
                    for fid in backend._values]
        selection = BindingSelection(artifact, self.policy, bindings,
            approved_digests=frozenset(binding_digest(b) for b in bindings),
            backends={"replay.seed": backend}, context=context)
        args = dict(approved_digest=artifact["content_digest"], selection=selection, context=context,
                    permissions=self.permissions if permissions is None else permissions,
                    policy_context_id=self.policy_context, clock=lambda: self.time)
        args.update(changes)
        return ReadRuntime(artifact, self.policy, **args)

    def setup_plan(self, goals=("client.ipv4",), runtime=None):
        rt = self.runtime if runtime is None else runtime
        case, state = rt.new_case(case_id="migration-case")
        runner = GraphRunner(rt.registry, case, state, max_repairs=0)
        return runner, runner.attach(Compiler(rt.registry).compile(goals, state))

    def step(self, runner, plan):
        return execute_ready_once(runner, plan, plan.goals, ordered_ids=plan.topological())[0]

    def test_replay_runs_shared_core_dependency_args_and_verifies_contracts(self):
        self.assertEqual((self.backend.calls, self.backend.probes), (0, 0))
        snapshot = self.runtime.probe()
        self.assertTrue(all(f.status == "AVAILABLE" for f in snapshot.functions))
        self.assertEqual(self.backend.calls, 0)
        runner, plan = self.runtime.execute(["client.ipv4", "wifi.station"])
        self.assertEqual(len(plan.nodes), 3)
        self.assertTrue(all(n.state == NodeState.SUCCEEDED for n in plan.nodes.values()))
        self.assertTrue(any(e.kind == "DATA" and e.port == "client.identity" for e in plan.edges))
        self.assertEqual(runner.calls, 3)
        self.assertEqual(len(runner.contract_b), 3)
        for e in runner.state.evidence:
            f = self.runtime.registry.functions[e["function_id"]]
            self.assertTrue(runner.state.usable(e, f.outputs[e["port"]]))
            self.assertEqual(e["contract_digest"], f.digest())
            self.assertNotEqual(e["contract_digest"], f.metadata_digest)
            self.assertNotEqual(e["contract_digest"], self.artifact["content_digest"])
        calls = runner.state.executed
        self.assertEqual(calls[0]["arguments"], {})
        self.assertTrue(all(row["arguments"] == {"client_id": "synthetic-client"} for row in calls[1:]))
        self.assertEqual(self.runtime.registry.legacy.functions["client.ipv4"]["risk"], "READ_ONLY")
        f = self.runtime.registry.functions["client.ipv4"]
        metadata = next(f for f in self.artifact["functions"] if f["function_id"] == "client.ipv4")
        self.assertEqual(f.retry_limit, metadata["retry"]["max_attempts"]-1)
        self.assertEqual(f.ttl_seconds, metadata["ttl_seconds"])

    def test_no_probe_no_capability_and_no_conformance_injection(self):
        case, state = self.runtime.new_case()
        self.assertEqual(self.runtime.registry.eligible(state), set())
        with self.assertRaises(PlanError):
            Compiler(self.runtime.registry).compile(["client.ipv4"], state)
        self.assertEqual(self.backend.calls, 0)
        self.assertFalse(self.runtime.allowed(self.runtime.registry.functions["clients.resolve"], state))

    def test_real_core_producer_connects_feature_availability(self):
        registry = FeatureRegistry(self.artifact, self.policy,
            read_feature_manifests(ROOT / "examples/features.replay.json"),
            read_feature_flags(ROOT / "config/feature_flags.example.json"))
        service = AvailabilityService(registry, clock=lambda: self.time)
        snapshot = self.runtime.probe()
        args = dict(context=self.context, permissions=self.permissions, policy_context_id=self.policy_context)
        self.assertEqual(service.evaluate("network.client.connectivity", capabilities=snapshot, **args)["status"], "READY")
        self.time += 31
        self.assertEqual(service.evaluate("network.client.connectivity", capabilities=snapshot, **args)["status"], "UNAVAILABLE")
        self.assertFalse(self.runtime.registry.eligible(self.runtime.new_case()[1]))

    def test_acl_target_environment_and_expiry_block_before_io(self):
        denied = self.make_runtime(permissions=frozenset())
        self.assertTrue(all(f.status == "PERMISSION_DENIED" for f in denied.probe().functions))
        self.assertEqual(self.backend.probes, 0)
        self.runtime.probe()
        for field, value in (("permissions", set()), ("config_version", "changed"),
                             ("boot_id", "changed"), ("target", {"scope": "client", "client_id": "other"})):
            with self.subTest(field=field):
                runner, plan = self.setup_plan()
                setattr(runner.state, field, value)
                self.assertIsNone(self.step(runner, plan))
        runner, plan = self.setup_plan()
        self.time += 31
        self.assertIsNone(self.step(runner, plan))
        self.assertEqual(self.backend.calls, 0)

    def test_contract_mutation_rejected_after_compile(self):
        for field, value in (("version", "99.0.0"), ("ttl_seconds", 999), ("timeout_ms", 999),
                             ("risk", "READ"), ("port_versions", {})):
            rt = self.make_runtime()
            rt.probe()
            runner, plan = self.setup_plan(runtime=rt)
            setattr(rt.registry.functions["clients.resolve"], field, value)
            with self.subTest(field=field), self.assertRaisesRegex(PlanError, "contract_changed_after_compile"):
                self.step(runner, plan)
        self.assertEqual(self.backend.calls, 0)

    def test_no_legacy_fallback_with_adapter_missing_or_world_injected(self):
        self.runtime.probe()
        runner, plan = self.setup_plan()
        runner.case.pop("adapter")
        runner.case["world"] = VALUES
        self.assertEqual(self.step(runner, plan).state, NodeState.FAILED)
        self.assertEqual(runner.state.evidence, [])
        self.assertEqual(self.backend.calls, 0)
        with self.assertRaisesRegex(PlanError, "v02_requires_typed_core_execution"):
            execute("clients.resolve", {}, runner.state, runner.case, self.runtime.registry.legacy)

    def test_unknown_format_and_unapproved_or_wrong_artifact_fail_closed(self):
        with self.assertRaisesRegex(PlanError, "unsupported_contract_format"):
            load_runtime_registry(self.path, contract_format="v9")
        with self.assertRaises(PlanError):
            compile_registry(self.artifact, self.policy, approved_digest="0"*64)
        registry = load_runtime_registry(self.path, contract_format="v0.2", policy=self.policy,
                                         approved_digest=self.artifact["content_digest"])
        self.assertEqual(registry.contract_format, "v0.2")
        self.assertIsNone(getattr(registry, "runtime", None))
        case, _ = self.runtime.new_case()
        self.assertFalse(registry.eligible(CaseState(case, registry)))
        registry.contract_format = "unknown"
        self.assertFalse(registry.eligible(CaseState(case, registry)))
        for risk in ("WRITE", "PROBE", "READ", "unknown"):
            broken = copy.deepcopy(self.artifact)
            broken["functions"][0]["risk"] = risk
            broken["content_digest"] = digest({k:v for k,v in broken.items() if k != "content_digest"})
            with self.subTest(risk=risk), self.assertRaises(PlanError):
                compile_registry(broken, self.policy, approved_digest=broken["content_digest"])

    def test_probe_loss_and_backend_revision_change_never_fallback(self):
        for mutation in (lambda: setattr(self.backend, "supported", False),
                         lambda: setattr(self.backend, "revision", "99.0.0")):
            self.backend.supported, self.backend.revision = True, "1.0.0"
            self.runtime.probe()
            runner, plan = self.setup_plan()
            mutation()
            self.assertEqual(self.step(runner, plan).state, NodeState.FAILED)
            self.assertEqual(runner.state.evidence, [])
        self.assertEqual(self.backend.calls, 0)

    def test_invalid_results_timeout_and_stale_time_never_admit_evidence(self):
        def alter(key, value):
            def mutate(result):
                row = copy.deepcopy(result.observations[0]); row[key] = value
                return ToolResult(observations=(row,))
            return mutate
        mutations = [alter("target", "other"), alter("source", "linux_client/fake"),
                     alter("environment_id", "0"*64), alter("function_version", "99.0.0"),
                     alter("metadata_function_digest", "0"*64), alter("port", "wrong.port"),
                     alter("value", {"client_id": 42}), alter("age_s", float("nan")),
                     alter("observed_at", (datetime.now(UTC)-timedelta(hours=1)).isoformat()),
                     alter("observed_at", (datetime.now(UTC)+timedelta(hours=1)).isoformat()),
                     lambda r: ToolResult(observations=r.observations*2),
                     lambda r: ToolResult(is_error=True, error_code="failure")]
        for mutation in mutations:
            self.backend.mutate = mutation
            rt = self.make_runtime(); rt.probe()
            runner, plan = self.setup_plan(runtime=rt)
            with self.subTest(mutation=mutation):
                self.assertEqual(self.step(runner, plan).state, NodeState.FAILED)
                self.assertEqual(runner.state.evidence, [])
        def timeout(result):
            self.time += 5
            return result
        self.backend.mutate = timeout
        rt = self.make_runtime(); rt.probe()
        runner, plan = self.setup_plan(runtime=rt)
        self.assertEqual(self.step(runner, plan).state, NodeState.FAILED)
        self.assertEqual(runner.state.evidence, [])

    def test_v02_evidence_cannot_be_relabelled_or_used_after_contract_mutation(self):
        self.runtime.probe()
        runner, _ = self.runtime.execute(["client.ipv4"])
        evidence = runner.state.fact("client.ipv4")
        for field, value in (("contract_digest", "0"*64), ("function_version", "99.0.0"),
                             ("metadata_function_digest", "0"*64), ("environment_id", "0"*64)):
            old = evidence[field]; evidence[field] = value
            self.assertIsNone(runner.state.fact("client.ipv4"))
            evidence[field] = old
        self.runtime.registry.functions["client.ipv4"].version = "99.0.0"
        self.assertIsNone(runner.state.fact("client.ipv4"))

    def rebuild(self, catalog, selection=None):
        source = Path(self.tmp.name)/"synthetic-source"
        for group, key in (("functions", "function_id"), ("ports", "port_id"), ("skills", "skill_id")):
            for row in catalog[group]:
                folder = source/group/row["domain"] if group == "functions" else source/group
                folder.mkdir(parents=True, exist_ok=True)
                (folder/(row[key]+".json")).write_bytes(canonical_bytes(row))
        return build_registry(load_catalog(source),
            read_json(ROOT/"config/catalog_selection.example.json") if selection is None else selection,
            self.policy, Path(self.tmp.name)/"synthetic.json")

    def test_new_function_and_multi_output_backend_require_no_runner_edits(self):
        catalog = load_catalog(ROOT/"catalog")
        f = next(f for f in catalog["functions"] if f["function_id"] == "client.ipv4")
        f["function_id"] = "client.address_snapshot"
        f["outputs"]["wifi.station"] = "2.0.0"
        for skill in catalog["skills"]:
            if "client.ipv4" in skill["function_refs"]:
                skill["function_refs"][f["function_id"]] = skill["function_refs"].pop("client.ipv4")
        selection = read_json(ROOT/"config/catalog_selection.example.json")
        selection["functions"][f["function_id"]] = selection["functions"].pop("client.ipv4")
        artifact = self.rebuild(catalog, selection)
        class ExtendedBackend(Backend):
            probe_ids = {**Backend.probe_ids, "client.address_snapshot": "probe.replay.client_ipv4"}
        values = copy.deepcopy(VALUES)
        values["client.address_snapshot"] = values.pop("client.ipv4")
        values["client.address_snapshot"].update(VALUES["wifi.station"])
        backend = ExtendedBackend(values)
        rt = self.make_runtime(artifact=artifact, backend=backend)
        rt.probe()
        runner, plan = rt.execute(["client.ipv4", "wifi.station"])
        self.assertTrue(all(n.state == NodeState.SUCCEEDED for n in plan.nodes.values()))
        self.assertEqual({n.function_id for n in plan.nodes.values()}, {"clients.resolve", "client.address_snapshot"})
        self.assertEqual(len(runner.state.evidence), 3)

    def test_proposed_lifecycle_is_not_executable_despite_approved_digest(self):
        catalog = load_catalog(ROOT/"catalog")
        catalog["functions"][0]["lifecycle"] = "PROPOSED"
        artifact = self.rebuild(catalog)
        with self.assertRaisesRegex(PlanError, "runtime_read_lifecycle_required"):
            compile_registry(artifact, self.policy, approved_digest=artifact["content_digest"])

    def test_checkpoint_principal_or_binding_change_rejects_all_reuse(self):
        self.runtime.probe()
        runner, _ = self.runtime.execute(["client.ipv4"])
        runner.state.case_id = "migration-case"
        checkpoint = EvidenceCheckpoint(Path(self.tmp.name)/"checkpoint.json", b"k"*32, clock=lambda: 1000.0)
        checkpoint.save(self.runtime.registry, runner.state, "read", ["client.ipv4"])
        other = self.make_runtime(policy_context_id="f"*64)
        _, state = other.new_case(case_id="migration-case")
        self.assertEqual(checkpoint.restore(other.registry, state, "read", ["client.ipv4"]), 0)
        self.assertEqual(state.evidence, [])
        other = self.make_runtime()
        other._binding_pins = {"reviewed.other_binding": "e"*64}
        _, state = other.new_case(case_id="migration-case")
        self.assertEqual(checkpoint.restore(other.registry, state, "read", ["client.ipv4"]), 0)

    def test_changed_registry_snapshot_rejects_checkpoint_even_with_same_function_metadata(self):
        self.runtime.probe()
        runner, _ = self.runtime.execute(["client.ipv4"])
        runner.state.case_id = "migration-case"
        checkpoint = EvidenceCheckpoint(Path(self.tmp.name)/"checkpoint.json", b"k"*32, clock=lambda: 1000.0)
        checkpoint.save(self.runtime.registry, runner.state, "read", ["client.ipv4"])
        catalog = load_catalog(ROOT/"catalog")
        catalog["skills"][0]["description"] += " Synthetic changed registry context."
        artifact = self.rebuild(catalog)
        other = self.make_runtime(artifact=artifact)
        self.assertNotEqual(other.registry.functions["client.ipv4"].digest(),
                            self.runtime.registry.functions["client.ipv4"].digest())
        _, state = other.new_case(case_id="migration-case")
        self.assertEqual(checkpoint.restore(other.registry, state, "read", ["client.ipv4"]), 0)
        self.assertEqual(state.evidence, [])

    def test_backend_timeout_exception_support_loss_during_sample_and_age(self):
        def fail(result):
            raise TimeoutError("sensitive payload")
        def loss(result):
            self.backend.supported = False
            return result
        for mutation in (fail, loss):
            self.backend.supported = True
            self.backend.mutate = mutation
            rt = self.make_runtime(); rt.probe()
            runner, plan = self.setup_plan(runtime=rt)
            node = self.step(runner, plan)
            self.assertEqual(node.state, NodeState.FAILED)
            self.assertEqual(runner.state.evidence, [])
            self.assertNotIn("sensitive", str(node.failure))
        self.backend.supported = True
        def old(result):
            rows = copy.deepcopy(result.observations)
            for row in rows:
                row["observed_at"] = (datetime.now(UTC)-timedelta(seconds=5)).isoformat()
            return ToolResult(observations=rows)
        self.backend.mutate = old
        rt = self.make_runtime(); rt.probe()
        runner, _ = rt.execute(["client.ipv4"])
        self.assertTrue(all(e["age_s"] >= 5 for e in runner.state.evidence))
        self.time += 26
        self.assertIsNone(runner.state.fact("client.ipv4"))

    def test_checkpoint_same_snapshot_restores_but_other_contract_does_not(self):
        self.runtime.probe()
        runner, _ = self.runtime.execute(["client.ipv4"])
        runner.state.case_id = "migration-case"
        checkpoint = EvidenceCheckpoint(Path(self.tmp.name)/"checkpoint.json", b"k"*32, clock=lambda: 1000.0)
        self.assertEqual(checkpoint.save(self.runtime.registry, runner.state, "read", ["client.ipv4"]), 2)
        _, state = self.runtime.new_case(case_id="migration-case")
        self.assertEqual(checkpoint.restore(self.runtime.registry, state, "read", ["client.ipv4"]), 2)
        self.assertIsNotNone(state.fact("client.ipv4"))
        self.runtime.registry.functions["client.ipv4"].version = "99.0.0"
        _, state = self.runtime.new_case(case_id="migration-case")
        self.assertEqual(checkpoint.restore(self.runtime.registry, state, "read", ["client.ipv4"]), 0)


if __name__ == "__main__":
    unittest.main()
