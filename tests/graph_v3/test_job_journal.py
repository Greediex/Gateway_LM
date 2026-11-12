"""Signed read-only step journal, restart trace and tampering regression tests."""
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
from gateway_pilot.graph_v3.job_journal import ReadOnlyJobJournal


class JobJournalTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.path = Path(self.dir.name) / "audit.json"
        self.checkpoint_path = Path(self.dir.name) / "facts.json"
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(
            x for x in read_json(ROOT / "data/cases.json")
            if x["template"] == "wan_healthy"
        ))
        self.key = b"0123456789abcdef" * 2
        self.journal = ReadOnlyJobJournal(self.path, self.key)
        self.checkpoint = EvidenceCheckpoint(self.checkpoint_path, self.key,
                                             clock=lambda: 10000.0)

    def agent(self, **kwargs):
        return GoalAgent(self.registry, method="bm25",
                         journal=self.journal, **kwargs)

    def run_once(self):
        result = self.agent().run(
            "WAN status and RAM", copy.deepcopy(self.case),
            goals=("wan.status", "system.resources")
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["calls"], 2)
        return result

    def test_journal_logs_read_steps_without_raw_values_and_survives_restart(self):
        first = self.run_once()
        self.assertEqual(len(first["journal_events"]), 2)
        self.assertTrue(all(row["state"] == "SUCCEEDED"
                            for row in first["journal_events"]))
        envelope = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(envelope["version"], 1)
        self.assertEqual(len(envelope["entries"]), 2)
        self.assertNotIn("WAN status and RAM", str(envelope))
        self.assertNotIn("link_up", str(envelope))
        self.assertTrue(envelope["entries"][1]["previous"] ==
                        envelope["entries"][0]["mac"])
        result = self.agent(checkpoint=self.checkpoint).run(
            "WAN status and RAM", copy.deepcopy(self.case),
            goals=("wan.status", "system.resources")
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(len(result["journal_events"]), 4)
        self.assertEqual(result["calls"], 2)

    def test_checkpoint_and_journal_restore_verified_facts_without_new_calls(self):
        agent = self.agent(checkpoint=self.checkpoint)
        first = agent.run(
            "WAN status and RAM", copy.deepcopy(self.case),
            goals=("wan.status", "system.resources"),
        )
        self.assertEqual(first["calls"], 2)
        restarted = copy.deepcopy(self.case)
        restarted.pop("world", None)
        second = self.agent(checkpoint=self.checkpoint).run(
            "WAN status and RAM", restarted,
            goals=("wan.status", "system.resources"),
        )
        self.assertEqual(second["calls"], 0)
        self.assertEqual(second["reason"], "verified_evidence_reused")
        self.assertEqual(len(second["journal_events"]), 2)
        self.assertEqual(second["diagnosis"], "NOT_EVALUATED")

    def test_changed_registry_boot_and_acl_fail_closed(self):
        self.run_once()
        for change in (
            {"boot_id": "restarted"},
            {"config_version": "updated"},
            {"permissions": ["system.read"]},
        ):
            with self.subTest(change=change):
                changed_case = copy.deepcopy(self.case)
                changed_case.update(change)
                with self.assertRaisesRegex(PlanError, "journal_binding_mismatch"):
                    self.agent().run(
                        "WAN status and RAM", changed_case,
                        goals=("wan.status", "system.resources"),
                    )

    def test_tampering_and_wrong_secret_rejected(self):
        self.run_once()
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        rows["entries"][0]["event"]["state"] = "FAILED"
        self.path.write_text(json.dumps(rows), encoding="utf-8")
        with self.assertRaisesRegex(PlanError, "journal_signature_invalid"):
            self.agent().run(
                "WAN status and RAM", copy.deepcopy(self.case),
                goals=("wan.status", "system.resources"),
            )
        self.journal = ReadOnlyJobJournal(self.path, b"wrong-key" * 4)
        with self.assertRaisesRegex(PlanError, "journal_signature_invalid"):
            self.agent().run(
                "WAN status and RAM", copy.deepcopy(self.case),
                goals=("wan.status", "system.resources"),
            )

    def test_journal_budget_bounded_and_invalid_secret_refused(self):
        with self.assertRaises(ValueError):
            ReadOnlyJobJournal(self.path, b"weak")
        self.journal = ReadOnlyJobJournal(self.path, self.key, max_events=1)
        with self.assertRaisesRegex(PlanError, "runner_audit_sink_failed"):
            self.agent().run(
                "WAN status and RAM", copy.deepcopy(self.case),
                goals=("wan.status", "system.resources"),
            )
        rows = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(len(rows["entries"]), 1)


if __name__ == "__main__":
    unittest.main()
