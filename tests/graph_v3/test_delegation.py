"""Privacy, approval, budget and untrusted-response gates for Cloud delegation."""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.delegation import (
    CloudHypothesisAdapter, EdgeCloudPolicy, minimal_cloud_context,
)
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState


class MockCloud:
    def __init__(self, result=None, fail=False):
        self.result = result if result is not None else {"hypothesis": "Check uplink"}
        self.fail = fail
        self.calls = []

    def analyze(self, payload):
        self.calls.append(payload)
        if self.fail:
            raise TimeoutError("backend_not_available")
        return self.result


class CloudPolicyTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(
            c for c in read_json(ROOT / "data/cases.json")
            if c["template"] == "wan_healthy"
        ))
        self.state = CaseState(self.case, self.registry)
        plan = Compiler(self.registry).compile(
            ("wan.status", "system.resources"), self.state
        )
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.run(plan)
        self.assertIsNotNone(self.state.fact("wan.status"))

    def test_default_edge_first_and_cloud_disabled(self):
        policy = EdgeCloudPolicy()
        d = policy.decide("CROSS_LAYER_RCA", edge_can_resolve=True,
                          consent=True, privacy="AGGREGATED_ONLY",
                          estimated_cost_usd=0.01, backend_present=True)
        self.assertEqual(d.route, "EDGE")
        d = policy.decide("CROSS_LAYER_RCA", edge_can_resolve=False,
                          consent=True, privacy="AGGREGATED_ONLY",
                          estimated_cost_usd=0.01, backend_present=True)
        self.assertEqual(d.route, "BLOCKED")
        self.assertEqual(d.reason, "cloud_disabled")

    def test_consent_privacy_cost_and_unknown_purpose_fail_closed(self):
        policy = EdgeCloudPolicy(enabled=True, max_cost_usd=0.02)
        flags = dict(edge_can_resolve=False, consent=True,
                     privacy="AGGREGATED_ONLY", estimated_cost_usd=0.01,
                     backend_present=True)
        self.assertEqual(policy.decide("REBOOT", **flags).route, "BLOCKED")
        self.assertEqual(policy.decide("CROSS_LAYER_RCA", **{
            **flags, "privacy": "RAW_LOGS",
        }).reason, "privacy_not_aggregated")
        self.assertEqual(policy.decide("CROSS_LAYER_RCA", **{
            **flags, "consent": False,
        }).route, "NEEDS_APPROVAL")
        self.assertEqual(policy.decide("CROSS_LAYER_RCA", **{
            **flags, "backend_present": False,
        }).reason, "cloud_backend_not_configured")
        self.assertEqual(policy.decide("CROSS_LAYER_RCA", **{
            **flags, "estimated_cost_usd": 0.04,
        }).reason, "cloud_budget_exceeded")

    def test_redacted_context_has_only_verified_numeric_gateway_fields(self):
        context = minimal_cloud_context(self.registry, self.state)
        serialized = str(context)
        self.assertIn("wan.status", serialized)
        self.assertIn("system.resources", serialized)
        self.assertNotIn("client.identity", serialized)
        self.assertNotIn("client_id", serialized)
        self.assertNotIn("evidence_id", serialized)
        self.assertNotIn("system.logs", serialized)
        self.assertTrue(all(
            isinstance(value, (bool, int, float))
            for row in context["telemetry"] for value in row["metrics"].values()
        ))

    def test_cloud_hypothesis_never_claims_verified_diagnosis(self):
        backend = MockCloud()
        policy = EdgeCloudPolicy(enabled=True, max_requests=1, max_cost_usd=0.02)
        helper = CloudHypothesisAdapter(backend, policy)
        outcome = helper.request(
            self.registry, self.state, purpose="CROSS_LAYER_RCA",
            consent=True, edge_can_resolve=False, estimated_cost_usd=0.01,
        )
        self.assertEqual(outcome["status"], "HYPOTHESIS_UNVERIFIED")
        self.assertNotIn("diagnosis", outcome)
        self.assertEqual(policy.calls, 1)
        self.assertEqual(backend.calls[0]["requested_output"], "unverified_hypothesis_only")
        self.assertNotIn("request", backend.calls[0])
        second = helper.request(
            self.registry, self.state, purpose="CROSS_LAYER_RCA",
            consent=True, edge_can_resolve=False, estimated_cost_usd=0.01,
        )
        self.assertEqual(second["reason"], "cloud_budget_exceeded")
        self.assertEqual(len(backend.calls), 1)

    def test_invalid_remote_result_or_timeout_is_not_evidence(self):
        for backend in (MockCloud({"command": "reboot"}),
                        MockCloud(fail=True)):
            with self.subTest(backend=backend):
                helper = CloudHypothesisAdapter(
                    backend, EdgeCloudPolicy(enabled=True)
                )
                output = helper.request(
                    self.registry, self.state, purpose="FLEET_REFERENCE",
                    consent=True, edge_can_resolve=False,
                )
                self.assertIn(output["status"], {"ERROR", "REJECTED"})
                self.assertNotIn("diagnosis", output)
                self.assertNotIn("evidence_ids", output)

    def test_no_shareable_facts_prevents_cloud_request_and_charge(self):
        state = CaseState(self.case, self.registry)
        policy = EdgeCloudPolicy(enabled=True)
        backend = MockCloud()
        result = CloudHypothesisAdapter(backend, policy).request(
            self.registry, state, purpose="LONG_CONTEXT",
            consent=True, edge_can_resolve=False,
        )
        self.assertEqual(result["reason"], "no_shareable_evidence")
        self.assertEqual(policy.calls, 0)
        self.assertEqual(backend.calls, [])

    def test_invalid_policy_and_reservation_rejected(self):
        with self.assertRaises(ValueError):
            EdgeCloudPolicy(max_cost_usd=-1)
        policy = EdgeCloudPolicy(enabled=True)
        with self.assertRaises(PlanError):
            policy.reserve(policy.decide(
                "CROSS_LAYER_RCA", edge_can_resolve=True,
                consent=True, privacy="AGGREGATED_ONLY",
                estimated_cost_usd=0.01, backend_present=True
            ))


if __name__ == "__main__":
    unittest.main()
