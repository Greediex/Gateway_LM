"""Shared typed task entrypoint: measurement vs RCA, no false claims."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.task_runtime import TaskRequest, TaskRuntime
from gateway_pilot.graph_v3.graphs import GraphRegistry


class TaskRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = read_json(ROOT / "data/cases.json")

    def setUp(self):
        self.registry = GraphRegistry.from_v01()
        self.runtime = TaskRuntime(self.registry, method="bm25")

    def fixture(self, template):
        return copy.deepcopy(next(x for x in self.cases if x["template"] == template))

    def test_one_state_machine_two_read_only_policies(self):
        case = self.fixture("wan_down")
        goals = self.runtime.run(
            TaskRequest("Read WAN link", goals=("wan.status",)), case
        )
        self.assertEqual(goals["mode"], "MEASURE")
        self.assertEqual(goals["status"], "RESOLVED")
        self.assertIsNone(goals["diagnosis"])
        self.assertEqual(goals["result"]["diagnosis"], "NOT_EVALUATED")
        rca = self.runtime.run(
            TaskRequest("Why is WAN down?", mode="DIAGNOSE",
                        workflow="WF-018"), case
        )
        self.assertEqual(rca["mode"], "DIAGNOSE")
        self.assertEqual(rca["status"], "VERIFIED_FAULT")
        self.assertEqual(rca["diagnosis"], "wan_link_down")
        self.assertEqual(
            [row["state"] for row in rca["trace"]],
            ["RECEIVED", "ROUTED", "EXECUTED", "VERIFIED", "TERMINAL"],
        )

    def test_auto_uses_only_typed_registered_constraints(self):
        result = self.runtime.run(
            TaskRequest("WAN status", goals=("wan.status",)),
            self.fixture("wan_healthy")
        )
        self.assertEqual(result["mode"], "MEASURE")
        self.assertEqual(result["status"], "RESOLVED")
        result = self.runtime.run(
            TaskRequest("WAN problem", workflow="WF-018"),
            self.fixture("wan_route")
        )
        self.assertEqual(result["mode"], "DIAGNOSE")
        self.assertEqual(result["diagnosis"], "wan_no_route")

    def test_conflicting_contract_or_unsafe_diagnosis_rejected(self):
        case = self.fixture("wan_healthy")
        for task in (
            TaskRequest("WAN", goals=("wan.status",), workflow="WF-018"),
            TaskRequest("WAN", mode="MEASURE", workflow="WF-018"),
            TaskRequest("WAN", mode="DIAGNOSE", goals=("wan.status",),
                        workflow="WF-018"),
        ):
            with self.subTest(task=task), self.assertRaises(PlanError):
                self.runtime.run(task, case)
        for workflow in ("WF-WRITE", "WF-001", "unknown"):
            with self.subTest(workflow=workflow), self.assertRaises(PlanError):
                self.runtime.run(TaskRequest("reboot", mode="DIAGNOSE",
                                             workflow=workflow), case)

    def test_unregistered_measurement_never_runs_function(self):
        result = self.runtime.run(
            TaskRequest("What is that?", goals=None),
            self.fixture("wan_healthy")
        )
        self.assertIn(result["status"], {"NEEDS_INPUT", "BLOCKED", "RESOLVED"})
        if result["status"] == "RESOLVED":
            self.assertEqual(result["result"]["diagnosis"], "NOT_EVALUATED")
        with self.assertRaises(PlanError):
            self.runtime.run(
                TaskRequest("run arbitrary python", goals=("shell.exec",)),
                self.fixture("wan_healthy")
            )

    def test_write_request_never_executes_in_any_read_only_mode(self):
        for task in (
            TaskRequest("reboot router", goals=("wan.status",)),
            TaskRequest("restart router and check WAN", workflow="WF-018"),
        ):
            with self.subTest(task=task):
                result = self.runtime.run(task, self.fixture("wan_healthy"))
                self.assertEqual(result["status"], "BLOCKED")
                self.assertEqual(result["result"]["calls"], 0)

    def test_missing_real_observation_remains_inconclusive(self):
        case = self.fixture("wan_healthy")
        case.pop("world", None)
        task = TaskRequest("WAN check", mode="DIAGNOSE", workflow="WF-018")
        result = self.runtime.run(task, case)
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIsNone(result["diagnosis"])


if __name__ == "__main__":
    unittest.main()
