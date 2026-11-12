"""Regression and negative-path tests for composable runtime stage boundaries."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.adapters import Adapter, CompositeAdapter, PROBE_OK, ReplayAdapter
from gateway_pilot.core import PlanError, ROOT, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler, NodeState
from gateway_pilot.graph_v3.planning_stage import FunctionPlanner
from gateway_pilot.graph_v3.routing import FunctionRouter
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState


class BadObservationAdapter(Adapter):
    def probe(self):
        return {"wan.status": PROBE_OK}

    def call(self, function_id, arguments, state, case):
        return "not_a_typed_observation"


class RuntimeStageTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(
            row for row in read_json(ROOT / "data/cases.json") if row["template"] == "wan_healthy"
        ))
        self.state = CaseState(self.case, self.registry)

    def test_router_rejects_unknown_function_before_compilation(self):
        def untrusted(_registry, _state, _request, **_kwargs):
            return {"function_candidates": ["unregistered.command"],
                    "decision": "READY_TO_COMPILE", "skill_context": {}}
        with self.assertRaisesRegex(PlanError, "router_invalid_candidates"):
            FunctionRouter(untrusted).route(
                self.registry, self.state, "check WAN", goals=("wan.status",), method="bm25"
            )

    def test_router_rejects_candidate_for_blocked_decision(self):
        fid = "wan.status"
        def forbidden(_registry, _state, _request, **_kwargs):
            return {"function_candidates": [fid], "decision": "BLOCKED",
                    "skill_context": {fid: self.registry.functions[fid].skills[0]}}
        with self.assertRaisesRegex(PlanError, "router_blocked_with_candidates"):
            FunctionRouter(forbidden).route(
                self.registry, self.state, "change WAN", goals=("wan.status",)
            )

    def test_router_rejects_mismatched_skill_membership(self):
        fid = "wan.status"
        def invalid(_registry, _state, _request, **_kwargs):
            return {"function_candidates": [fid], "decision": "READY_TO_COMPILE",
                    "skill_context": {fid: "not_a_registered_skill"}}
        with self.assertRaisesRegex(PlanError, "router_unknown_skill_context"):
            FunctionRouter(invalid).route(
                self.registry, self.state, "check WAN", goals=("wan.status",)
            )

    def test_planner_can_only_compile_explicitly_selected_functions(self):
        fid = "wan.status"
        contract = {
            "decision": "READY_TO_COMPILE",
            "function_candidates": [fid],
            "skill_context": {fid: self.registry.functions[fid].skills[0]},
            "plan_revision": 1,
        }
        plan = FunctionPlanner().compile(self.registry, self.state, contract)
        self.assertEqual(set(plan.nodes), {fid})
        self.assertEqual(plan.revision, 1)
        with self.assertRaisesRegex(PlanError, "planner_unknown_candidates"):
            FunctionPlanner().compile(self.registry, self.state,
                                      {**contract, "function_candidates": ["bad"]})

    def test_composite_adapter_runs_via_typed_executor_and_evidence_verifier(self):
        backend = ReplayAdapter(self.registry, ["wan.status"])
        self.case["adapter"] = CompositeAdapter({"wan.status": backend})
        plan = Compiler(self.registry).compile(["wan.status"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state, max_repairs=0)
        result = runner.run(plan)
        self.assertEqual(result.nodes["wan.status"].state, NodeState.SUCCEEDED)
        self.assertIsNotNone(self.state.fact("wan.status"))
        self.assertEqual(runner.calls, 1)
        self.assertEqual(runner.contract_b[0]["tool_status"], "EXIT_OK")
        self.assertEqual(runner.contract_b[0]["goal_claim"], "NOT_EVALUATED")

    def test_unassigned_adapter_function_fails_closed(self):
        backend = ReplayAdapter(self.registry, ["wan.routes"])
        self.case["adapter"] = CompositeAdapter({"wan.routes": backend})
        plan = Compiler(self.registry).compile(["wan.status"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state, max_repairs=0)
        result = runner.run(plan)
        self.assertEqual(result.nodes["wan.status"].state, NodeState.FAILED)
        self.assertEqual(runner.calls, 1)
        self.assertIsNone(self.state.fact("wan.status"))
        self.assertEqual(runner.contract_b[0]["tool_status"], "EXIT_ERROR")

    def test_malformed_adapter_output_is_not_evidence(self):
        self.case["adapter"] = CompositeAdapter({"wan.status": BadObservationAdapter()})
        plan = Compiler(self.registry).compile(["wan.status"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state, max_repairs=0)
        result = runner.run(plan)
        self.assertEqual(result.nodes["wan.status"].state, NodeState.FAILED)
        self.assertIsNone(self.state.fact("wan.status"))
        self.assertEqual(runner.calls, 1)

    def test_preferred_unready_node_is_not_silently_substituted(self):
        plan = Compiler(self.registry).compile(["wan.status"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state, max_repairs=0)
        with self.assertRaisesRegex(PlanError, "preferred_node_not_ready"):
            runner.step(plan, preferred="shell.exec")
        self.assertEqual(runner.calls, 0)
        self.assertEqual(self.state.evidence, [])



if __name__ == "__main__":
    unittest.main()
