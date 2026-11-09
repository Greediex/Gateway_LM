import copy
import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.core import (ROOT, PlanError, Registry, bind_and_gate, execute,
                                new_state, read_json, support, validate_decision)
from gateway_pilot.run import prompt, run_case, summarize


class PilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = Registry()
        cls.cases = read_json(ROOT / "data/cases.json")

    def case(self, template="wan_healthy"):
        return copy.deepcopy(next(c for c in self.cases if c["template"] == template))

    def state(self, case=None):
        return new_state(case or self.case(), self.registry)

    def test_closure_builds_ordered_dependencies(self):
        self.assertEqual(self.registry.closure(["wan.probe"], self.state()),
                         ["wan.status", "wan.routes", "wan.probe"])

    def test_closure_reuses_fresh_fact(self):
        c = self.case()
        s = self.state(c)
        execute("wan.status", {}, s, c, self.registry)
        self.assertEqual(self.registry.closure(["wan.probe"], s), ["wan.routes", "wan.probe"])

    def test_stale_fact_cannot_satisfy_prerequisite(self):
        c = self.case()
        s = self.state(c)
        execute("wan.status", {}, s, c, self.registry)["age_s"] = 100
        self.assertEqual(self.registry.closure(["wan.routes"], s), ["wan.status", "wan.routes"])

    def test_cycle_rejected(self):
        registry = copy.deepcopy(self.registry)
        registry.functions["wan.status"]["requires"] = ["wan.probe"]
        with self.assertRaisesRegex(PlanError, "cycle"):
            registry.closure(["wan.probe"], self.state())

    def test_missing_capability_rejected(self):
        s = self.state()
        s.capabilities.remove("wan.status")
        with self.assertRaisesRegex(PlanError, "missing_producer"):
            self.registry.closure(["wan.probe"], s)

    def test_node_budget(self):
        with self.assertRaisesRegex(PlanError, "budget"):
            self.registry.closure(["wan.probe"], self.state(), max_nodes=2)

    def test_flat_call_missing_precondition_rejected(self):
        with self.assertRaisesRegex(PlanError, "missing_precondition"):
            bind_and_gate("wan.probe", {}, self.state(), self.registry)

    def test_write_rejected_by_compiler_and_gate(self):
        with self.assertRaisesRegex(PlanError, "transaction"):
            self.registry.closure(["dns.apply"], self.state())
        with self.assertRaisesRegex(PlanError, "transaction"):
            bind_and_gate("qos.apply", {}, self.state(), self.registry)

    def test_unknown_tool_rejected(self):
        with self.assertRaisesRegex(PlanError, "unknown_function"):
            bind_and_gate("shell.run", {}, self.state(), self.registry)

    def test_wrong_client_argument_rejected(self):
        c = self.case("dhcp_healthy")
        s = self.state(c)
        execute("clients.resolve", {}, s, c, self.registry)
        with self.assertRaisesRegex(PlanError, "wrong_target"):
            execute("dhcp.leases", {"client_id": "someone_else"}, s, c, self.registry)

    def test_wrong_target_observation_unusable(self):
        c = self.case("dhcp_wrong_client")
        s = self.state(c)
        execute("clients.resolve", {}, s, c, self.registry)
        execute("dhcp.leases", {}, s, c, self.registry)
        self.assertIsNone(s.fact("dhcp.leases"))
        self.assertFalse(support("client_no_lease", s, c)[0])

    def test_stale_dns_cannot_support_finish(self):
        c = self.case("dns_stale")
        s = self.state(c)
        for fid in self.registry.closure(["dns.probe", "wan.probe"], s):
            execute(fid, {}, s, c, self.registry)
        self.assertFalse(support("gateway_dns_failure", s, c)[0])

    def test_timeout_is_unknown_not_false(self):
        c = self.case("wan_timeout")
        s = self.state(c)
        for fid in self.registry.closure(["wan.probe"], s):
            execute(fid, {}, s, c, self.registry)
        self.assertIsNone(s.fact("wan.probe"))
        self.assertFalse(support("wan_packet_loss", s, c)[0])
        self.assertFalse(support("no_fault_observed", s, c)[0])

    def test_malformed_adapter_data_is_unknown(self):
        c = self.case("sys_parse")
        s = self.state(c)
        observation = execute("system.resources", {}, s, c, self.registry)
        self.assertEqual(observation["status"], "PARSE_ERROR")
        self.assertIsNone(s.fact("system.resources"))

    def test_healthy_link_alone_cannot_finish(self):
        c = self.case()
        s = self.state(c)
        execute("wan.status", {}, s, c, self.registry)
        self.assertFalse(support("no_fault_observed", s, c)[0])

    def test_finish_requires_real_and_complete_citations(self):
        c = self.case("wan_down")
        s = self.state(c)
        execute("wan.status", {}, s, c, self.registry)
        for ids in ([], ["e999"], ["e1", "e999"]):
            with self.assertRaises(PlanError):
                validate_decision({"action": "FINISH", "diagnosis": "wan_link_down", "evidence_ids": ids},
                                  s, c, self.registry, list(self.registry.functions))
        validate_decision({"action": "FINISH", "diagnosis": "wan_link_down", "evidence_ids": ["e1"]},
                          s, c, self.registry, list(self.registry.functions))

    def test_prompt_never_contains_gold_world_id_template(self):
        c = self.case()
        c["gold"] = {"secret": "GOLD_CANARY_538"}
        c["world"] = {"secret": "WORLD_CANARY_948"}
        c["id"] = "CASE_CANARY_384"
        c["template"] = "TEMPLATE_CANARY_138"
        messages = json.dumps(prompt(c, self.state(c), self.registry, ["wan.status"], 10))
        for canary in ("GOLD_CANARY_538", "WORLD_CANARY_948", "CASE_CANARY_384", "TEMPLATE_CANARY_138"):
            self.assertNotIn(canary, messages)

    def test_rule_baseline_blind_to_gold(self):
        c = self.case("wan_down")
        c["gold"] = {"action": "FINISH", "diagnosis": "system_cpu_load"}
        args = Namespace(max_decisions=10, max_tools=12, candidate_k=4)
        result = run_case(c, "rules", args, self.registry)
        self.assertEqual(result["terminal"]["diagnosis"], "wan_link_down")
        self.assertFalse(result["autonomous_success"])

    def test_rules_for_representative_fault_and_missing_cases(self):
        args = Namespace(max_decisions=10, max_tools=12, candidate_k=4)
        for template in ("wan_down", "wan_route", "wan_loss", "wan_timeout", "dns_fail", "dns_stale",
                         "dhcp_pool", "dhcp_service", "dhcp_ambiguous", "sys_cpu", "sys_parse", "write_denied"):
            with self.subTest(template=template):
                self.assertTrue(run_case(self.case(template), "rules", args, self.registry)["autonomous_success"])

    def test_retrieval_graph_adds_required_producers(self):
        c = self.case("dns_fail")
        s = self.state(c)
        retrieved = self.registry.candidates(c, s, "retrieval", k=1)
        graph = self.registry.candidates(c, s, "graph", k=1)
        self.assertTrue(set(retrieved).issubset(graph))
        for fid in graph:
            self.assertEqual(self.registry.functions[fid]["risk"], "READ")

    def test_no_network_or_shell_executor_in_fixture(self):
        for f in self.registry.functions.values():
            self.assertEqual(f["adapter"], "synthetic_replay/v1")

    def test_forced_stop_not_counted_as_model_success(self):
        c = self.case("sys_missing")
        args = Namespace(max_decisions=0, max_tools=12, candidate_k=4)
        r = run_case(c, "rules", args, self.registry)
        self.assertTrue(r["outcome_match"])
        self.assertFalse(r["autonomous_success"])

    def test_incomplete_cannot_fabricate_evidence(self):
        c = self.case()
        with self.assertRaisesRegex(PlanError, "fabricated_evidence"):
            validate_decision({"action": "INCOMPLETE", "diagnosis": "insufficient_evidence", "evidence_ids": ["e999"]},
                              self.state(c), c, self.registry, [])

    def test_incomplete_cannot_claim_healthy(self):
        c = self.case()
        with self.assertRaisesRegex(PlanError, "action_diagnosis_mismatch"):
            validate_decision({"action": "INCOMPLETE", "diagnosis": "no_fault_observed", "evidence_ids": []},
                              self.state(c), c, self.registry, [])

    def test_dns_goal_expands_cross_skill_producer(self):
        c = self.case("dns_fail")
        candidates = self.registry.candidates(c, self.state(c), "graph", k=1)
        for fid in ("dns.config", "dns.probe", "wan.status", "wan.routes", "wan.probe"):
            self.assertIn(fid, candidates)

    def test_wan_down_world_is_coherent(self):
        world = self.case("wan_down")["world"]
        self.assertFalse(world["wan.status"]["link_up"])
        self.assertFalse(world["wan.routes"]["default_route"])
        self.assertEqual(world["wan.probe"]["loss_pct"], 100)

    def test_batch_dns_uses_only_read_producers(self):
        c = self.case("dns_fail")
        args = Namespace(max_decisions=2, max_tools=12, candidate_k=4)
        decision = {"action": "FINISH", "diagnosis": "gateway_dns_failure", "evidence_ids": ["e2", "e5"]}
        with patch("gateway_pilot.run.model_decision", return_value=(decision, {"wall_s": 0, "ollama": {}})):
            result = run_case(c, "graph_batch", args, self.registry)
        self.assertTrue(result["autonomous_success"])
        self.assertEqual(result["tool_calls"], 5)
        self.assertNotIn("dns.apply", [x["function_id"] for x in result["executed"]])

    def test_batch_resource_gold_is_not_used_for_prediction(self):
        c = self.case("sys_ram")
        args = Namespace(max_decisions=1, max_tools=12, candidate_k=4)
        wrong = {"action": "FINISH", "diagnosis": "no_fault_observed", "evidence_ids": ["e1"]}
        with patch("gateway_pilot.run.model_decision", return_value=(wrong, {"wall_s": 0, "ollama": {}})):
            result = run_case(c, "graph_batch", args, self.registry)
        self.assertFalse(result["autonomous_success"])
        self.assertTrue(result["forced_stop"])
        self.assertIn("unsupported_finish_or_missing_citations", result["raw_rejections"])


if __name__ == "__main__":
    unittest.main()
