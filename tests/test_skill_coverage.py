"""COV-01 contract and negative-path tests for the 120-Skill inventory."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.skill_expansion.catalog import DATA_DIR
from gateway_pilot.skill_expansion.coverage import (
    CoverageError, REGISTRY_V01, build_coverage, classify, summarize,
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
        rows = build_coverage(actions_for=_actions(replay=("B02",), live=("A08",)))
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


if __name__ == "__main__":
    unittest.main()
