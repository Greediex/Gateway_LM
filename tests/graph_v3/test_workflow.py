import copy
import unittest
from unittest.mock import Mock

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.workflow import diagnose, replay_from_fixture, workflow_registry


class TextWorkflowTests(unittest.TestCase):
    request = "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?"

    @classmethod
    def setUpClass(cls):
        cls.registry = workflow_registry()
        cls.fixtures = {case["id"]: case for case in read_json(ROOT / "data/cases.json")}

    def replay(self, case_id="GLM-21-0"):
        return replay_from_fixture(copy.deepcopy(self.fixtures[case_id]), self.registry)

    def run_request(self, request=None, replay=None, **options):
        options.setdefault("dynamic", False)
        return diagnose(request or self.request, self.replay() if replay is None else replay,
                        registry=self.registry, **options)

    def assert_result(self, result, action, diagnosis, expected_calls):
        terminal = result["terminal"]
        self.assertEqual((terminal["action"], terminal["diagnosis"]), (action, diagnosis))
        graph = result.get("graph", {})
        calls = [row["function_id"] for row in graph.get("executed", [])]
        self.assertEqual(calls, expected_calls)
        evidence = {e["id"]: e for e in graph.get("evidence", [])}
        for eid in terminal["evidence_ids"]:
            self.assertEqual(evidence[eid]["status"], "OK")

    def test_same_question_adapts_to_observed_fault(self):
        client_base = ["clients.resolve", "wifi.station"]
        link_base = client_base + ["client.ipv4", "wan.status"]
        for tool, change, label, calls in [
            ("wifi.station", {"rssi_dbm": -88}, "wifi_weak_signal", client_base),
            ("wifi.station", {"associated": False}, "client_not_associated", client_base),
            ("wan.status", {"link_up": False}, "wan_link_down", link_base),
            ("wan.routes", {"default_route": False}, "wan_no_route", link_base + ["wan.routes"]),
            ("wan.probe", {"loss_pct": 90}, "wan_packet_loss", link_base + ["wan.routes", "wan.probe"]),
            ("dns.probe", {"rcode": "SERVFAIL"}, "gateway_dns_failure",
             link_base + ["wan.routes", "wan.probe", "dns.config", "dns.probe"]),
        ]:
            with self.subTest(label=label):
                replay = self.replay()
                world = replay["devices"][0]["world"] if tool == "wifi.station" else replay["world"]
                world[tool].update(change)
                result = self.run_request(replay=replay)
                self.assertEqual(result["workflow"], "WF-INTERNET")
                self.assert_result(result, "FINISH", label, calls)
                self.assertTrue(result["terminal"]["evidence_ids"])

    def test_missing_ipv4_follows_dhcp_instead_of_wan(self):
        replay = self.replay()
        device = replay["devices"][0]["world"]
        device["client.ipv4"].update(address="", configured=False)
        device["dhcp.leases"]["lease_valid"] = False
        replay["world"]["dhcp.pool"]["free_addresses"] = 0
        result = self.run_request(replay=replay)
        self.assert_result(result, "FINISH", "dhcp_pool_exhausted",
                           ["clients.resolve", "wifi.station", "client.ipv4", "dhcp.leases", "dhcp.pool"])

    def test_router_health_does_not_prove_client_path(self):
        advisor = Mock()
        result = self.run_request(advisor=advisor)
        advisor.assert_not_called()
        self.assertEqual(result["workflow_id"], "WF-018")
        self.assertEqual(result["case_status"], "PARTIAL")
        self.assert_result(result, "INCOMPLETE", "client_path_unverified",
                           ["clients.resolve", "wifi.station", "client.ipv4", "wan.status",
                            "wan.routes", "wan.probe", "dns.config", "dns.probe"])
        graph = result["graph"]
        self.assertEqual(graph["stages"][-1]["goal"], "client.probe")
        self.assertIn("capability", graph["stages"][-1]["error"])
        self.assertTrue(all(row["upstream_kernel_used"] for row in graph["retrievals"]))
        self.assertEqual([p["revision"] for p in graph["plans"]], list(range(1, len(graph["plans"]) + 1)))
        self.assertEqual(graph["plans"][0]["edges"][0]["kind"], "DATA")
        self.assertEqual(graph["executed"][1]["arguments"]["client_id"], result["target"]["client_id"])

    def test_client_probe_uses_target_and_limits_conclusion_to_measured_path(self):
        for loss, action, diagnosis in [(80, "FINISH", "client_path_loss"),
                                        (0, "INCOMPLETE", "client_ip_reachable")]:
            with self.subTest(loss=loss):
                replay = self.replay()
                replay["capabilities"].append("client.probe")
                replay["devices"][0]["world"]["client.probe"]["loss_pct"] = loss
                result = self.run_request(replay=replay)
                self.assert_result(result, action, diagnosis,
                                   ["clients.resolve", "wifi.station", "client.ipv4", "wan.status",
                                    "wan.routes", "wan.probe", "dns.config", "dns.probe", "client.probe"])
                self.assertEqual(result["graph"]["executed"][-1]["arguments"]["client_id"],
                                 result["target"]["client_id"])

    def test_stale_or_wrong_device_wifi_cannot_support_a_diagnosis(self):
        for detail in ({"_age_s": 300}, {"_target": "client_other"}):
            with self.subTest(detail=detail):
                replay = self.replay()
                replay["devices"][0]["world"]["wifi.station"].update({"rssi_dbm": -88, **detail})
                result = self.run_request(replay=replay)
                self.assert_result(result, "INCOMPLETE", "insufficient_evidence",
                                   ["clients.resolve", "wifi.station"])

    def test_clarification_and_write_gate_run_no_tools(self):
        for request, action, diagnosis in [
            ("Kiểm tra giúp tôi.", "ASK_USER", "intent_unclear"),
            ("Laptop Bình bắt Wi-Fi nhưng không vào mạng.", "ASK_USER", "target_ambiguous"),
            ("Wi-Fi có mà Internet không dùng được.", "ASK_USER", "target_ambiguous"),
            ("Đổi DNS router sang 8.8.8.8 ngay.", "INCOMPLETE", "unsafe_change_denied"),
        ]:
            with self.subTest(request=request):
                self.assert_result(self.run_request(request), action, diagnosis, [])

    def test_policy_block_is_distinct_from_missing_measurements(self):
        replay = self.replay()
        replay["permissions"] = []
        advisor = Mock()
        result = self.run_request(replay=replay, advisor=advisor)
        self.assert_result(result, "INCOMPLETE", "read_permission_denied", [])
        self.assertEqual(result["case_status"], "BLOCKED")
        advisor.assert_not_called()

    def test_advisor_can_choose_an_admissible_probe_and_save_calls(self):
        replay = self.replay()
        replay["capabilities"].append("client.probe")
        replay["devices"][0]["world"]["client.probe"]["loss_pct"] = 80
        advisor = Mock(return_value="client.probe")
        result = self.run_request(replay=replay, advisor=advisor)
        self.assert_result(result, "FINISH", "client_path_loss",
                           ["clients.resolve", "wifi.station", "client.ipv4", "wan.status",
                            "wan.routes", "wan.probe", "client.probe"])
        advisor.assert_called_once()
        self.assertEqual(advisor.call_args.args[2], ("dns.probe", "client.probe"))
        self.assertTrue(result["graph"]["advice"][0]["accepted"])
        self.assertEqual(result["case_status"], "PARTIAL")

    def test_outside_candidate_and_model_failure_fall_back_to_core(self):
        replay = self.replay()
        replay["capabilities"].append("client.probe")
        core = self.run_request(replay=replay)
        for advisor in (Mock(return_value="dns.apply"), Mock(side_effect=TimeoutError())):
            result = self.run_request(replay=replay, advisor=advisor)
            self.assertEqual(result["terminal"], core["terminal"])
            self.assertEqual(result["graph"]["executed"], core["graph"]["executed"])
            self.assertFalse(result["graph"]["advice"][0]["accepted"])

    def test_client_dns_requires_matching_domain_scope_and_good_ip_path(self):
        replay = self.replay()
        replay["capabilities"].extend(("client.probe", "client.dns"))
        client_world = replay["devices"][0]["world"]
        client_world["client.dns"] = {"query": "Example.COM.", "rcode": "SERVFAIL"}
        valid = self.run_request(replay=replay)
        self.assertEqual(valid["terminal"]["diagnosis"], "client_dns_failure")
        self.assertEqual(valid["case_status"], "RESOLVED")
        self.assertEqual(valid["graph"]["executed"][-1]["arguments"]["client_id"], valid["target"]["client_id"])
        self.assertEqual(len(valid["terminal"]["evidence_ids"]), 3)
        for change in ({"query": "other.example"}, {"_target": "client_other"}, {"_age_s": 300}):
            with self.subTest(change=change):
                current = copy.deepcopy(replay)
                current["devices"][0]["world"]["client.dns"].update(change)
                self.assertEqual(self.run_request(replay=current)["terminal"]["diagnosis"], "client_ip_reachable")

    def test_ambiguous_inventory_and_resolver_never_probe_a_guessed_device(self):
        replay = self.replay()
        replay["devices"].append({"selector": "laptop-binh", "aliases": ["Laptop An"], "world": {}})
        self.assert_result(self.run_request(replay=replay), "ASK_USER", "target_ambiguous", [])
        result = self.run_request("Điện thoại của tôi không được cấp IP.", self.replay("GLM-13-0"))
        self.assertEqual(result["terminal"]["action"], "ASK_USER")
        self.assertTrue(result["graph"]["executed"])
        self.assertEqual({x["function_id"] for x in result["graph"]["executed"]}, {"clients.resolve"})

    def test_case_call_budget_applies_across_stages(self):
        result = self.run_request(max_calls=3)
        self.assert_result(result, "INCOMPLETE", "insufficient_evidence",
                           ["clients.resolve", "wifi.station", "client.ipv4"])
        self.assertEqual(result["graph"]["calls"], 3)

    def test_dynamic_probe_falls_back_after_wan_timeout(self):
        replay = self.replay()
        replay["capabilities"].append("client.probe")
        replay["world"]["wan.probe"]["_status"] = "TIMEOUT"
        replay["devices"][0]["world"]["client.probe"]["loss_pct"] = 80
        advisor = Mock()
        result = self.run_request(replay=replay, dynamic=True, advisor=advisor)
        self.assert_result(result, "FINISH", "client_path_loss",
                           ["clients.resolve", "wifi.station", "client.ipv4", "wan.status",
                            "wan.routes", "wan.probe", "client.probe"])
        self.assertEqual(result["case_status"], "PARTIAL")
        stage = result["graph"]["policy_steps"][-1]
        self.assertFalse(stage["wan_verified"])
        self.assertEqual(stage["selected"], "client.probe")
        advisor.assert_not_called()

    def test_dynamic_only_offers_candidates_within_call_budget(self):
        replay = self.replay()
        replay["capabilities"].append("client.probe")
        advisor = Mock()
        result = self.run_request(replay=replay, dynamic=True, max_calls=7, advisor=advisor)
        self.assert_result(result, "INCOMPLETE", "client_ip_reachable",
                           ["clients.resolve", "wifi.station", "client.ipv4", "wan.status",
                            "wan.routes", "wan.probe", "client.probe"])
        self.assertEqual(result["graph"]["policy_steps"][-1]["rejected"]["dns.probe"],
                         "insufficient_call_budget")
        advisor.assert_not_called()

    def test_dynamic_rejects_advisor_choice_outside_compiled_goals(self):
        replay = self.replay()
        replay["capabilities"].append("client.probe")
        replay["devices"][0]["world"]["client.probe"]["loss_pct"] = 80
        advisor = Mock(return_value="dns.apply")
        result = self.run_request(replay=replay, dynamic=True, advisor=advisor)
        self.assert_result(result, "FINISH", "client_path_loss",
                           ["clients.resolve", "wifi.station", "client.ipv4", "wan.status",
                            "wan.routes", "wan.probe", "client.probe"])
        advisor.assert_called_once()
        self.assertFalse(result["graph"]["advice"][0]["accepted"])

    def test_dns_fault_requires_reachable_external_ip(self):
        replay = self.replay()
        replay["world"]["dns.probe"]["rcode"] = "SERVFAIL"
        replay["world"]["wan.status"]["link_up"] = False
        result = self.run_request("Kiểm tra DNS của router.", replay)
        self.assert_result(result, "INCOMPLETE", "insufficient_evidence",
                           ["dns.config", "dns.probe", "wan.status"])

    def test_default_wan_policy_groups_route_and_probe_and_honors_guard(self):
        for route_ok, diagnosis in ((True, "no_fault_observed"), (False, "wan_no_route")):
            with self.subTest(route_ok=route_ok):
                replay = self.replay()
                replay["world"]["wan.routes"]["default_route"] = route_ok
                result = diagnose("Kiểm tra WAN của router.", replay, registry=self.registry)
                calls = ["wan.status", "wan.routes"] + (["wan.probe"] if route_ok else [])
                self.assert_result(result, "FINISH", diagnosis, calls)
                self.assertEqual(result["decision_source"], "dynamic_policy")
                self.assertEqual(result["graph"]["plans"][1]["goals"], ("wan.routes", "wan.probe"))

    def test_dynamic_dns_timeout_keeps_verified_wan_result_partial(self):
        replay = self.replay()
        replay["world"]["dns.probe"]["_status"] = "TIMEOUT"
        result = self.run_request("Kiểm tra DNS của router.", replay, dynamic=True)
        self.assert_result(result, "INCOMPLETE", "gateway_ip_reachable_dns_unverified",
                           ["dns.config", "dns.probe", "wan.status", "wan.routes", "wan.probe"])
        self.assertEqual(result["case_status"], "PARTIAL")

    def test_dynamic_dhcp_uses_service_when_pool_is_unavailable(self):
        replay = self.replay()
        replay["devices"][0]["world"]["dhcp.leases"]["lease_valid"] = False
        replay["world"]["dhcp.service"]["running"] = False
        replay["capabilities"].remove("dhcp.pool")
        result = self.run_request("Laptop An chưa được cấp IP.", replay, dynamic=True)
        self.assert_result(result, "FINISH", "dhcp_service_down",
                           ["clients.resolve", "dhcp.leases", "dhcp.service"])
        self.assertIn("dhcp.pool", result["graph"]["policy_steps"][-1]["rejected"])

    def test_dynamic_system_uses_verified_resources_and_rejects_stale_data(self):
        for age, action, diagnosis in ((0, "FINISH", "system_cpu_load"),
                                       (300, "INCOMPLETE", "insufficient_evidence")):
            with self.subTest(age=age):
                replay = self.replay()
                replay["world"]["system.resources"] = {"available_ram_pct": 35, "cpu_pct": 98,
                                                       "storage_used_pct": 20, "_age_s": age}
                result = self.run_request("Kiểm tra CPU của router.", replay, dynamic=True)
                self.assert_result(result, action, diagnosis, ["system.resources"])
                self.assertEqual(result["graph"]["policy_steps"][0]["selected"], "system.resources")

    def test_routing_ignores_fixture_workflow_gold_and_private_world(self):
        fixture = copy.deepcopy(self.fixtures["GLM-21-0"])
        fixture["workflow"] = "WF-WRITE"
        fixture["gold"] = {"action": "FINISH", "diagnosis": "wifi_weak_signal"}
        result = self.run_request(replay=replay_from_fixture(fixture, self.registry))
        self.assertEqual(result["workflow"], "WF-INTERNET")
        self.assertEqual(result["terminal"]["diagnosis"], "client_path_unverified")
        result = self.run_request("Kiểm tra cổng WAN của router.", self.replay())
        self.assert_result(result, "FINISH", "no_fault_observed", ["wan.status", "wan.routes", "wan.probe"])


if __name__ == "__main__":
    unittest.main()
