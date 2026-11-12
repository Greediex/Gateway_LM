"""Regression tests for all-or-nothing read-only task decomposition and selection."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.selection import ReadySelector
from gateway_pilot.graph_v3.task_decomposer import TaskDecomposer


class TaskDecomposerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base_case = next(x for x in read_json(ROOT / "data/cases.json") if x["template"] == "wan_healthy")

    def setUp(self):
        self.registry = GraphRegistry.from_v01()
        self.case = copy.deepcopy(self.base_case)

    def test_bilingual_compound_request_maps_without_fixed_workflow_id(self):
        agent = GoalAgent(self.registry, method="bm25")
        for question in ("Kiểm tra trạng thái WAN và RAM",
                         "Check WAN status and memory"):
            with self.subTest(question=question):
                result = agent.run(question, copy.deepcopy(self.case))
                self.assertEqual(result["status"], "RESOLVED")
                self.assertEqual(result["goals"], ["wan.status", "system.resources"])
                self.assertEqual(result["calls"], 2)
                self.assertEqual(result["diagnosis"], "NOT_EVALUATED")
                self.assertEqual(result["routing"]["source"], "registered_goal_aliases")

    def test_compound_unknown_clause_blocks_entire_request(self):
        for question in ("Kiểm tra trạng thái WAN và nhiệt độ modem",
                         "Check WAN status and cosmic ray detector"):
            with self.subTest(question=question):
                result = GoalAgent(self.registry, method="bm25").run(question, self.case)
                self.assertEqual(result["status"], "NEEDS_INPUT")
                self.assertEqual(result["calls"], 0)
                self.assertFalse(result["goal_facts"])
                self.assertEqual(result["reason"], "ambiguous_or_unsupported_clause")
                self.assertTrue(result["routing"]["unresolved"])

    def test_compound_write_clause_blocks_all_read_actions(self):
        for question in ("Kiểm tra trạng thái WAN và reboot router",
                         "Restart router and check RAM",
                         "Check WAN status and block internet"):
            with self.subTest(question=question):
                result = GoalAgent(self.registry, method="bm25").run(question, self.case)
                self.assertEqual((result["status"], result["calls"]), ("BLOCKED", 0))
                self.assertEqual(result["reason"], "write_intent_in_compound_request")

    def test_single_request_remains_owned_by_calibrated_router(self):
        decision = TaskDecomposer(self.registry).decompose("Kiểm tra đường WAN giúp tôi")
        self.assertEqual(decision.decision, "NOT_APPLICABLE")

    def test_unregistered_goal_alias_cannot_create_a_function(self):
        with tempfile.TemporaryDirectory() as folder:
            d = read_json(ROOT / "data/goal_aliases_v01.json")
            d["aliases"]["secret.exec"] = ["unsafe helper"]
            path = Path(folder) / "aliases.json"
            path.write_text(json.dumps(d), encoding="utf-8")
            decision = TaskDecomposer(self.registry, manifest=path).decompose(
                "WAN status and unsafe helper"
            )
            self.assertEqual(decision.decision, "NEEDS_INPUT")

    def test_duplicate_ownership_fails_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            d = read_json(ROOT / "data/goal_aliases_v01.json")
            d["aliases"]["wan.routes"].append("wan status")
            path = Path(folder) / "aliases.json"
            path.write_text(json.dumps(d), encoding="utf-8")
            with self.assertRaisesRegex(PlanError, "ambiguous_goal_alias"):
                TaskDecomposer(self.registry, manifest=path)

    def test_client_goal_still_requires_target(self):
        result = GoalAgent(self.registry, method="bm25").run(
            "Check WAN status and WiFi signal", self.case
        )
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["reason"], "client_target_required")

    def test_no_split_or_too_many_clauses(self):
        d = TaskDecomposer(self.registry)
        self.assertEqual(d.decompose("WAN status").decision, "NOT_APPLICABLE")
        self.assertEqual(d.decompose("WAN status and RAM and DNS probe and DHCP pool and CPU and WAN routes and WiFi signal").decision,
                         "NEEDS_INPUT")


class ReadySelectorTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.ready = [SimpleNamespace(id="a", function_id="wan.status"),
                      SimpleNamespace(id="b", function_id="system.resources")]

    def test_retrieval_scores_do_not_allow_unready_action(self):
        selected = ReadySelector.choose(
            self.ready, registry=self.registry,
            scores={"f:system.resources": 0.8, "f:wan.status": 0.2, "f:untrusted": 999}
        )
        self.assertEqual(selected.function_id, "system.resources")

    def test_ordered_resolver_and_nba_selection(self):
        result = ReadySelector.choose(self.ready, ordered_ids=["system.resources", "wan.status"])
        self.assertEqual(result.function_id, "system.resources")
        result = ReadySelector.choose(self.ready, ordered_ids=["system.resources", "wan.status"],
                                      favored="wan.status")
        self.assertEqual(result.function_id, "wan.status")

    def test_empty_set_and_registry_guard(self):
        self.assertIsNone(ReadySelector.choose([]))
        with self.assertRaisesRegex(PlanError, "selector_registry_required"):
            ReadySelector.choose(self.ready, scores={})


if __name__ == "__main__":
    unittest.main()
