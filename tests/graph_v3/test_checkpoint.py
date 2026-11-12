"""Evidence checkpoint integrity, freshness and permission regression tests."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.checkpoint import EvidenceCheckpoint
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry


class EvidenceCheckpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = next(x for x in read_json(ROOT / "data/cases.json") if x["template"] == "wan_healthy")

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "state.json"
        self.registry = GraphRegistry()
        self.request = "WAN status"
        self.goals = ("wan.status",)
        self.time = [10000.0]
        self.store = EvidenceCheckpoint(self.path, b"0123456789abcdef" * 2,
                                        clock=lambda: self.time[0])

    def case(self):
        return copy.deepcopy(self.base)

    def agent(self, store=None):
        return GoalAgent(self.registry, method="bm25",
                         checkpoint=self.store if store is None else store)

    def first_run(self):
        result = self.agent().run(self.request, self.case(), goals=self.goals)
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["checkpoint_facts_saved"], 1)
        return result

    def test_signed_fact_resume_without_world_or_new_tool_invocation(self):
        first = self.first_run()
        next_case = self.case()
        del next_case["world"]
        resumed = self.agent().run(self.request, next_case, goals=self.goals)
        self.assertEqual(resumed["status"], "RESOLVED")
        self.assertEqual(resumed["calls"], 0)
        self.assertEqual(resumed["reason"], "verified_evidence_reused")
        self.assertEqual(resumed["goal_facts"][0]["value"], first["goal_facts"][0]["value"])
        self.assertEqual(resumed["diagnosis"], "NOT_EVALUATED")

    def test_expired_fact_not_resumed(self):
        self.first_run()
        self.time[0] += 31
        next_case = self.case()
        del next_case["world"]
        outcome = self.agent().run(self.request, next_case, goals=self.goals)
        self.assertEqual(outcome["status"], "INCONCLUSIVE")
        self.assertEqual(outcome["calls"], 0)
        self.assertEqual(outcome["reason"], "observation_source_not_configured")

    def test_tampered_or_wrong_signature_fails_closed(self):
        self.first_run()
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        saved["body"]["evidence"][0]["value"]["link_up"] = False
        self.path.write_text(json.dumps(saved), encoding="utf-8")
        with self.assertRaisesRegex(PlanError, "checkpoint_signature_invalid"):
            self.agent().run(self.request, self.case(), goals=self.goals)
        wrong_key = EvidenceCheckpoint(self.path, b"not-the-same-secret" * 2,
                                       clock=lambda: self.time[0])
        with self.assertRaisesRegex(PlanError, "checkpoint_signature_invalid"):
            self.agent(wrong_key).run(self.request, self.case(), goals=self.goals)

    def test_boot_firmware_acl_and_target_changed_prevents_reuse(self):
        self.first_run()
        changed = (
            {"boot_id": "rebooted"},
            {"config_version": "another-version"},
            {"permissions": ["network.read"]},
            {"target": {"scope": "gateway", "id": "different-gateway"}},
        )
        for delta in changed:
            with self.subTest(delta=delta):
                next_case = self.case()
                del next_case["world"]
                next_case.update(copy.deepcopy(delta))
                outcome = self.agent().run(self.request, next_case, goals=self.goals)
                self.assertEqual(outcome["calls"], 0)
                self.assertNotEqual(outcome["status"], "RESOLVED")

    def test_wrong_request_not_used_as_cache_authority(self):
        self.first_run()
        next_case = self.case()
        del next_case["world"]
        outcome = self.agent().run("other question", next_case, goals=self.goals)
        self.assertEqual(outcome["status"], "INCONCLUSIVE")

    def test_clock_rollback_rejected(self):
        self.first_run()
        self.time[0] -= 5
        with self.assertRaisesRegex(PlanError, "checkpoint_clock_rollback"):
            self.agent().run(self.request, self.case(), goals=self.goals)

    def test_short_or_untrusted_secret_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceCheckpoint(self.path, b"weak")


if __name__ == "__main__":
    unittest.main()
