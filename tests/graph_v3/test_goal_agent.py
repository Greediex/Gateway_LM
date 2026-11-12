"""Integration tests for the goal-driven bounded graph path."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.adapters import CompositeAdapter, ReplayAdapter
from gateway_pilot.core import PlanError, ROOT, read_json
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry


class GoalAgentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = read_json(ROOT / "data/cases.json")

    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(x for x in self.data if x["template"] == "wan_healthy"))

    def agent(self, **kwargs):
        return GoalAgent(self.registry, method="bm25", **kwargs)

    def test_multi_goal_execution_without_workflow_id(self):
        self.case.pop("workflow")
        result = self.agent().run("WAN and RAM health", self.case,
                                  goals=("wan.status", "system.resources"))
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["diagnosis"], "NOT_EVALUATED")
        self.assertEqual(result["missing_goals"], [])
        self.assertEqual(result["calls"], 2)
        self.assertEqual({x["port"] for x in result["goal_facts"]},
                         {"wan.status", "system.resources"})
        self.assertTrue(all(row["selected_ready"] in row["ready_set"]
                            for row in result["ready_trace"]))
        self.assertTrue(result["plans"])

    def test_dependency_closure_from_typed_goal(self):
        self.case.pop("workflow")
        result = self.agent().run("Measure WAN external path", self.case,
                                  goals=("wan.probe",))
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["missing_goals"], [])
        self.assertIn("wan.probe", {x["port"] for x in result["goal_facts"]})
        self.assertGreater(result["calls"], 1)

    def test_unknown_goal_never_executes(self):
        with self.assertRaisesRegex(PlanError, "unknown_or_empty_goal_ports"):
            self.agent().run("arbitrary shell command", self.case,
                             goals=("shell.exec",))
        with self.assertRaisesRegex(PlanError, "unknown_or_empty_goal_ports"):
            self.agent().run("nothing", self.case, goals=())

    def test_client_goal_requires_specific_target(self):
        result = self.agent().run("check client wifi", self.case,
                                  goals=("wifi.station",))
        self.assertEqual((result["status"], result["calls"]),
                         ("NEEDS_INPUT", 0))
        self.assertEqual(result["reason"], "client_target_required")

    def test_no_observation_source_is_inconclusive(self):
        self.case.pop("world")
        result = self.agent().run("check WAN", self.case, goals=("wan.status",))
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["reason"], "observation_source_not_configured")
        self.assertEqual(result["calls"], 0)

    def test_insufficient_budget_never_claims_all_goals_verified(self):
        result = self.agent(max_calls=1).run(
            "WAN and memory", self.case, goals=("wan.status", "system.resources")
        )
        self.assertEqual(result["calls"], 1)
        self.assertNotEqual(result["status"], "RESOLVED")
        self.assertEqual(len(result["goal_facts"]), 1)
        self.assertEqual(len(result["missing_goals"]), 1)

    def test_missing_capability_does_not_fall_back_to_world(self):
        self.case["capabilities"] = ["dns.apply"]  # WRITE only, not an allowed producer.
        result = self.agent().run("check WAN", self.case, goals=("wan.status",))
        self.assertEqual(result["calls"], 0)
        self.assertNotEqual(result["status"], "RESOLVED")
        self.assertFalse(result["goal_facts"])

    def test_unassigned_backend_not_substituted_with_fixture(self):
        backend = ReplayAdapter(self.registry, ["system.resources"])
        self.case["adapter"] = CompositeAdapter({"system.resources": backend})
        result = self.agent().run("Check WAN", self.case, goals=("wan.status",))
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["missing_goals"], ["wan.status"])
        self.assertNotEqual(result["status"], "RESOLVED")

    def test_explicit_goals_are_deduplicated(self):
        result = self.agent().run("WAN status", self.case,
                                  goals=("wan.status", "wan.status"))
        self.assertEqual(result["goals"], ["wan.status"])
        self.assertEqual(result["calls"], 1)

    def test_invalid_budget_rejected(self):
        for params in ({"max_calls": 0}, {"max_rounds": 0}, {"retrieval_k": -1},
                       {"max_repairs": -1}):
            with self.subTest(params=params), self.assertRaises(ValueError):
                self.agent(**params)


if __name__ == "__main__":
    unittest.main()
