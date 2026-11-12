"""C4: data-driven claim contracts, claim-based case status, and sessions that keep one Case."""
import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot import workflow as wf
from gateway_pilot.assistant import answer
from gateway_pilot.core import DIAGNOSES, ROOT, PlanError, read_json, support
from gateway_pilot.graph_v3.claims import ClaimBook, claim_book
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.session import SessionStore

CASES = read_json(ROOT / "data/cases.json")
REFERENCE = [d for d in DIAGNOSES if d not in {"insufficient_evidence", "target_ambiguous", "unsafe_change_denied",
                                               "client_path_unverified"}]


def two_device_replay(registry):
    fixture = next(c for c in CASES if c["id"] == "GLM-21-1")
    replay = wf.replay_from_fixture(fixture, registry)
    phone = copy.deepcopy(replay["devices"][0])
    phone.update(selector="my-phone", aliases=[], client_id="client_phone")
    phone["world"]["clients.resolve"] = {"client_id": "client_phone"}
    replay["devices"].append(phone)
    return replay


class ClaimContractTests(unittest.TestCase):
    def test_claims_agree_with_support_at_every_proof_on_all_72_cases(self):
        checks, mismatches, original = [0], [], wf.Diagnostic.proof

        def proof(diag, *diagnoses):
            book = claim_book(diag.runner.registry)
            for name in REFERENCE:
                ok, ids = support(name, diag.state, diag.case)
                truth, claim_ids = book.support(name, diag.state, diag.case.get("workflow"))
                checks[0] += 1
                if (ok and bool(ids)) != truth or (truth and ids != claim_ids):
                    mismatches.append((diag.case["request"], name))
            return original(diag, *diagnoses)

        registry = wf.workflow_registry()
        self.assertEqual(len(CASES), 72)
        with patch.object(wf.Diagnostic, "proof", proof):
            for case in CASES:
                wf.diagnose(case["request"], wf.replay_from_fixture(case, registry), registry=registry,
                            route="fastpath")
        self.assertGreater(checks[0], 1000)
        self.assertEqual(mismatches, [])

    def test_case_status_comes_from_claim_scope_and_severity(self):
        book = claim_book(GraphRegistry.from_v01())
        self.assertEqual(book.status("wan_link_down", "FINISH", "WF-018"), "RESOLVED")
        self.assertEqual(book.status("wan_link_down", "FINISH", "WF-INTERNET"), "PARTIAL")  # router proof, client question
        self.assertEqual(book.status("wan_link_down", "FINISH", "WF-023"), "PARTIAL")  # partial_claims
        self.assertEqual(book.status("gateway_dns_failure", "FINISH", "WF-023"), "RESOLVED")
        self.assertEqual(book.status("client_no_lease", "FINISH", "WF-024"), "PARTIAL")  # OBSERVATION
        self.assertEqual(book.status("wifi_weak_signal", "FINISH", "WF-INTERNET"), "RESOLVED")
        self.assertIsNone(book.status("insufficient_evidence", "INCOMPLETE", "WF-018"))

    def test_terminal_verdict_without_a_true_claim_is_downgraded(self):
        registry = wf.workflow_registry()
        case = next(c for c in CASES if c["template"] == "dns_fail")
        diag = wf.Diagnostic({**case, "workflow": "WF-023", "target": {"scope": "gateway", "id": "gateway_01"},
                              "initial_evidence": []}, registry, "gos", 12, None)
        claimed = wf.verdict("FINISH", "wan_link_down", ["e9"])  # nothing measured
        self.assertEqual(wf.verify_terminal(claimed, diag)["diagnosis"], "insufficient_evidence")
        diag.observe("wan.status", "test")
        diag.observe("wan.routes", "test")
        verified = wf.verify_terminal(wf.verdict("FINISH", "wan_no_route", []), diag)
        self.assertEqual(verified["diagnosis"], "insufficient_evidence")  # this fixture's route is present
        unclaimed = wf.verdict("ASK_USER", "target_ambiguous")
        self.assertIs(wf.verify_terminal(unclaimed, diag), unclaimed)

    def test_boolean_and_numeric_comparisons_are_type_strict(self):
        from gateway_pilot.graph_v3.claims import _compare
        self.assertFalse(_compare(1, "eq", True))
        self.assertFalse(_compare(0, "eq", False))
        self.assertTrue(_compare(False, "eq", False))
        self.assertTrue(_compare(0.0, "eq", 0))
        self.assertFalse(_compare(True, "ge", 1))
        self.assertFalse(_compare("SERVFAIL ", "in", ["SERVFAIL"]))

    def test_observed_does_not_conclude_when_its_claim_is_not_true(self):
        registry = wf.workflow_registry()
        case = next(c for c in CASES if c["id"] == "GLM-21-1")
        replay = wf.replay_from_fixture(case, registry)
        device = replay["devices"][0]
        diag = wf.Diagnostic({"request": case["request"], "workflow": "WF-INTERNET",
                              "target": {"scope": "client", "selector": device["selector"],
                                         "client_id": device["client_id"]},
                              "world": {**replay["world"], **device["world"]},
                              "capabilities": replay["capabilities"], "initial_evidence": []},
                             registry, "gos", 12, None)
        diag.observe("wifi.station", "test")
        self.assertIs(diag.state.fact("wifi.station")["value"]["associated"], True)
        self.assertIsNone(diag.observed("FINISH", "client_not_associated", "wifi.station"))

    def test_claim_book_rejects_bad_contracts(self):
        ports = GraphRegistry.from_v01().ports
        base = {"claim_id": "x", "diagnosis": "x", "scope": "gateway", "severity": "FAULT", "excludes": [],
                "message_key": "x", "requires": [{"port": "wan.status", "field": "link_up", "op": "eq", "value": False}]}
        for change, code in [({"severity": "MAYBE"}, "invalid_claim"),
                             ({"requires": [{"port": "nope", "field": "", "op": "exists"}]}, "invalid_claim_requirement"),
                             ({"requires": [{"port": "wan.probe", "field": "loss_pct", "op": "gt", "value": "50"}]},
                              "invalid_claim_requirement"),
                             ({"requires": []}, "claim_without_requirements")]:
            with self.subTest(code), self.assertRaisesRegex(PlanError, code):
                ClaimBook([{**base, **change}], ports, {})
        with self.assertRaisesRegex(PlanError, "partial_claim_outside_workflow"):
            ClaimBook([base], ports, {"WF-X": {"target_scope": "gateway", "claims": ["x"], "partial_claims": ["y"]}})
        with self.assertRaisesRegex(PlanError, "workflow_claim_without_contract"):
            ClaimBook([base], ports, {"WF-X": {"target_scope": "gateway", "claims": ["x", "ghost"]}})

    def test_next_best_action_stays_inside_candidates_and_prefers_open_predicates(self):
        registry = wf.workflow_registry()
        case = next(c for c in CASES if c["template"] == "dns_fail")
        diag = wf.Diagnostic({**case, "workflow": "WF-018", "target": {"scope": "gateway", "id": "gateway_01"},
                              "initial_evidence": []}, registry, "gos", 12, None)
        book = diag.claims
        self.assertEqual(book.next_best_action(registry, diag.state, "WF-018", ["dns.config", "wan.status"]),
                         "wan.status")
        self.assertIsNone(book.next_best_action(registry, diag.state, "WF-018", ["dns.config"]))
        result = wf.diagnose(case["request"], wf.replay_from_fixture(case, registry), registry=registry,
                             route="resolver", workflow="WF-018", selection="nba")
        self.assertIn(result["case_status"], {"RESOLVED", "PARTIAL", "INCONCLUSIVE"})
        with self.assertRaisesRegex(ValueError, "invalid_selection"):
            wf.diagnose(case["request"], wf.replay_from_fixture(case, registry), registry=registry,
                        route="resolver", selection="llm")


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry.from_v01()
        self.replay = two_device_replay(self.registry)
        self.store = SessionStore()

    def executed(self, result):
        return [e["function_id"] for e in result.get("graph", {}).get("executed", [])]

    def test_follow_up_to_another_device_reuses_fresh_wan_facts(self):
        session = self.store.get()
        first = answer("laptop-an vẫn có Wi-Fi mà không vào được mạng", self.replay,
                       registry=self.registry, session=session)
        self.assertIn("wan.probe", self.executed(first))
        second = answer("còn my-phone thì sao", self.replay, registry=self.registry, session=session)
        self.assertEqual(second["turn_type"], "FOLLOW_UP")
        self.assertEqual(second["workflow"], "WF-INTERNET")
        self.assertFalse([f for f in self.executed(second) if f.startswith(("wan.", "dns."))])
        self.assertEqual(second["target"]["selector"], "my-phone")
        self.assertEqual(len(session.history), 2)

    def test_old_device_client_facts_are_not_used_for_the_new_device(self):
        session = self.store.get()
        answer("laptop-an vẫn có Wi-Fi mà không vào được mạng", self.replay, registry=self.registry, session=session)
        laptop_ids = {e["id"] for e in session.evidence if e["scope"] == "client"}
        self.assertTrue(laptop_ids)
        # Only the current verified observation per port/target is carried.
        self.assertTrue(all(e["status"] == "OK" and not e.get("_invalidated") for e in session.evidence))
        keys = [(e["port"], e["target"]) for e in session.evidence]
        self.assertEqual(len(keys), len(set(keys)))
        second = answer("còn my-phone thì sao", self.replay, registry=self.registry, session=session)
        client = [e for e in second["graph"]["evidence"] if e["scope"] == "client"]
        self.assertTrue(client)
        self.assertEqual({e["target"] for e in client}, {"client_phone"})
        self.assertIn("clients.resolve", self.executed(second))  # the new device is identified afresh

    def test_reply_to_a_device_question_continues_the_waiting_case(self):
        session = self.store.get()
        asked = answer("sao máy tôi có wifi mà không vào được internet", self.replay,
                       registry=self.registry, session=session)
        self.assertEqual(asked["case_status"], "NEEDS_INPUT")
        self.assertEqual(session.status, "WAITING_INPUT")
        reply = answer("my-phone", self.replay, registry=self.registry, session=session)
        self.assertEqual(reply["turn_type"], "FOLLOW_UP")
        self.assertEqual(reply["target"]["selector"], "my-phone")
        self.assertEqual(session.request, "sao máy tôi có wifi mà không vào được internet")
        self.assertNotEqual(session.status, "WAITING_INPUT")

    def test_session_carries_only_current_verified_observations(self):
        session = self.store.get()
        result = wf.diagnose("laptop-an vẫn có Wi-Fi mà không vào được mạng", self.replay,
                             registry=self.registry, return_state=True)
        state = result["case_state"]
        good = state.fact("wan.status")
        stale = dict(copy.deepcopy(good), id="old", _invalidated=True)
        failed = dict(copy.deepcopy(good), id="bad", status="TIMEOUT")
        state.evidence.insert(0, stale)
        state.evidence.append(failed)  # newest wan.status observation failed: no wan.status fact now
        session.remember(result, request="x")
        carried = {e["id"].split(".", 1)[1] for e in session.evidence}
        self.assertFalse({"old", "bad", good["id"]} & carried)
        self.assertIn(state.fact("dns.probe")["id"], carried)

    def test_expired_session_starts_a_new_case(self):
        now = [0.0]
        store = SessionStore(ttl_s=60, clock=lambda: now[0])
        session = store.get()
        answer("laptop-an vẫn có Wi-Fi mà không vào được mạng", self.replay, registry=self.registry, session=session)
        self.assertIs(store.get(session.session_id), session)
        now[0] = 61.0
        fresh = store.get(session.session_id)
        self.assertNotEqual(fresh.session_id, session.session_id)
        self.assertIsNone(fresh.request)
        self.assertEqual(fresh.evidence, [])
        other = store.get(fresh.session_id, environment="replay:GLM-01-0")
        self.assertIs(other, fresh)  # same session, new environment -> Case reset
        self.assertEqual(other.environment, "replay:GLM-01-0")

    def test_web_sends_session_id_instead_of_concatenating_questions(self):
        app = (ROOT / "web_gateway/static/app.js").read_text(encoding="utf-8")
        self.assertNotIn("lastQuestion", app)
        self.assertIn("session_id:state.sessionId", app)
        sys.path.insert(0, str(ROOT / "web_gateway"))
        try:
            import server
        finally:
            sys.path.remove(str(ROOT / "web_gateway"))
        first = server.analyze({"message": "Sao máy tôi có Wi-Fi mà không vào được Internet?",
                                "fixture_id": "GLM-21-1", "method": "bm25"})
        self.assertEqual(first["case_status"], "NEEDS_INPUT")
        second = server.analyze({"message": "laptop-an", "fixture_id": "GLM-21-1", "method": "bm25",
                                 "session_id": first["session_id"]})
        self.assertEqual(second["session_id"], first["session_id"])
        self.assertEqual(second["request"], first["request"])
        self.assertNotEqual(second["case_status"], "NEEDS_INPUT")


if __name__ == "__main__":
    unittest.main()
