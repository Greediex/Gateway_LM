"""COV-01 contract and negative-path tests for the 120-Skill inventory."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.skill_expansion.catalog import DATA_DIR
from gateway_pilot.skill_expansion.coverage import (
    ACCEPTANCE, CoverageError, REGISTRY_V01, accepted_skills, build_acceptance,
    build_coverage, classify, inputs_digest, summarize,
)


def _actions(replay=(), live=()):
    table = {"replay": replay, "live": live}
    def actions_for(mode):
        rows = {sid: {"kind": "design"} for sid in table[mode]}
        rows["laptop.wifi.inspect"] = {"kind": "laptop"}
        return rows
    return actions_for


class CoverageInventoryTests(unittest.TestCase):
    def test_real_inventory_is_exact_120_by_15x8(self):
        rows = build_coverage()
        self.assertEqual(len({r.skill_id for r in rows}), 120)
        summary = summarize(rows)
        self.assertEqual(len(summary["by_batch"]), 15)
        self.assertEqual(set(summary["by_batch"].values()), {8})
        self.assertEqual(sum(summary["by_type"].values()), 120)

    def test_laptop_actions_are_not_in_denominator(self):
        rows = build_coverage(actions_for=_actions(live=("SK01",)))
        self.assertNotIn("laptop.wifi.inspect", {r.skill_id for r in rows})
        self.assertEqual(summarize(rows)["levels"]["live_launchable"], 1)

    def test_launchable_is_never_reported_as_verified(self):
        # No acceptance source: launchable alone must never count as verified.
        rows = build_coverage(actions_for=_actions(replay=("B02",), live=("A08",)),
                              acceptance_path=Path("/nonexistent/acceptance.json"))
        levels = summarize(rows)["levels"]
        self.assertEqual((levels["replay_launchable"], levels["live_launchable"]), (1, 1))
        self.assertEqual(levels["simulation_verified"], 0)
        self.assertEqual(levels["router_verified"], 0)
        b02 = next(r for r in rows if r.skill_id == "B02")
        self.assertIn("REPLAY_PENDING_ACCEPTANCE", b02.gaps)

    def test_write_skill_is_change_type_sandbox_only(self):
        sk13 = next(r for r in build_coverage() if r.skill_id == "SK13")
        self.assertEqual(sk13.skill_type, "change")
        self.assertIn("WRITE_SANDBOX_ONLY", sk13.gaps)
        self.assertFalse(sk13.live_launchable)

    def test_existing_dependency_is_hard_and_proposed_kept_separate(self):
        rows = {r.skill_id: r for r in build_coverage()}
        self.assertIn("SK01", rows["SK02"].hard_dependencies)
        for row in rows.values():
            self.assertFalse(set(row.hard_dependencies) & set(row.proposed_dependencies))

    def test_unknown_deployment_skill_is_rejected(self):
        with self.assertRaises(CoverageError):
            build_coverage(actions_for=_actions(replay=("ZZ99",)))

    def test_unknown_proposal_mode_is_rejected(self):
        with self.assertRaises(CoverageError):
            classify(mapping={"skill_id": "X", "proposal_mode": "AUTO"}, stub={}, write_set=())

    def test_missing_skill_in_mapping_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "data"
            shutil.copytree(DATA_DIR, data)
            path = data / "skill_function_mapping_120.json"
            rows = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(rows[1:]), encoding="utf-8")
            with self.assertRaises(CoverageError):
                build_coverage(data_dir=data, registry_path=REGISTRY_V01,
                               actions_for=_actions())


class AcceptanceTests(unittest.TestCase):
    """WP-A5: simulation_verified only from a run-generated, input-pinned file."""

    def _write(self, doc):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "acceptance.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def test_committed_acceptance_matches_a_fresh_run(self):
        from scripts.simulate_skills import evaluate_all
        self.assertEqual(build_acceptance(evaluate_all()["rows"]),
                         json.loads(ACCEPTANCE.read_text(encoding="utf-8")))

    def test_real_coverage_counts_only_accepted_batch_a_and_b_skills(self):
        rows = [r for r in build_coverage() if r.simulation_verified]
        self.assertEqual({r.skill_id for r in rows},
                         {"A02", "A03", "A04", "A05", "A06", "A07", "A08",
                          "B02", "B03", "B04", "B05", "B06", "B07", "B08"})
        self.assertFalse(any(r.router_verified for r in rows))

    def test_hand_edited_failure_or_missing_state_is_not_counted(self):
        doc = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        doc["skills"]["A02"]["fault"]["pass"] = False
        del doc["skills"]["A04"]["missing"]
        doc["skills"]["A06"]["normal"]["core_calls"] = 0
        accepted = accepted_skills(self._write(doc))
        self.assertTrue({"A02", "A04", "A06"}.isdisjoint(accepted))
        self.assertIn("A08", accepted)

    def test_stale_or_foreign_acceptance_fails_closed(self):
        doc = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        with self.assertRaises(CoverageError):
            accepted_skills(self._write({**doc, "inputs_digest": "0" * 64}))
        with self.assertRaises(CoverageError):
            accepted_skills(self._write({**doc, "format": "other"}))
        self.assertEqual(doc["inputs_digest"], inputs_digest())

    def test_unknown_skill_in_acceptance_is_rejected(self):
        doc = json.loads(ACCEPTANCE.read_text(encoding="utf-8"))
        doc["skills"]["ZZ99"] = doc["skills"]["A02"]
        with self.assertRaises(CoverageError):
            build_coverage(acceptance_path=self._write(doc))

    def test_unexpected_or_duplicate_rows_are_rejected(self):
        row = {"id": "A02-normal", "skill_id": "A02", "pass": True, "core_calls": 1, "verdict": "HEALTHY"}
        with self.assertRaises(CoverageError):
            build_acceptance([row, row])
        with self.assertRaises(CoverageError):
            build_acceptance([{**row, "id": "A02-weird"}])


if __name__ == "__main__":
    unittest.main()
