"""T7: evidence records, scoped facts, hypotheses, state revision and Contracts B/C."""
import copy
import json
import unittest

from jsonschema import Draft202012Validator

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler, NodeState
from gateway_pilot.graph_v3.registry_v01 import fact_assertions
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState

SCHEMAS = {name: read_json(ROOT / f"docs/contracts/{name}.schema.json")
           for name in ("contract_b", "contract_c", "evidence_record")}


def valid(name, document):
    return not list(Draft202012Validator(SCHEMAS[name]).iter_errors(document))


class EvidenceT7Tests(unittest.TestCase):
    def setUp(self):
        self.now = 0.0
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(c for c in read_json(ROOT / "data/cases.json") if c["template"] == "dns_fail"))

    def state(self, case=None, registry=None):
        return CaseState(case or self.case, registry or self.registry, lambda: self.now)

    def run_goals(self, goals, state, case=None, registry=None):
        registry = registry or self.registry
        runner = GraphRunner(registry, case or self.case, state, max_repairs=0)
        return runner, runner.run(Compiler(registry).compile(goals, state))

    def test_router_proof_with_unmeasured_client_goal_is_partial_not_resolved(self):
        case = copy.deepcopy(self.case)
        case["target"] = {"scope": "client", "selector": "laptop-an", "client_id": "client_01"}
        state = self.state(case)
        self.assertNotIn("client.probe", state.capabilities)
        self.run_goals(["wan.probe"], state, case)
        self.assertEqual(state.fact_table()["router_wan_reachable"]["value"], "TRUE")
        self.assertEqual(state.fact_table()["client_internet_reachable"]["value"], "UNKNOWN")
        goals = ["wan.probe", "client.probe"]
        self.assertEqual(state.case_status(goals), "PARTIAL")
        self.assertEqual(state.case_status(goals, exhausted=True), "PARTIAL")
        contract = state.export_contract_c(goals)
        self.assertEqual(contract["decision"], "PARTIAL")
        self.assertEqual(contract["outstanding_questions"], ["client_internet_reachable"])
        self.assertEqual(state.case_status(["wan.probe"]), "RESOLVED")
        # A missing gateway goal that cannot be measured is INCONCLUSIVE, never PARTIAL.
        state.capabilities.discard("dhcp.pool")
        self.assertEqual(state.case_status(["wan.probe", "dhcp.pool"]), "INCONCLUSIVE")
        # Still measurable: CONTINUE, unless the runner reports its budget exhausted.
        self.assertEqual(state.case_status(["wan.probe", "dns.probe"]), "CONTINUE")
        self.assertEqual(state.case_status(["wan.probe", "dns.probe"], exhausted=True), "INCONCLUSIVE")
        case["target"] = {"scope": "gateway", "id": "gateway_01"}
        self.assertEqual(self.state(case).case_status(["client.probe"]), "NEEDS_INPUT")
        self.assertEqual(self.state(case).case_status(["wan.probe"], blocked=True), "BLOCKED")

    def test_exit_ok_with_stale_evidence_leaves_node_inconclusive_and_fact_unknown(self):
        self.case["world"]["wan.status"]["_age_s"] = 100  # contract TTL is 30 s
        state = self.state()
        runner, plan = self.run_goals(["wan.status"], state)
        [contract_b] = runner.contract_b
        self.assertEqual(contract_b["tool_status"], "EXIT_OK")
        self.assertEqual(contract_b["goal_claim"], "NOT_EVALUATED")
        self.assertEqual(plan.nodes["wan.status"].state, NodeState.INCONCLUSIVE)
        self.assertEqual(plan.nodes["wan.status"].failure["type"], "postcondition")
        self.assertIsNone(state.fact("wan.status"))
        self.assertEqual(state.fact_table()["router_wan_link"]["value"], "UNKNOWN")
        record = state.evidence_record(state.evidence[-1])
        self.assertEqual(record["validator"], {"schema": True, "target": True, "fresh": False})
        self.assertEqual(record["assertions"], [])

    def test_advisor_hypothesis_never_reaches_contract_c_facts(self):
        state = self.state()
        self.run_goals(["dns.probe"], state)
        before = (len(state.evidence), state.state_revision)
        statement = "Có thể lỗi DNS phía client"
        state.add_hypothesis(statement)
        contract = state.export_contract_c(["dns.probe", "client.probe"])
        self.assertNotIn(statement, json.dumps(contract, ensure_ascii=False))
        self.assertTrue(all(name.startswith(("router_", "client_")) for name in contract["facts"]))
        self.assertEqual((len(state.evidence), state.state_revision), before)
        self.assertEqual(state.hypotheses[0]["status"], "UNTESTED")

    def test_boot_or_config_change_makes_every_old_fact_unknown(self):
        for change in ({"boot_id": "boot-2"}, {"config_version": "config-2"}):
            with self.subTest(change):
                state = self.state()
                self.run_goals(["dns.probe", "wan.status"], state)
                table = state.fact_table()
                self.assertEqual(table["router_dns_works"]["value"], "FALSE")  # SERVFAIL in this fixture
                self.assertEqual(table["router_wan_link"]["value"], "TRUE")
                revision = state.state_revision
                state.set_environment(**change)
                self.assertTrue(all(row["value"] == "UNKNOWN" for row in state.fact_table().values()))
                self.assertEqual(state.state_revision, revision + 1)

    def test_gateway_observation_never_yields_a_client_fact(self):
        self.case["world"]["dns.probe"] = {"rcode": "NOERROR"}
        registry = GraphRegistry.from_v01()
        case = copy.deepcopy(self.case)
        case["capabilities"] = list(registry.functions)
        state = CaseState(case, registry, lambda: self.now)
        self.run_goals(["dns.probe"], state, case, registry)
        table = state.fact_table()
        self.assertEqual(table["router_dns_works"], {"value": "TRUE", "evidence": [state.fact("dns.probe")["id"]],
                                                      "scope": "gateway", "port": "dns.probe"})
        self.assertEqual((table["client_dns_works"]["value"], table["client_dns_works"]["evidence"]), ("UNKNOWN", []))
        contract = state.export_contract_c(["dns.probe", "client.dns"])
        self.assertEqual(contract["facts"]["client_dns_works"], {"value": "UNKNOWN", "evidence": []})
        self.assertEqual(contract["outstanding_questions"], ["client_dns_works"])
        ports = registry.ports
        for row in ({"fact": "router_dns_works", "scope": "client", "port": "client.dns", "field": "rcode",
                     "op": "eq", "value": "NOERROR"},
                    {"fact": "client_dns_works", "scope": "gateway", "port": "dns.probe", "field": "rcode",
                     "op": "eq", "value": "NOERROR"},
                    {"fact": "client_dns_works", "scope": "client", "port": "dns.probe", "field": "rcode",
                     "op": "eq", "value": "NOERROR"},
                    {"fact": "router_dns_works", "scope": "client", "port": "dns.probe", "field": "rcode",
                     "op": "eq", "value": "NOERROR"}):
            with self.subTest(row), self.assertRaisesRegex(PlanError, "fact_scope_mismatch"):
                fact_assertions([row], ports)

    def test_state_revision_counts_fact_changes_and_outstanding_tracks_goals(self):
        state = self.state()
        goals = ["wan.status", "dns.probe"]
        self.assertEqual(state.state_revision, 0)
        self.assertEqual(state.export_contract_c(goals)["outstanding_questions"],
                         ["router_wan_link", "router_dns_works"])
        self.assertEqual(state.export_contract_c(goals)["decision"], "CONTINUE")
        self.run_goals(["wan.status"], state)
        self.assertEqual(state.state_revision, 1)
        self.assertEqual(state.export_contract_c(goals)["outstanding_questions"], ["router_dns_works"])
        self.assertEqual(state.state_revision, 1)  # reading does not bump the revision
        self.run_goals(["dns.probe"], state)
        self.assertEqual(state.state_revision, 2)
        self.assertEqual(state.export_contract_c(goals)["decision"], "RESOLVED")
        self.now = 1000.0  # TTL expiry changes facts: the next read reflects it
        self.assertEqual(state.export_contract_c(goals)["state_revision"], 3)

    def test_contracts_b_c_and_evidence_records_match_their_schemas(self):
        state = self.state()
        runner, _ = self.run_goals(["dns.probe", "wan.routes"], state)
        self.assertEqual(len(runner.contract_b), 4)
        for contract in runner.contract_b:
            self.assertTrue(valid("contract_b", contract), contract)
        self.assertTrue(valid("contract_c", state.export_contract_c(["dns.probe", "wan.routes"])))
        for e in state.evidence:
            record = state.evidence_record(e)
            self.assertTrue(valid("evidence_record", record), record)
            self.assertEqual(record["case_id"], state.case_id)
        dns = state.evidence_record(state.fact("dns.probe"))
        self.assertEqual(dns["assertions"], [{"fact": "router_dns_works", "value": "FALSE"}])
        self.assertEqual(dns["target"], {"kind": "gateway", "id": "gateway_01"})

    def test_ttl_comes_from_contract_and_observed_at_from_the_injected_clock(self):
        registry = GraphRegistry.from_v01()
        registry.functions["wan.status"].ttl_seconds = 5
        case = copy.deepcopy(self.case)
        case["capabilities"] = list(registry.functions)
        self.now = 90.0
        state = CaseState(case, registry, lambda: self.now)
        self.now = 180.0
        runner, _ = self.run_goals(["wan.status"], state, case, registry)
        e = state.fact("wan.status")
        self.assertEqual((e["ttl_s"], e["ttl_seconds"]), (5, 5))
        self.assertEqual(e["observed_at"], "2026-11-07T00:01:30Z")
        self.assertEqual(state.assertions_for(e), [{"fact": "router_wan_link", "value": "TRUE"}])
        self.now = 186.0
        self.assertIsNone(state.fact("wan.status"))
        self.assertEqual(state.assertions_for(e), [])  # expired evidence asserts nothing
        self.assertNotIn("2026-11-07T00:00:00Z", json.dumps(state.evidence_record(e)))


if __name__ == "__main__":
    unittest.main()
