"""Exercise the real Gateway diagnostic code through the web adapter."""

import unittest
from importlib.util import find_spec
from unittest.mock import Mock, patch

from web_gateway.server import analyze


class GatewayWebTests(unittest.TestCase):
    @unittest.skipUnless(find_spec("langgraph"), "Install requirements-react.txt to test LangGraph")
    def test_react_executes_gos_and_validates_plans_with_skilldag(self):
        request = {"message": "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?",
                   "fixture_id": "WEB-WAN-TIMEOUT-1", "method": "gos", "policy": "react"}
        result = analyze(request)
        self.assertEqual((result["decision_source"], result["diagnosis"], result["calls"]),
                         ("langgraph_react", "client_path_loss", 7))
        self.assertIsNone(result["skill_context"])
        self.assertTrue(all(row["upstream_kernel_used"] for row in result["retrievals"]))
        self.assertTrue(all(any(row["operator"] == "SKILLDAG_CHECK" for row in plan["audit"])
                            for plan in result["plans"]))
        trace = result["react"]["steps"]
        self.assertEqual([row["node"] for row in trace], ["call_model", "tools"] * 5 + ["call_model"])
        self.assertEqual(trace[-2]["stage"], "client.probe")
        conflict = {"expanded": ["SK01", "SK02"], "prerequisites": [], "conflicts": [["SK01", "SK02"]]}
        with patch("gateway_pilot.graph_v3.react_runtime.check_skills", return_value=conflict):
            rejected = analyze(request)
        self.assertEqual(rejected["calls"], 0)
        self.assertEqual(rejected["stages"][0]["error"], "skilldag_conflict")

    def test_same_fixture_exposes_a_real_policy_difference(self):
        request = {"message": "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?",
                   "fixture_id": "WEB-WAN-TIMEOUT-1", "method": "bm25"}
        dynamic = analyze(request)
        core = analyze({**request, "policy": "core"})
        self.assertEqual((core["diagnosis"], core["calls"]), ("insufficient_evidence", 6))
        self.assertEqual((dynamic["diagnosis"], dynamic["calls"]), ("client_path_loss", 7))
        self.assertEqual(dynamic["case_status"], "PARTIAL")
        self.assertEqual(dynamic["policy_steps"][-1]["selected"], "client.probe")
        self.assertEqual(dynamic["timeline"][-2]["status"], "TIMEOUT")
        self.assertEqual(dynamic["timeline"][-1]["evidence_id"], dynamic["evidence_ids"][0])
        self.assertTrue(any(len(plan["goals"]) > 1 for plan in dynamic["plans"]))

    @unittest.skipUnless(find_spec("langgraph"), "Install requirements-react.txt to test LangGraph")
    def test_model_can_route_and_change_next_stage_but_cannot_cite_unknown_evidence(self):
        payload = {"message": "Laptop An vào được IP nhưng không phân giải được tên miền.",
                   "fixture_id": "WEB-CLIENT-DNS-1", "policy": "react", "with_llm": True}
        advisor = Mock(model="local-test-model")
        advisor.understand_request.return_value = "WF-INTERNET"

        def recommend(_request, facts, candidates, _failed_check):
            self.assertEqual(set(candidates), {"dns.probe", "client.probe"})
            return {"next_stage": "dns.probe", "hypothesis": "Kiểm tra phân giải tên miền từ router.",
                    "evidence_ids": [facts["wan.probe"]["id"]]}

        advisor.reason_next.side_effect = recommend
        with patch("gateway_pilot.workflow_advisor.OllamaProbeAdvisor", return_value=advisor):
            accepted = analyze(payload)
            advisor.reason_next.side_effect = None
            advisor.reason_next.return_value = {"next_stage": "dns.probe", "hypothesis": "Đo DNS.",
                                                "evidence_ids": ["unobserved"]}
            rejected = analyze(payload)
            advisor.understand_request.return_value = "WF-024"
            wrong_intent = analyze(payload)
        self.assertTrue(accepted["intake"]["accepted"])
        self.assertEqual(accepted["advice"][0]["selected"], "dns.probe")
        self.assertTrue(accepted["advice"][0]["accepted"])
        self.assertEqual(accepted["timeline"][6]["function_id"], "dns.config")
        self.assertFalse(rejected["advice"][0]["accepted"])
        self.assertEqual(rejected["timeline"][6]["function_id"], "client.probe")
        self.assertEqual(accepted["diagnosis"], rejected["diagnosis"])
        self.assertFalse(wrong_intent["intake"]["accepted"])
        self.assertEqual(wrong_intent["calls"], 0)

    def test_web_request_cannot_write_configuration(self):
        result = analyze({"message": "Đổi DNS router sang 8.8.8.8.", "with_guide": False})
        self.assertEqual((result["case_status"], result["diagnosis"]), ("BLOCKED", "unsafe_change_denied"))
        self.assertEqual(result["calls"], 0)
        self.assertFalse(result["plans"])
