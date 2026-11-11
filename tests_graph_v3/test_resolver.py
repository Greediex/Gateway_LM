"""T4 acceptance: read-only Contract 0 selection, expansion and entry points."""
import copy
import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.contracts import Truth
from gateway_pilot.graph_v3.graphs import GraphRegistry, Relation
from gateway_pilot.graph_v3.planner import Compiler
from gateway_pilot.graph_v3.resolver import ResolverBudget, resolve
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.workflow import diagnose, replay_from_fixture, workflow_registry


class ResolverTests(unittest.TestCase):
    def setUp(self):
        self.registry = workflow_registry()
        self.case = {"target": {"scope": "client", "selector": "laptop-an"},
                     "capabilities": list(self.registry.functions), "world": {}}
        self.state = CaseState(self.case, self.registry, clock=lambda: 0)

    def fact(self, port, value):
        evidence = {"id": "fact:" + port, "port": port, "value": value,
                    "function_id": self.registry.hf.outputs[port][0], "status": "OK",
                    "scope": self.registry.ports[port].scope, "target": "gateway_01",
                    "source": "synthetic_replay/test", "ttl_s": 30, "age_s": 0}
        self.state.evidence.append(evidence)
        self.state.record(evidence)

    def dns(self, **kwargs):
        return resolve(self.registry, self.state, "Kiểm tra DNS của laptop An",
                       selected_skills=("SK05",), goals=("client.dns",), **kwargs)

    def test_a_client_dns_adds_cross_skill_identity_producer(self):
        result = self.dns()
        self.assertEqual(result["decision"], "EXPAND_PREREQUISITES")
        self.assertIn("clients.resolve", result["function_candidates"])
        self.assertEqual(result["case_state"]["client.identity"]["status"], "UNKNOWN")
        row = next(r for r in result["cross_skill_candidates"] if r["function_id"] == "clients.resolve")
        self.assertEqual(row["reason"], "producer_for:client.identity")
        self.assertGreater(result["plan_revision"], 1)
        for row in result["cross_skill_candidates"]:
            self.assertTrue(any(m["input"] == row["reason"].removeprefix("producer_for:")
                                for m in result["missing_inputs"]))
        Compiler(self.registry).compile((), self.state, requested=result["function_candidates"],
                                        skill_context=result["skill_context"])

    def test_b_link_down_does_not_imply_route_predicate_false(self):
        self.fact("wan.status", {"link_up": False})
        predicate = self.registry.functions["wan.probe"].predicates[0]
        # Actual contract: default_route == true, NOT link_up == true.
        self.assertEqual(predicate.port, "wan.routes")
        self.assertEqual(predicate.evaluate(self.state), Truth.UNKNOWN)
        unknown = resolve(self.registry, self.state, "WAN đã lỗi", selected_skills=("SK04",),
                          goals=("wan.status", "wan.probe"))
        self.assertNotIn("wan.status", unknown["function_candidates"])
        self.assertNotIn("wan.probe", unknown["function_candidates"])
        self.assertIn("wan.routes", unknown["function_candidates"])
        self.assertEqual(unknown["decision"], "EXPAND_PREREQUISITES")
        self.assertFalse(any(r["reason"].startswith("false_precondition") for r in unknown["rejected"]))
        self.fact("wan.routes", {"default_route": False})
        self.assertEqual(predicate.evaluate(self.state), Truth.FALSE)
        result = resolve(self.registry, self.state, "WAN đã lỗi", selected_skills=("SK04",),
                         goals=("wan.status", "wan.probe"))
        self.assertNotIn("wan.status", result["function_candidates"])
        self.assertNotIn("wan.probe", result["function_candidates"])
        self.assertEqual(result["decision"], "INCOMPLETE")
        self.assertIn({"function_id": "wan.probe", "reason": "false_precondition:wan.routes.default_route"},
                      result["rejected"])

    def test_c_change_dns_is_blocked_without_adapter_calls(self):
        with patch("gateway_pilot.core.execute") as core, patch("gateway_pilot.graph_v3.runner.execute") as runner:
            result = resolve(self.registry, self.state, "Đổi DNS router sang 8.8.8.8", intent="CHANGE")
            self.assertEqual(result["decision"], "BLOCKED")
            self.assertFalse(result["policy"]["write_approval"])
            self.assertEqual(result["function_candidates"], [])
            self.assertIn({"function_id": "dns.apply", "reason": "policy:WRITE"}, result["rejected"])
            core.assert_not_called()
            runner.assert_not_called()

    def test_missing_only_producer_capability_is_incomplete(self):
        self.state.capabilities.remove("client.ipv4")
        result = self.dns()
        self.assertEqual(result["decision"], "INCOMPLETE")
        self.assertNotIn("client.dns", result["function_candidates"])
        self.assertIn({"function_id": "client.dns", "input": "client.ipv4"}, result["missing_inputs"])

    def test_depth_zero_reports_gap_and_budget(self):
        result = self.dns(budget=ResolverBudget(max_depth=0))
        self.assertEqual(result["function_candidates"], [])
        self.assertEqual(result["decision"], "INCOMPLETE")
        self.assertTrue(result["missing_inputs"])
        self.assertTrue(any("budget_exhausted:max_depth" in r["reason"] for r in result["rejected"]))

    def test_node_and_latency_budgets_are_reported(self):
        for budget in (ResolverBudget(max_nodes=0), ResolverBudget(max_latency_ms=0)):
            with self.subTest(budget=budget):
                result = self.dns(budget=budget)
                self.assertEqual(result["decision"], "INCOMPLETE")
                self.assertEqual(result["function_candidates"], [])
                self.assertTrue(any("budget_exhausted" in r["reason"] for r in result["rejected"]))

    def test_missing_target_or_identity_producer_asks_user(self):
        self.state.target = {}
        self.assertEqual(self.dns()["decision"], "ASK_USER")
        self.state.target = {"selector": "laptop-an"}
        self.state.capabilities.remove("clients.resolve")
        self.assertEqual(self.dns()["decision"], "ASK_USER")

    def test_selected_multiskill_context_reaches_compiler(self):
        result = resolve(self.registry, self.state, "system.logs", selected_skills=("SK09",),
                         goals=("system.logs",))
        self.assertEqual(result["skill_context"]["system.logs"], "SK09")
        plan = Compiler(self.registry).compile((), self.state, requested=result["function_candidates"],
                                               skill_context=result["skill_context"])
        self.assertEqual(plan.nodes["system.logs"].skill_context, "SK09")
        self.assertEqual(Compiler(self.registry).compile(("system.logs",), self.state)
                         .nodes["system.logs"].skill_context, "SK08")

    def test_cross_skill_multiskill_context_uses_highest_retrieval_score(self):
        self.registry.functions["dns.probe"].inputs["system.logs"] = self.registry.ports["system.logs"]
        self.registry.rebuild()
        retrieval = self.registry.retrieve("DNS", ("dns.probe",), self.state)
        retrieval["scores"].update({"s:SK08": 0.01, "s:SK09": 0.9})
        with patch.object(self.registry, "retrieve", return_value=retrieval):
            result = resolve(self.registry, self.state, "DNS", selected_skills=("SK05",), goals=("dns.probe",))
        self.assertEqual(result["skill_context"]["system.logs"], "SK09")
        self.assertIn({"function_id": "dns.probe", "input": "system.logs"}, result["missing_inputs"])
        self.assertIn({"function_id": "system.logs", "from_skill": "SK09", "reason": "producer_for:system.logs"},
                      result["cross_skill_candidates"])

    def test_contract_schema_and_resolver_never_executes(self):
        schema = read_json(ROOT / "docs/contracts/contract_0.schema.json")
        Draft202012Validator.check_schema(schema)
        with patch("gateway_pilot.core.execute") as execute:
            for result in (self.dns(), resolve(self.registry, self.state, "nonsense_xyz", goals=())):
                Draft202012Validator(schema).validate(result)
            execute.assert_not_called()
        invalid = self.dns()
        invalid["decision"] = "MAYBE"
        self.assertFalse(Draft202012Validator(schema).is_valid(invalid))

    def test_v01_and_legacy_agree_on_candidates(self):
        new = GraphRegistry.from_v01()
        for goals, selected in ((("client.dns",), ("SK05",)), (("wan.probe",), ("SK04",)),
                                (("system.logs",), ("SK09",))):
            with self.subTest(goals=goals):
                other = CaseState(self.case, new, clock=lambda: 0)
                a = resolve(self.registry, self.state, "diagnostics", goals=goals, selected_skills=selected)
                b = resolve(new, other, "diagnostics", goals=goals, selected_skills=selected)
                # v0.1 has additional catalog text/nodes, so retrieval scores
                # (and the order of independent candidates) may differ.
                self.assertEqual(set(a["function_candidates"]), set(b["function_candidates"]))

    def test_conflicts_pruned_and_completed_outputs_not_proposed(self):
        self.registry.function_conflicts.add(frozenset(("wan.status", "system.resources")))
        result = resolve(self.registry, self.state, "WAN CPU", selected_skills=("SK04", "SK08"),
                         goals=("wan.status", "system.resources"))
        self.assertEqual(len(result["function_candidates"]), 1)
        self.assertTrue(any("conflict" in r["reason"] for r in result["rejected"]))
        self.registry.function_conflicts.clear()
        self.registry.gs.apply(self.registry.gs.propose_edge(Relation("SK04", "SK08", "conflicts_with"),
                               reason="T4 conflict test"), permissions={"graph.edit"})
        result = resolve(self.registry, self.state, "WAN CPU", selected_skills=("SK04", "SK08"),
                         goals=("wan.status", "system.resources"))
        self.assertEqual(len(result["function_candidates"]), 1)
        self.fact("wan.status", {"link_up": True})
        result = resolve(self.registry, self.state, "wan.status", goals=("wan.status",))
        self.assertEqual(result["function_candidates"], [])

    def test_diagnose_resolver_matches_ten_fixtures_across_five_workflows(self):
        fixtures = read_json(ROOT / "data/cases.json")
        selected = []
        for wf in ("WF-018", "WF-023", "WF-024", "WF-039", "WF-INTERNET"):
            templates = list(dict.fromkeys(c["template"] for c in fixtures if c["workflow"] == wf))[:2]
            selected.extend(next(c for c in fixtures if c["workflow"] == wf and c["template"] == template)
                            for template in templates)
        self.assertEqual(len(selected), 10)
        for fixture in selected:
            with self.subTest(case=fixture["id"]):
                replay = replay_from_fixture(copy.deepcopy(fixture), self.registry)
                default = diagnose(fixture["request"], replay, registry=self.registry)
                result = diagnose(fixture["request"], replay, registry=self.registry, route="resolver")
                self.assertEqual((result["terminal"]["diagnosis"], result["case_status"]),
                                 (default["terminal"]["diagnosis"], default["case_status"]))
                self.assertEqual(default["route"], "fastpath")
                self.assertEqual(result["route"], "resolver")
                self.assertTrue(result["graph"]["contract_0"])
                self.assertLessEqual(result["graph"]["calls"], 12)

    def test_hard_gates_remain_hard_with_high_retrieval_scores(self):
        for registry in (self.registry, GraphRegistry.from_v01()):
            state = CaseState(self.case, registry, clock=lambda: 0)
            for restriction in ("capability", "permission", "actor", "status"):
                with self.subTest(registry=type(registry), restriction=restriction):
                    if restriction == "status" and not hasattr(registry.functions["system.resources"], "status"):
                        continue
                    altered = copy.copy(state)
                    actor = None
                    original_status = getattr(registry.functions["system.resources"], "status", None)
                    if restriction == "capability":
                        altered.capabilities = state.capabilities - {"system.resources"}
                    elif restriction == "permission":
                        altered.permissions = set()
                    elif restriction == "actor":
                        actor = {"permissions": []}
                    else:
                        registry.functions["system.resources"].status = "PROPOSED_NOT_VERIFIED"
                    result = resolve(registry, altered, "system.resources CPU RAM", goals=("system.resources",),
                                     selected_skills=("SK08",), actor=actor)
                    self.assertEqual(result["function_candidates"], [])
                    self.assertEqual(result["decision"], "BLOCKED")
                    if original_status is not None:
                        registry.functions["system.resources"].status = original_status

    def test_cycle_rejected_and_no_orphan_prerequisites_returned(self):
        self.registry.functions["clients.resolve"].inputs["client.dns"] = self.registry.ports["client.dns"]
        self.registry.rebuild()
        result = self.dns()
        self.assertEqual(result["decision"], "INCOMPLETE")
        self.assertEqual(result["function_candidates"], [])
        self.assertTrue(any(r["reason"] == "dependency_cycle" for r in result["rejected"]))

    def test_no_lexical_seed_still_expands_goal_deficit(self):
        retrieval = {"functions": [], "scores": {}, "rerank_scores": {}, "query": "unmatched",
                     "seeds": {}, "lexical_match": False}
        with patch.object(self.registry, "retrieve", return_value=retrieval):
            result = self.dns()
        self.assertIn("clients.resolve", result["function_candidates"])
        self.assertEqual(result["decision"], "EXPAND_PREREQUISITES")

    def test_retrieval_controls_shortlist_instead_of_forcing_every_goal(self):
        retrieval = {"functions": ["system.resources"], "scores": {}, "rerank_scores": {},
                     "query": "CPU", "seeds": {"s:SK08": 1.0}, "lexical_match": True}
        with patch.object(self.registry, "retrieve", return_value=retrieval):
            result = resolve(self.registry, self.state, "CPU", goals=("wan.status",))
        self.assertEqual(result["function_candidates"], [])
        self.assertEqual(result["decision"], "INCOMPLETE")

    def test_rerank_then_declared_objective_choose_conflicting_shortlist(self):
        self.registry.function_conflicts.add(frozenset(("wan.status", "system.resources")))
        retrieval = {"functions": ["wan.status", "system.resources"], "scores": {},
                     "rerank_scores": {"f:wan.status": 1, "f:system.resources": 2},
                     "query": "WAN CPU", "seeds": {}}
        def choose():
            with patch.object(self.registry, "retrieve", return_value=retrieval):
                return resolve(self.registry, self.state, "WAN CPU", goals=("wan.status", "system.resources"),
                               selected_skills=("SK04", "SK08"))["function_candidates"]
        self.assertEqual(choose(), ["system.resources"])
        retrieval["rerank_scores"]["f:system.resources"] = 1
        self.registry.functions["wan.status"].cost = 0.5
        self.assertEqual(choose(), ["wan.status"])

    def test_diagnose_contracts_show_newly_verified_batches_and_bounded_calls(self):
        fixture = next(c for c in read_json(ROOT / "data/cases.json") if c["template"] == "wan_healthy")
        replay = replay_from_fixture(fixture, self.registry)
        for limit in (0, 1, 12):
            with self.subTest(limit=limit):
                result = diagnose(fixture["request"], replay, registry=self.registry, route="resolver", max_calls=limit)
                graph = result["graph"]
                self.assertLessEqual(graph["calls"], limit)
                self.assertTrue(graph["contract_0"])
                for contract in graph["contract_0"]:
                    Draft202012Validator(read_json(ROOT / "docs/contracts/contract_0.schema.json")).validate(contract)
                if limit == 12:
                    self.assertEqual(graph["contract_0"][0]["case_state"]["wan.status"]["status"], "UNKNOWN")
                    self.assertEqual(graph["contract_0"][1]["case_state"]["wan.status"]["status"], "KNOWN")

    def test_resolver_route_write_and_ambiguous_target_make_no_calls(self):
        fixture = read_json(ROOT / "data/cases.json")[0]
        replay = replay_from_fixture(fixture, self.registry)
        with patch("gateway_pilot.core.execute") as core, patch("gateway_pilot.graph_v3.runner.execute") as runner:
            for request in ("Đổi DNS router sang 8.8.8.8", "Laptop Bình không vào Internet"):
                result = diagnose(request, replay, registry=self.registry, route="resolver")
                self.assertEqual(result["graph"]["calls"], 0)
                self.assertTrue(result["graph"]["contract_0"])
            core.assert_not_called()
            runner.assert_not_called()

    def test_acquire_compiles_only_resolver_candidates(self):
        from gateway_pilot.graph_v3.orchestrator import acquire
        case = next(c for c in read_json(ROOT / "data/cases.json") if c["template"] == "wan_healthy")
        state = CaseState(case, self.registry)
        trace = acquire(case, self.registry, state)
        self.assertIsInstance(trace["contract_0"], dict)
        contracts = {c["plan_revision"]: c for c in trace["contract_0_history"]}
        for plan in trace["plans"]:
            self.assertLessEqual(set(plan["nodes"]), set(contracts[plan["revision"]]["function_candidates"]))
        self.assertTrue(all(state.fact(goal) for goal in self.registry.goal_ports[case["workflow"]]))

    def test_cli_resolver_flag_keeps_legacy_default_registry(self):
        completed = subprocess.run([sys.executable, "-m", "gateway_pilot.workflow", "--fixture", "GLM-04-0",
                                    "--request", "Check WAN", "--route", "resolver", "--trace"],
                                   cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=30)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["route"], "resolver")
        self.assertEqual(result["terminal"]["diagnosis"], "no_fault_observed")
        self.assertTrue(result["graph"]["contract_0"])


if __name__ == "__main__":
    unittest.main()
