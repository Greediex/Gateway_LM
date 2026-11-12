"""Opt-in verified ubus binding tests (mock transport only; not board tests)."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.adapters import (
    CompositeAdapter, OpenWrtUbusAdapter, PROBE_FAILED, PROBE_OK,
    UbusReadAdapter, UbusReadBinding,
)
from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.contracts import Function, Port
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry


class FakeTransport:
    def __init__(self, *, allowed=True, response=None, error=None):
        self.allowed = allowed
        self.response = response if response is not None else {"celsius": 42.5}
        self.error = error
        self.probes = []
        self.calls = []

    def probe(self, obj, method):
        self.probes.append((obj, method))
        return self.allowed

    def read(self, obj, method, args):
        self.calls.append((obj, method, args))
        if self.error:
            raise TimeoutError("device_timeout")
        return self.response


class UbusReadAdapterTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(
            row for row in read_json(ROOT / "data/cases.json") if row["template"] == "wan_healthy"
        ))
        self.case.pop("workflow", None)
        self.case.pop("world")
        self.fid = "gateway.temperature.read"
        self.port = "gateway.temperature"
        self.registry.skills["SK99"] = {
            "id": "SK99", "name": "Gateway board telemetry",
            "description": "Read a registered gateway sensor", "tags": [],
            "requires": [], "produces": [self.port], "depends_on": [],
            "completion_ports": [], "read_set": [self.port], "write_set": [],
        }
        p = Port(self.port, "gateway", {
            "type": "object",
            "properties": {"celsius": {"type": "number"}},
            "required": ["celsius"],
            "additionalProperties": False,
        }, provenance="ubus/")
        self.registry.ports[self.port] = p
        self.registry.functions[self.fid] = Function(
            self.fid, ("SK99",), {}, {self.port: p},
            "Read board sensor", "gateway", permission="system.read"
        )
        self.registry.legacy.functions[self.fid] = {
            "id": self.fid, "requires": [], "produces": [self.port],
            "risk": "READ", "scope": "gateway", "ttl_s": 30,
        }
        self.registry.rebuild()
        self.case["capabilities"].append(self.fid)
        self.binding = {self.fid: UbusReadBinding("gateway.sensor", "temperature")}

    def run_goal(self, transport):
        adapter = UbusReadAdapter(self.registry, self.binding, transport)
        self.case["adapter"] = CompositeAdapter({self.fid: adapter})
        result = GoalAgent(self.registry, method="bm25").run(
            "gateway temperature", self.case, goals=(self.port,)
        )
        return result

    def test_new_skill_and_function_can_execute_without_changing_core(self):
        transport = FakeTransport()
        result = self.run_goal(transport)
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["goal_facts"][0]["value"], {"celsius": 42.5})
        self.assertEqual(result["goal_facts"][0]["source"], "ubus/verified")
        self.assertEqual(transport.calls, [("gateway.sensor", "temperature", {})])
        self.assertEqual(result["diagnosis"], "NOT_EVALUATED")

    def test_missing_method_or_unavailable_board_fails_closed(self):
        transport = FakeTransport(allowed=False)
        result = self.run_goal(transport)
        self.assertEqual(result["calls"], 0)
        self.assertNotEqual(result["status"], "RESOLVED")
        self.assertEqual(transport.calls, [])

    def test_wrong_schema_and_transport_timeout_never_claims_fact(self):
        for transport in (FakeTransport(response={"celsius": "hot"}),
                          FakeTransport(error=True)):
            with self.subTest(transport=transport):
                result = self.run_goal(transport)
                self.assertNotEqual(result["status"], "RESOLVED")
                self.assertEqual(result["missing_goals"], [self.port])
                self.assertEqual(result["diagnosis"], "NOT_EVALUATED")

    def test_reject_unsafe_contract_and_untrusted_bindings(self):
        with self.assertRaises(ValueError):
            UbusReadBinding("sensor; reboot", "temperature")
        self.registry.functions[self.fid].risk = "WRITE"
        with self.assertRaisesRegex(ValueError, "registered_gateway_read"):
            UbusReadAdapter(self.registry, self.binding, FakeTransport())
        self.registry.functions[self.fid].risk = "READ"
        self.registry.ports[self.port] = Port(
            self.port, "gateway", self.registry.ports[self.port].schema,
            provenance="synthetic_replay/"
        )
        self.registry.functions[self.fid].outputs[self.port] = self.registry.ports[self.port]
        with self.assertRaisesRegex(ValueError, "provenance"):
            UbusReadAdapter(self.registry, self.binding, FakeTransport())

    def test_old_openwrt_placeholder_still_fails_probe(self):
        stub = OpenWrtUbusAdapter()
        self.assertEqual(stub.probe()["wan.status"], PROBE_FAILED)
        self.assertNotIn(PROBE_OK, stub.probe().values())


if __name__ == "__main__":
    unittest.main()
