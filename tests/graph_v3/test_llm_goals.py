"""Fail-closed tests for opt-in local LLM goal nomination."""
from __future__ import annotations

import copy
import json
import unittest
from unittest.mock import patch

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.llm_goals import BoundedGoalProposer


class FakeModel:
    local_only = True

    def __init__(self, output):
        self.output = output
        self.calls = []

    def propose_goals(self, request, catalog):
        self.calls.append((request, catalog))
        return self.output


def proposal(goals=("wan.status",), *, confidence=0.93,
             spans=None, needs_clarification=False):
    return {
        "goals": list(goals),
        "confidence": confidence,
        "spans": spans if spans is not None else {g: "nghen ket noi" for g in goals},
        "needs_clarification": needs_clarification,
    }


class ModelGoalTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry.from_v01()
        self.case = copy.deepcopy(next(
            row for row in read_json(ROOT / "data/cases.json")
            if row["template"] == "wan_healthy"
        ))
        self.router_patch = patch("gateway_pilot.graph_v3.goal_agent.route_turn",
                                  return_value={"turn_type": "UNRESOLVED",
                                                "action": "ASK_USER", "band": "LOW",
                                                "reason": "unknown_intent",
                                                "plan_hint": None})
        self.router_patch.start()
        self.addCleanup(self.router_patch.stop)

    def run_model(self, model, request="nghen ket noi", case=None):
        p = BoundedGoalProposer(model)
        return GoalAgent(self.registry, method="bm25", goal_proposer=p).run(
            request, self.case if case is None else case
        )

    def test_local_proposal_executes_only_registered_verified_goal(self):
        model = FakeModel(proposal())
        outcome = self.run_model(model)
        self.assertEqual(outcome["status"], "RESOLVED")
        self.assertEqual(outcome["routing"]["source"], "bounded_llm_proposal")
        self.assertEqual(outcome["goals"], ["wan.status"])
        self.assertEqual(outcome["calls"], 1)
        self.assertEqual(outcome["diagnosis"], "NOT_EVALUATED")
        self.assertEqual(model.calls[0][0], "nghen ket noi")
        self.assertTrue(all("port" in d and "description" in d
                            for d in model.calls[0][1]))

    def test_model_cannot_inject_unregistered_or_write_tool(self):
        for ids in (("shell.exec",), ("dns.apply",), ("wan.status", "shell.exec")):
            with self.subTest(ids=ids):
                model = FakeModel(proposal(ids))
                outcome = self.run_model(model)
                self.assertEqual(outcome["status"], "NEEDS_INPUT")
                self.assertEqual(outcome["calls"], 0)

    def test_unsafe_request_never_reaches_model(self):
        for request in ("restart router", "nghen ket noi and reboot", "set bandwidth"):
            with self.subTest(request=request):
                model = FakeModel(proposal())
                result = self.run_model(model, request=request)
                self.assertEqual((result["status"], result["calls"]), ("BLOCKED", 0))
                self.assertFalse(model.calls)

    def test_low_confidence_missing_spans_or_clarification_blocks(self):
        values = [
            proposal(confidence=0.6),
            proposal(spans={"wan.status": "unknown phrase"}),
            proposal(needs_clarification=True),
            proposal(spans={}),
            proposal(goals=()),
            proposal(goals=("wan.status", "wan.status")),
            {"goals": ["wan.status"], "confidence": 0.99, "spans": {}, "needs_clarification": False,
             "command": "reboot"},
        ]
        for value in values:
            with self.subTest(value=value):
                result = self.run_model(FakeModel(value))
                self.assertEqual(result["status"], "NEEDS_INPUT")
                self.assertEqual(result["calls"], 0)

    def test_malformed_and_model_error_fail_closed(self):
        for output in ("not json", json.dumps({"goals": ["wan.status"]}), list(range(3))):
            with self.subTest(output=output):
                result = self.run_model(FakeModel(output))
                self.assertEqual(result["status"], "NEEDS_INPUT")
                self.assertEqual(result["calls"], 0)
        class Failing(FakeModel):
            def propose_goals(self, request, catalog):
                raise TimeoutError("simulated model timeout")
        result = self.run_model(Failing(None))
        self.assertEqual(result["reason"], "model_unavailable")

    def test_client_proposal_without_target_does_not_execute(self):
        model = FakeModel(proposal(("wifi.station",), spans={"wifi.station": "nghen ket noi"}))
        result = self.run_model(model)
        self.assertEqual(result["reason"], "client_target_required")
        self.assertEqual(result["calls"], 0)

    def test_unprobed_model_target_cannot_expand_permissions(self):
        case = copy.deepcopy(self.case)
        case["capabilities"] = ["system.resources"]
        model = FakeModel(proposal())
        result = self.run_model(model, case=case)
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertEqual(result["calls"], 0)

    def test_reject_untrusted_cloud_model_as_planner(self):
        model = FakeModel(proposal())
        model.local_only = False
        with self.assertRaisesRegex(ValueError, "trusted_local"):
            BoundedGoalProposer(model)

    def test_bounded_multi_goal_model_proposal(self):
        model = FakeModel(proposal(
            ("wan.status", "system.resources"),
            spans={"wan.status": "nghen ket noi",
                   "system.resources": "tai nguyen"},
        ))
        result = self.run_model(model, request="nghen ket noi tai nguyen")
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["calls"], 2)
        self.assertEqual(len(result["goal_facts"]), 2)


if __name__ == "__main__":
    unittest.main()
