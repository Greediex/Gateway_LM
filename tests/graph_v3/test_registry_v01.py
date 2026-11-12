"""T1 acceptance: data contracts, migration parity and fail-closed policy."""
import copy
import json
import tempfile
import unittest
from dataclasses import asdict, fields
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.contracts import Function, from_legacy
from gateway_pilot.graph_v3.graphs import GraphRegistry, Relation
from gateway_pilot.graph_v3.planner import Compiler, NodeState
from gateway_pilot.graph_v3.registry_v01 import load_registry
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.workflow import workflow_registry


REGISTRY = ROOT / "data/registry_v01.json"


class RegistryV01Tests(unittest.TestCase):
    def setUp(self):
        self.data = read_json(REGISTRY)

    def load(self, data=None):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "registry.json"
            path.write_text(json.dumps(self.data if data is None else data), encoding="utf-8")
            return load_registry(path)

    def state(self, registry, **overrides):
        case = {"target": {}, "capabilities": list(registry.functions),
                "permissions": ["network.read", "system.read", "network.write"]}
        case.update(overrides)
        return CaseState(case, registry)

    def test_field_by_field_legacy_equivalence(self):
        old = workflow_registry()
        new = GraphRegistry.from_v01(REGISTRY)
        _, ports, functions = from_legacy(old.legacy)
        self.assertEqual(len(new.skills), 8)
        self.assertEqual(len(new.functions), 17)
        self.assertEqual(set(new.functions), set(functions))
        self.assertEqual(new.ports, ports)
        expected_goals = {wid: [] for wid in new.workflows}
        expected_goals.update(copy.deepcopy(old.goal_ports))
        expected_goals['WF-INTERNET'].append('client.dns')
        self.assertEqual(new.goal_ports, expected_goals)
        self.assertEqual(new.function_conflicts, old.function_conflicts)
        for fid, expected in functions.items():
            for field in fields(Function):
                actual = getattr(new.functions[fid], field.name)
                value = getattr(expected, field.name)
                if field.name == "risk" and value == "READ":
                    # The legacy READ category splits into the two HTML read risks.
                    value = "PROBE" if fid in {"wan.probe", "dns.probe", "client.probe", "client.dns"} else "READ_ONLY"
                with self.subTest(function=fid, field=field.name):
                    self.assertEqual(actual, value)
            self.assertEqual(new.objective(fid), old.objective(fid))
            self.assertEqual(new.functions[fid].predicates, expected.predicates)
        for sid, expected in old.skills.items():
            for key, value in expected.items():
                self.assertEqual(new.skills[sid][key], value)
        self.assertEqual(
            [{f.name: getattr(e, f.name) for f in fields(Relation)} for e in new.relations],
            [asdict(e) for e in old.relations])
        self.assertEqual(dict(new.gsf.by_skill), dict(old.gsf.by_skill))
        self.assertEqual(dict(new.hf.outputs), dict(old.hf.outputs))
        self.assertEqual(new.eligible(self.state(new)), old.eligible(self.state(old)))

    def test_requirements_are_complete_and_titles_preserved(self):
        saved = read_json(ROOT / "data/requirements_v01.json")
        records = {r["requirement_id"]: r for r in saved["requirements"]}
        self.assertEqual(len(saved["requirements"]), 270)
        self.assertEqual(set(records), {f"F{i:03}" for i in range(1, 271)})
        missing = {"F202", "F203", "F204", "F205", "F206", "F207", "F208", "F209",
                   "F210", "F211", "F226", "F227", "F228", "F229", "F230"}
        self.assertEqual({key for key, r in records.items() if r["title_missing"]}, missing)
        self.assertTrue(all(records[key]["title"] is None for key in missing))
        source = ROOT / "runs/html_catalog_rag_v1/catalog.json"
        # Tests remain portable when the read-only extraction is not distributed.
        if source.exists():
            catalog = read_json(source)
            self.assertEqual(len(catalog["requirements"]), 255)
            for key, r in catalog["requirements"].items():
                self.assertEqual(records[key]["title"], r["title"])

    def test_new_metadata_is_loaded_without_legacy_inference(self):
        # These changes deliberately contradict the old name/scope-based rules.
        row = next(f for f in self.data["functions"] if f["function_id"] == "dns.probe")
        row["permission"] = "custom.read"
        row["preconditions"] = [{"port": "dns.config", "field": "resolver", "op": "eq", "value": "x"}]
        row["argument_sources"] = {}
        row["arguments_schema"]["required"] = []
        self.data["skills"][0]["completion_ports"] = []
        registry = self.load()
        f = registry.functions["dns.probe"]
        self.assertEqual(f.permission, "custom.read")
        self.assertEqual(f.argument_sources, {})
        self.assertEqual(f.predicates[0].value, "x")
        self.assertEqual(registry.skills["SK01"]["completion_ports"], [])
        for row in self.data["functions"]:
            f = registry.functions[row["function_id"]]
            for name in ("status", "adapter", "requirement_refs", "effects", "capability_probe",
                         "evidence_scope", "ttl_seconds", "on_unknown"):
                self.assertEqual(getattr(f, name), row[name])
        self.assertEqual(registry.legacy.functions["dns.probe"]["requires"], ["dns.config"])

    def test_rejects_missing_verifier(self):
        del self.data["functions"][0]["verifier"]
        with self.assertRaises(PlanError):
            self.load()

    def test_rejects_empty_verifier(self):
        self.data["functions"][0]["verifier"] = ""
        with self.assertRaises(PlanError):
            self.load()

    def test_rejects_nonpositive_or_nonfinite_timeout(self):
        for timeout in (0, -1, float("nan"), float("inf")):
            with self.subTest(timeout=timeout), self.assertRaises(PlanError):
                self.data["functions"][0]["timeout_ms"] = timeout
                self.load()

    def test_rejects_unknown_requirement_ref(self):
        for ref in ("F000", "F271", "wan.status"):
            with self.subTest(ref=ref), self.assertRaises(PlanError):
                self.data["functions"][0]["requirement_refs"] = [ref]
                self.load()

    def test_accepts_title_missing_requirement_ids(self):
        self.data["functions"][0]["requirement_refs"] = ["F202", "F230"]
        self.assertEqual(self.load().functions["clients.resolve"].requirement_refs, ["F202", "F230"])

    def test_rejects_unknown_skill_membership(self):
        self.data["functions"][0]["skill_ids"] = ["SK99"]
        with self.assertRaisesRegex(PlanError, "unknown_skill_membership"):
            self.load()

    def test_relation_type_sets_are_separate(self):
        edge = {"source": "SK04", "target": "SK05", "type": "alternative_to", "weight": 0.5,
                "origin": "test", "reason": "Separate pilot extension"}
        self.data["extension_relations"] = [edge]
        registry = self.load()
        self.assertEqual(registry.extension_relations[0].kind, "alternative_to")
        self.assertNotIn(registry.extension_relations[0], registry.gs.edges)
        self.data["relations"].append(edge)
        with self.assertRaises(PlanError):
            self.load()
        self.data["relations"].pop()
        self.data["extension_relations"][0]["type"] = "depends_on"
        with self.assertRaises(PlanError):
            self.load()
        self.data["extension_relations"][0]["type"] = "invented"
        with self.assertRaises(PlanError):
            self.load()

    def test_rejects_unknown_port_relation_endpoint_and_duplicates(self):
        for mutate in (
            lambda d: d["functions"][0]["outputs"].update({"unknown": "unknown/v1"}),
            lambda d: d["relations"][0].update(target="SK99"),
            lambda d: d["functions"].append(copy.deepcopy(d["functions"][0])),
            lambda d: d["skills"].append(copy.deepcopy(d["skills"][0])),
        ):
            data = copy.deepcopy(self.data)
            mutate(data)
            with self.assertRaises(PlanError):
                self.load(data)

    def test_write_and_unverified_never_eligible_even_with_permissive_state(self):
        permissive = SimpleNamespace(allowed=lambda f: True)
        for risk, status in (("WRITE", "PROBED_OK"), ("WRITE", "REPLAY_ONLY"),
                             ("READ_ONLY", "PROPOSED_NOT_VERIFIED"), ("PROBE", "PROPOSED_NOT_VERIFIED")):
            registry = self.load()
            # C1 rejects unsupported goals at load time. Mutate the already
            # loaded registry to independently exercise both execution gates.
            for function in registry.functions.values():
                function.risk, function.status = risk, status
            with self.subTest(risk=risk, status=status):
                self.assertEqual(registry.eligible(permissive), set())
                self.assertEqual(registry.eligible(self.state(registry)), set())
                with self.assertRaises(PlanError):
                    Compiler(registry).compile(["wan.status"], self.state(registry))

    def test_compiler_and_replay_match_legacy(self):
        results = []
        for registry in (GraphRegistry(), GraphRegistry.from_v01(REGISTRY)):
            case = {"target": {"client_id": "client_01"}, "capabilities": list(registry.functions),
                    "world": {"clients.resolve": {"client_id": "client_01"},
                              "client.ipv4": {"address": "192.0.2.2", "configured": True},
                              "client.probe": {"loss_pct": 0}, "dns.config": {"resolver": "192.0.2.1"},
                              "dns.probe": {"rcode": "NOERROR"}}}
            state = CaseState(case, registry)
            plan = Compiler(registry).compile(["client.probe", "dns.probe"], state)
            final = GraphRunner(registry, case, state).run(plan)
            self.assertTrue(all(n.state == NodeState.SUCCEEDED for n in final.nodes.values()))
            result = state.public()
            for evidence in result["evidence"]:
                # v0.1 deliberately fingerprints the additional contract metadata.
                self.assertEqual(evidence.pop("contract_digest"),
                                 registry.functions[evidence["function_id"]].digest())
                # T7 evidence records carry the Case id; v0.1 Cases get a fresh UUID (T5).
                self.assertEqual(evidence.pop("case_id"), state.case_id)
            results.append(result)
        self.assertEqual(*results)

    def test_status_and_adapter_hard_gate(self):
        fid = self.data["functions"][0]["function_id"]
        for status, adapter, expected in (
            ("REPLAY_ONLY", "synthetic_replay/v1", True),
            ("REPLAY_ONLY", "openwrt", False),
            ("PROBED_OK", "openwrt", True),
            ("PROPOSED_NOT_VERIFIED", "synthetic_replay/v1", False),
            ("PROBE_FAILED", "synthetic_replay/v1", False),
        ):
            registry = self.load()
            # Keep a valid goal catalog while testing the runtime gate in
            # isolation; invalid producer catalogs are rejected by C1 tests.
            registry.functions[fid].status = status
            registry.functions[fid].adapter = adapter
            with self.subTest(status=status, adapter=adapter):
                self.assertEqual(fid in registry.eligible(self.state(registry)), expected)

    def test_probe_needs_explicit_case_capability_and_permission(self):
        row = self.data["functions"][0]
        row["risk"] = "PROBE"
        registry = self.load()
        fid = row["function_id"]
        self.assertIn(fid, registry.eligible(self.state(registry)))
        self.assertNotIn(fid, registry.eligible(CaseState({"target": {}}, registry)))
        self.assertNotIn(fid, registry.eligible(self.state(registry, capabilities=[])))
        self.assertNotIn(fid, registry.eligible(self.state(registry, permissions=[])))
        self.assertNotIn(fid, registry.eligible(self.state(registry), excluded=[fid]))

    def test_rejects_legacy_risk_in_v01(self):
        self.data["functions"][0]["risk"] = "READ"
        with self.assertRaises(PlanError):
            self.load()

    def test_retry_and_cost_are_declarative(self):
        self.data["functions"][0].update(cost=2, latency_ms=123, retry={"max_attempts": 3})
        registry = self.load()
        self.assertEqual(registry.functions["clients.resolve"].retry_limit, 2)
        self.assertEqual(registry.objective("clients.resolve"), 2.123)

    def test_loader_does_not_read_frozen_registry_or_catalog(self):
        import gateway_pilot.graph_v3.registry_v01 as module
        original = module.read_json

        def read(path):
            self.assertIn(Path(path).name, {"registry_v01.json", "requirements_v01.json", "workflow_catalog_v01.json"})
            return original(path)

        with patch.object(module, "read_json", side_effect=read):
            self.assertEqual(len(GraphRegistry.from_v01(REGISTRY).functions), 17)

    def test_default_legacy_contracts_and_read_gate_stay_unchanged(self):
        registry = GraphRegistry()
        state = self.state(registry)
        self.assertEqual(registry.functions["wan.status"].risk, "READ")
        self.assertIn("wan.status", registry.eligible(state))
        self.assertNotIn("dns.apply", registry.eligible(state))
        self.assertEqual(set(asdict(registry.functions["wan.status"])), {f.name for f in fields(Function)})


if __name__ == "__main__":
    unittest.main()
