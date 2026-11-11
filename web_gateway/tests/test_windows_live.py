import os
import unittest
from unittest.mock import Mock, patch

from web_gateway.server import analyze


def sample(address, _source):
    rtt = [1, 2, 3, 4] if address == "192.168.4.1" else [36, 40, 44]
    return {"address": address, "replies": True, "sent": 4, "received": len(rtt),
            "loss_pct": 25 * (4 - len(rtt)), "rtt_ms": rtt}


@unittest.skipUnless(os.name == "nt", "Windows live mode requires Windows")
class LiveWindowsTests(unittest.TestCase):
    def test_live_trace_uses_current_gateway_and_never_reads_fixture(self):
        route = {"gateway": "192.168.4.1", "source_ipv4": "192.168.4.2"}
        with (patch("web_gateway.server.fixture_catalog", side_effect=AssertionError("unexpected replay access")),
              patch("gateway_pilot.windows_live.default_route", return_value=route),
              patch("gateway_pilot.windows_live.sample_echo", side_effect=sample) as ping):
            result = analyze({"message": "Gateway hiện tại là gì?", "source_mode": "live",
                              "fixture_id": "not-used", "with_guide": True})
        ping.assert_called_once_with("192.168.4.1", "192.168.4.2")
        self.assertEqual(result["mode"], "windows_live")
        self.assertEqual(result["case_status"], "RESOLVED")
        self.assertIn("192.168.4.1", result["answer"])
        self.assertTrue(all(row["source"] == "windows_live/v1" for row in result["evidence"]))
        self.assertFalse(result["runbooks"])

    def test_route_change_invalidates_the_previous_gateway(self):
        routes = [{"gateway": "192.168.4.1", "source_ipv4": "192.168.4.2"},
                  {"gateway": "192.168.0.1", "source_ipv4": "192.168.0.2"}]
        with (patch("gateway_pilot.windows_live.default_route", side_effect=routes),
              patch("gateway_pilot.windows_live.sample_echo") as ping):
            result = analyze({"message": "Gateway hiện tại là gì?", "source_mode": "live"})
        ping.assert_not_called()
        self.assertEqual(result["case_status"], "INCONCLUSIVE")
        self.assertEqual(result["timeline"][-1]["status"], "ROUTE_CHANGED")
        self.assertFalse(result["evidence_ids"])

    def test_online_lookup_needs_router_data(self):
        result = analyze({"message": "Ai đang online?", "source_mode": "live"})
        self.assertEqual(result["workflow"], "WF-001")
        self.assertEqual(result["diagnosis"], "live_capability_missing")
        self.assertEqual(result["calls"], 0)

    def test_quality_intents_use_the_same_live_measurement_plan(self):
        route = {"gateway": "192.168.4.1", "source_ipv4": "192.168.4.2"}
        with (patch("gateway_pilot.windows_live.default_route", return_value=route),
              patch("gateway_pilot.windows_live.sample_echo", side_effect=sample),
              patch("gateway_pilot.windows_live._dns", return_value={"query": "example.com", "resolved": True})):
            for question in ("mạng chất lượng thế nào", "Đo độ trễ và mất gói từ máy này",
                             "Đường truyền bữa nay có đáng tin không?"):
                with self.subTest(question=question):
                    result = analyze({"message": question, "source_mode": "live"})
                    self.assertEqual(result["workflow"], "LIVE-QUALITY")
                    self.assertEqual(result["case_status"], "RESOLVED")
                    self.assertIn("mất gói ICMP 25%", result["answer"])
                    self.assertIn("trung bình 40 ms", result["answer"])
                    ports = {e["port"] for e in result["evidence"] if e["id"] in result["evidence_ids"]}
                    self.assertEqual(ports, {"live.route", "live.gateway", "live.internet", "live.dns"})
            speed = analyze({"message": "Tốc độ tải là bao nhiêu Mbps?", "source_mode": "live"})
            combined = analyze({"message": "Ai đang online và chất lượng mạng thế nào?", "source_mode": "live"})
        self.assertEqual(speed["case_status"], "PARTIAL")
        self.assertIn("Chưa đo được tốc độ", speed["answer"])
        self.assertEqual(combined["case_status"], "PARTIAL")
        self.assertIn("bảng thiết bị từ router", combined["answer"])
        self.assertIn("trung bình 40 ms", combined["answer"])

    def test_llm_intake_selects_from_catalog_and_rejects_unknown_goals(self):
        advisor = Mock(model="test-model")
        route = {"gateway": "192.168.4.1", "source_ipv4": "192.168.4.2"}
        payload = {"message": "Đường truyền đôi khi khựng giữa chừng.", "source_mode": "live", "with_llm": True}
        with (patch("gateway_pilot.workflow_advisor.OllamaProbeAdvisor", return_value=advisor),
              patch("gateway_pilot.windows_live.default_route", return_value=route),
              patch("gateway_pilot.windows_live.sample_echo", side_effect=sample),
              patch("gateway_pilot.windows_live._dns", return_value={"query": "example.com", "resolved": True})):
            advisor.understand_live_request.return_value = "quality"
            result = analyze(payload)
            advisor.understand_live_request.return_value = "run_arbitrary_command"
            rejected = analyze(payload)
        self.assertEqual(result["workflow"], "LIVE-QUALITY")
        self.assertTrue(result["intake"]["accepted"])
        self.assertFalse(rejected["intake"]["accepted"])
        self.assertEqual(rejected["calls"], 0)
        self.assertEqual(rejected["action"], "ASK_USER")
