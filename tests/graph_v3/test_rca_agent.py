"""Evidence-driven RCA: bounded adaptive probes, Claim proof and fail-closed cases."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.adapters import CompositeAdapter, ReplayAdapter
from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.rca_agent import RCAAgent


class RCAPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples = read_json(ROOT / "data/cases.json")

    def setUp(self):
        self.registry = GraphRegistry.from_v01()
        self.agent = RCAAgent(self.registry, method="bm25",
                              max_calls=8, max_rounds=10)

    def case(self, template):
        return copy.deepcopy(next(x for x in self.samples if x["template"] == template))

    def test_wan_down_claim_stops_after_first_verified_measurement(self):
        result = self.agent.run("Internet WAN is down", self.case("wan_down"),
                                workflow="WF-018")
        self.assertEqual(result["status"], "VERIFIED_FAULT")
        self.assertEqual(result["diagnosis"], "wan_link_down")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["steps"][0]["goal"], "wan.status")
        self.assertTrue(result["evidence_ids"])
        self.assertTrue(all(c["evidence_ids"] for c in result["claim_results"]
                            if c["diagnosis"] == "wan_link_down" and c["truth"] == "TRUE"))

    def test_wan_route_fault_is_measured_in_dependency_order(self):
        result = self.agent.run("WAN route not working", self.case("wan_route"),
                                workflow="WF-018")
        self.assertEqual(result["status"], "VERIFIED_FAULT")
        self.assertEqual(result["diagnosis"], "wan_no_route")
        self.assertEqual(result["calls"], 2)
        # The planner may pick wan.probe and *automatically* acquire
        # wan.routes as a typed dependency. The evidence/Claim must be right,
        # not an artificially fixed high-level goal ordering.
        self.assertEqual(result["steps"][0]["goal"], "wan.status")
        self.assertTrue(any(c["diagnosis"] == "wan_no_route" and c["truth"] == "TRUE"
                            for c in result["claim_results"]))
        self.assertTrue(result["evidence_ids"])

    def test_healthy_requires_faults_to_be_ruled_out_by_all_observations(self):
        result = self.agent.run("WAN health", self.case("wan_healthy"),
                                workflow="WF-018")
        self.assertEqual(result["status"], "HEALTHY_OBSERVED")
        self.assertEqual(result["diagnosis"], "no_fault_observed")
        self.assertEqual(result["calls"], 3)
        self.assertEqual(result["steps"][0]["goal"], "wan.status")
        self.assertTrue(any(c["diagnosis"] == "no_fault_observed" and c["truth"] == "TRUE"
                            for c in result["claim_results"]))
        self.assertTrue(result["evidence_ids"])

    def test_missing_measurement_never_hallucinates_root_cause(self):
        case = self.case("wan_healthy")
        case["capabilities"] = ["wan.status"]
        result = self.agent.run("WAN check", case, workflow="WF-018")
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIsNone(result["diagnosis"])
        self.assertFalse(result["evidence_ids"])
        self.assertLessEqual(result["calls"], 1)

    def test_no_trusted_observation_source_is_inconclusive(self):
        case = self.case("wan_down")
        case.pop("world")
        result = self.agent.run("WAN down", case, workflow="WF-018")
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["calls"], 0)
        self.assertEqual(result["reason"], "observation_source_not_configured")

    def test_adapter_without_wan_assignment_cannot_use_fixture_world(self):
        case = self.case("wan_down")
        backend = ReplayAdapter(self.registry, ["system.resources"])
        case["adapter"] = CompositeAdapter({"system.resources": backend})
        result = self.agent.run("WAN down", case, workflow="WF-018")
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIsNone(result["diagnosis"])
        self.assertEqual(result["calls"], 0)

    def test_no_permission_cannot_execute_a_probe(self):
        case = self.case("wan_down")
        case["permissions"] = ["system.read"]
        result = self.agent.run("WAN", case, workflow="WF-018")
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertEqual(result["calls"], 0)

    def test_catalog_only_and_unsupported_workflows_are_rejected(self):
        for wf in ("WF-001", "WF-WRITE", "not_a_workflow"):
            with self.subTest(wf=wf), self.assertRaisesRegex(
                PlanError, "rca_requires_supported_diagnostic_workflow"
            ):
                self.agent.run("test", self.case("wan_down"), workflow=wf)

    def test_client_target_missing_requires_user(self):
        result = self.agent.run("Client internet", self.case("wan_healthy"),
                                workflow="WF-INTERNET")
        self.assertEqual(result["status"], "NEEDS_INPUT")
        self.assertEqual(result["calls"], 0)

    def test_budget_exhaustion_is_never_reported_as_verified(self):
        agent = RCAAgent(self.registry, method="bm25", max_calls=1)
        result = agent.run("WAN", self.case("wan_healthy"), workflow="WF-018")
        self.assertEqual(result["status"], "INCONCLUSIVE")
        self.assertIsNone(result["diagnosis"])
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["reason"], "rca_call_budget_exhausted")


if __name__ == "__main__":
    unittest.main()
