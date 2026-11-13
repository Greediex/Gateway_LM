"""Synthetic rule inputs and bounded chat; rules never collect OS data."""
import copy
import unittest
from unittest.mock import patch
from gateway_pilot.features.laptop_network import diagnose_snapshot
from gateway_pilot.application.diagnose_network import chat_linux


class LaptopRuleTests(unittest.TestCase):
    def setUp(self):
        values = {"laptop.route":{"has_route":True,"interface":"ethernet0","gateway":"192.0.2.1"},
                  "laptop.gateway_probe":{"sent":4,"received":4,"latency_ms":1,"loss_pct":0},
                  "laptop.internet_probe":{"sent":4,"received":4,"latency_ms":20,"loss_pct":0},
                  "laptop.dns":{"query":"example.com","resolved":True,"interface":"ethernet0"},
                  "laptop.wifi":{"interface":"wifi0","radio_enabled":True,"associated":True,"signal_pct":70}}
        self.snapshot = {"facts":{pid:{"evidence_id":"synthetic-"+pid,"value":value} for pid,value in values.items()}}
        self.availability = {"network.laptop.connectivity":{"status":"READY"},"network.laptop.wifi":{"status":"READY"}}
    def diagnose(self):
        return diagnose_snapshot(self.snapshot,self.availability)
    def test_measured_is_not_health_and_route_mismatch_is_explicit(self):
        conn,wifi = self.diagnose()
        self.assertEqual(conn["status"],"MEASURED")
        self.assertIn("Chưa kiểm tra truy cập web",conn["summary"])
        self.assertIn("chưa kiểm chứng Internet qua Wi-Fi",wifi["summary"])
        self.assertTrue(conn["evidence_ids"])
    def test_missing_measurement_never_complete(self):
        for pid in ("laptop.route","laptop.gateway_probe","laptop.internet_probe","laptop.dns"):
            original = self.snapshot["facts"].pop(pid)
            conn = self.diagnose()[0]
            self.assertEqual(conn["status"],"INCOMPLETE")
            self.assertIn(pid,conn["missing_ports"])
            self.snapshot["facts"][pid] = original
    def test_no_route_loss_dns_failure_and_no_causal_claim(self):
        original=copy.deepcopy(self.snapshot)
        cases=[("laptop.route","has_route",False,"NO_ROUTE"),
               ("laptop.internet_probe","loss_pct",100,"IP_PROBE_LOSS"),
               ("laptop.dns","resolved",False,"DNS_NOT_RESOLVED")]
        for pid,key,value,code in cases:
            self.snapshot=copy.deepcopy(original);self.snapshot["facts"][pid]["value"][key]=value
            self.assertEqual(self.diagnose()[0]["code"],code)
            self.assertEqual(self.diagnose()[0]["status"],"ISSUE")
    def test_radio_off_disconnected_and_metric_missing(self):
        original=copy.deepcopy(self.snapshot)
        for key,value,code in (("radio_enabled",False,"WIFI_RADIO_OFF"),("associated",False,"WIFI_DISCONNECTED"),
                               ("signal_pct",-1,"WIFI_SIGNAL_MISSING"),("signal_pct",20,"WIFI_SIGNAL_LOW")):
            self.snapshot=copy.deepcopy(original);self.snapshot["facts"]["laptop.wifi"]["value"][key]=value
            self.assertEqual(self.diagnose()[1]["code"],code)
    def test_write_router_and_device_boundaries_make_no_measurements(self):
        with patch("gateway_pilot.application.diagnose_network.diagnose_network") as run:
            for prompt in ("Chặn Internet thiết bị", "CPU RAM router", "Ai đang kết nối wifi?"):
                result=chat_linux(prompt)
                self.assertEqual(result["calls"],0)
            run.assert_not_called()
    def test_gateway_no_reply_never_displays_negative_latency(self):
        facts={"laptop.route":{"evidence_id":"route", "function_id":"laptop.route", "scope":"client", "target":"local",
                "source":"linux_client/test","observed_at":"2026-11-13T00:00:00Z", "value":self.snapshot["facts"]["laptop.route"]["value"]},
               "laptop.gateway_probe":{"evidence_id":"ping", "function_id":"laptop.gateway_probe", "scope":"client", "target":"local",
                "source":"linux_client/test","observed_at":"2026-11-13T00:00:00Z", "value":{"sent":4,"received":0,"latency_ms":-1}}}
        with patch("gateway_pilot.application.diagnose_network.diagnose_network",return_value={"features":[],"snapshot":{"facts":facts,"missing_ports":[]}}):
            result=chat_linux("Gateway hiện tại là gì?")
        self.assertNotIn("-1 ms",result["answer"])
        self.assertIn("chưa có số đo RTT",result["answer"])

    def test_application_synthetic_backend_runs_core_before_rules(self):
        from gateway_pilot.adapters.read_backends import ReplayReadBackend
        from gateway_pilot.adapters.linux_wifi import LinuxWifiBackend
        from gateway_pilot.application.diagnose_network import diagnose_network
        class SyntheticLinuxBackend(ReplayReadBackend):
            source = "linux_client/synthetic_test"
            probe_ids = LinuxWifiBackend.probe_ids
            interface = "wifi0"
        values = {"clients.resolve":{"client.identity":{"client_id":"local-laptop"}},
                  "client.ipv4":{"client.ipv4":{"configured":True,"address":"192.0.2.10"}},
                  "laptop.route":{"laptop.route":{"has_route":True,"interface":"ethernet0","source_ipv4":"192.0.2.10",
                                      "gateway":"192.0.2.1","resolver_fingerprint":"f"*64}},
                  "laptop.wifi":{"laptop.wifi":{"interface":"wifi0","radio_enabled":True,"associated":True,
                                   "ssid":"synthetic","bssid":"synthetic","signal_pct":20,"channel":1,"frequency_mhz":2412,"ap_rate_mbps":54}},
                  "laptop.gateway_probe":{"laptop.gateway_probe":{"destination":"192.0.2.1","interface":"ethernet0",
                    "sent":4,"received":4,"loss_pct":0,"latency_ms":2}},
                  "laptop.internet_probe":{"laptop.internet_probe":{"destination":"1.1.1.1","interface":"ethernet0",
                    "sent":4,"received":0,"loss_pct":100,"latency_ms":-1}},
                  "laptop.dns":{"laptop.dns":{"query":"example.com","resolved":False,"interface":"ethernet0"}}}
        backend = SyntheticLinuxBackend(values,client_id="local-laptop")
        result = diagnose_network(backend=backend)
        self.assertEqual(result["calls"],7)
        self.assertEqual(len(result["timeline"]),7)
        self.assertTrue(all(r["status"] == "OK" for r in result["timeline"]))
        self.assertEqual(result["snapshot"]["missing_ports"],[])
        self.assertTrue(all(f["evidence_ids"] for f in result["features"]))
        self.assertEqual([f["code"] for f in result["features"]],["IP_PROBE_LOSS","WIFI_SIGNAL_LOW"])
        self.assertFalse(result["route_uses_wifi"])
        self.assertEqual(result["router_health"]["status"],"UNAVAILABLE")
        self.assertTrue(all(r["contract_digest"] for r in result["snapshot"]["facts"].values()))
