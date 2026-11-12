"""Structured ToolResult conformance and fail-closed adapter integration."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.adapters import Adapter, PROBE_OK, ToolResult
from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.contracts import Function, Port
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler, NodeState
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState


class StructuredAdapter(Adapter):
    def __init__(self, function_id, reply):
        self.function_id, self.reply = function_id, reply
        self.called = 0

    def probe(self):
        return {self.function_id: PROBE_OK}

    def call(self, function_id, arguments, state, case):
        self._check(function_id, arguments)
        self.called += 1
        return self.reply


class ToolResultTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(
            x for x in read_json(ROOT / "data/cases.json") if x["template"] == "wan_healthy"
        ))

    def _multi(self):
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}},
                  "required": ["ok"], "additionalProperties": False}
        x = Port("x", "gateway", schema)
        y = Port("y", "gateway", schema)
        self.registry.ports.update(x=x, y=y)
        self.registry.functions["shared"] = Function(
            "shared", ("SK04",), {}, {"x": x, "y": y}, "Read two outputs", "gateway"
        )
        self.registry.legacy.functions["shared"] = {
            "id": "shared", "produces": ["x", "y"], "requires": [],
            "risk": "READ", "scope": "gateway", "ttl_s": 30,
        }
        self.registry.rebuild()
        self.case["capabilities"].append("shared")

    @staticmethod
    def _observation(port, *, ident, status="OK", source="synthetic_replay/v3",
                     fid="shared", value=None):
        return {
            "id": ident, "function_id": fid, "port": port,
            "scope": "gateway", "target": "gateway_01",
            "source": source, "status": status, "value": value or {"ok": True},
            "age_s": 0, "ttl_s": 30,
        }

    def _execute(self, goals, adapter):
        self.case.pop("world", None)  # Real Adapter must not need replay world.
        self.case["adapter"] = adapter
        state = CaseState(self.case, self.registry)
        plan = Compiler(self.registry).compile(goals, state)
        runner = GraphRunner(self.registry, self.case, state, max_repairs=0)
        return runner.run(plan), state, runner

    def test_structured_multi_output_verified_without_mutating_adapter_state(self):
        self._multi()
        a = StructuredAdapter("shared", ToolResult((
            self._observation("x", ident="x-1", value={"ok": True}),
            self._observation("y", ident="y-1", value={"ok": False}),
        )))
        plan, state, runner = self._execute(["x", "y"], a)
        self.assertEqual(plan.nodes["shared"].state, NodeState.SUCCEEDED)
        self.assertEqual(a.called, 1)
        self.assertEqual(runner.calls, 1)
        self.assertEqual(len(state.evidence), 2)
        self.assertEqual(state.fact("x")["value"], {"ok": True})
        self.assertEqual(state.fact("y")["value"], {"ok": False})
        self.assertEqual(runner.contract_b[0]["tool_status"], "EXIT_OK")
        self.assertEqual(runner.contract_b[0]["goal_claim"], "NOT_EVALUATED")

    def test_missing_or_extra_output_fails_closed(self):
        self._multi()
        for rows in ((self._observation("x", ident="x-1"),),
                     (self._observation("x", ident="x-1"),
                      self._observation("unexpected", ident="z-1"))):
            with self.subTest(rows=len(rows)):
                adapter = StructuredAdapter("shared", ToolResult(rows))
                plan, state, runner = self._execute(["x", "y"], adapter)
                self.assertEqual(plan.nodes["shared"].state, NodeState.FAILED)
                self.assertEqual(len(state.evidence), 0)
                self.assertIsNone(state.fact("x"))
                self.assertEqual(runner.contract_b[0]["tool_status"], "EXIT_ERROR")

    def test_duplicate_id_or_foreign_function_rejected_without_evidence(self):
        self._multi()
        cases = (
            (self._observation("x", ident="collision"),
             self._observation("y", ident="collision")),
            (self._observation("x", ident="x-1", fid="forged"),
             self._observation("y", ident="y-1")),
        )
        for rows in cases:
            with self.subTest(rows=rows):
                plan, state, runner = self._execute(
                    ["x", "y"], StructuredAdapter("shared", ToolResult(rows))
                )
                self.assertEqual(plan.nodes["shared"].state, NodeState.FAILED)
                self.assertEqual(len(state.evidence), 0)

    def test_error_result_cannot_claim_success(self):
        with self.assertRaises(ValueError):
            ToolResult((), is_error=True)
        with self.assertRaises(ValueError):
            ToolResult((self._observation("x", ident="1"),), is_error=True, error_code="FAIL")
        with self.assertRaises(ValueError):
            ToolResult((), is_error=False)
        adapter = StructuredAdapter("wan.status", ToolResult(is_error=True, error_code="DISCONNECTED"))
        plan, state, runner = self._execute(["wan.status"], adapter)
        self.assertEqual(plan.nodes["wan.status"].state, NodeState.FAILED)
        self.assertIsNone(state.fact("wan.status"))
        self.assertEqual(runner.calls, 1)

    def test_injected_clock_metadata_not_trusted(self):
        adapter = StructuredAdapter("wan.status", ToolResult((
            {**self._observation("wan.status", ident="external-1", fid="wan.status",
                                  value={"link_up": True}),
             "_received_at": -1000000, "boot_id": "foreign-boot",
             "config_version": "foreign-version"},
        )))
        plan, state, _ = self._execute(["wan.status"], adapter)
        self.assertEqual(plan.nodes["wan.status"].state, NodeState.SUCCEEDED)
        e = state.fact("wan.status")
        self.assertEqual(e["boot_id"], state.boot_id)
        self.assertEqual(e["config_version"], state.config_version)
        self.assertNotEqual(e["_received_at"], -1000000)

    def test_untrusted_source_is_not_accepted_as_fact(self):
        adapter = StructuredAdapter("wan.status", ToolResult((
            self._observation("wan.status", ident="untrusted-1", fid="wan.status",
                              value={"link_up": True}, source="untrusted/log"),
        )))
        plan, state, _ = self._execute(["wan.status"], adapter)
        self.assertEqual(plan.nodes["wan.status"].state, NodeState.INCONCLUSIVE)
        self.assertIsNone(state.fact("wan.status"))

    def test_multi_output_dict_not_implicitly_accepted(self):
        self._multi()
        adapter = StructuredAdapter("shared", self._observation("x", ident="x-1"))
        plan, state, _ = self._execute(["x", "y"], adapter)
        self.assertEqual(plan.nodes["shared"].state, NodeState.FAILED)
        self.assertEqual(len(state.evidence), 0)


if __name__ == "__main__":
    unittest.main()
