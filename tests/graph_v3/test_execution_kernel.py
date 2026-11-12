"""Shared execution kernel is used by Resolver and GoS diagnostic routes."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.execution_kernel import execute_ready_once
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState


class ExecutionKernelTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(
            c for c in read_json(ROOT / "data/cases.json")
            if c["template"] == "wan_healthy"
        ))
        self.state = CaseState(self.case, self.registry)
        self.plan = Compiler(self.registry).compile(
            ("wan.status", "system.resources"), self.state
        )
        self.runner = GraphRunner(self.registry, self.case, self.state)

    def test_retrieval_mode_has_pre_execution_ready_audit(self):
        self.runner.attach(self.plan)
        audit = []
        node, result = execute_ready_once(
            self.runner, self.plan,
            ("wan.status", "system.resources"),
            method="bm25", audit=audit,
        )
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0], result)
        self.assertIn(node.id, result["ready_set"])
        self.assertEqual(result["selected_ready"], node.id)
        self.assertEqual(self.runner.calls, 1)
        self.assertIsNotNone(self.state.fact(next(iter(self.registry.functions[node.function_id].outputs))))

    def test_policy_mode_orders_only_already_ready_nodes(self):
        self.runner.attach(self.plan)
        before = self.runner.ready(self.plan)
        self.assertGreaterEqual(len(before), 2)
        selected, retrieval = execute_ready_once(
            self.runner, self.plan,
            ordered_ids=("system.resources", "wan.status"),
            favored="some.not.ready.function", ready=before,
        )
        self.assertEqual(selected.function_id, "system.resources")
        self.assertIsNone(retrieval)
        self.assertEqual(self.runner.calls, 1)

    def test_favored_ready_wins_but_forbidden_nonready_never_selected(self):
        self.runner.attach(self.plan)
        selected, _ = execute_ready_once(
            self.runner, self.plan,
            ordered_ids=("system.resources", "wan.status"),
            favored="wan.status",
        )
        self.assertEqual(selected.function_id, "wan.status")
        self.assertEqual(self.runner.calls, 1)

    def test_empty_ready_set_never_executes(self):
        self.runner.attach(self.plan)
        result = execute_ready_once(self.runner, self.plan, ready=[])
        self.assertEqual(result, (None, None))
        self.assertEqual(self.runner.calls, 0)


if __name__ == "__main__":
    unittest.main()
