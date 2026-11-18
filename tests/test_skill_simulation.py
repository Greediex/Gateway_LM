"""COV-02 scenario dataset: contract, negative paths and shared-Core run."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.skill_expansion.simulation import (
    SIM_DIR, SimulationError, load_gold, load_scenarios,
)


class _Copy:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        shutil.copytree(SIM_DIR, self.dir, dirs_exist_ok=True)
        self.doc = json.loads((self.dir / "scenarios.json").read_text(encoding="utf-8"))
        return self

    def save(self):
        (self.dir / "scenarios.json").write_text(json.dumps(self.doc), encoding="utf-8")

    def __exit__(self, *exc):
        self._tmp.cleanup()


class ScenarioLoaderTests(unittest.TestCase):
    def test_dataset_has_all_three_states_per_skill(self):
        rows = load_scenarios()
        by_skill = {}
        for r in rows:
            by_skill.setdefault(r.skill_id, set()).add(r.state)
        self.assertTrue(by_skill)
        for states in by_skill.values():
            self.assertEqual(states, {"normal", "fault", "missing"})
        self.assertEqual(set(load_gold(rows)), {r.id for r in rows})

    def test_schema_violation_rejected(self):
        with _Copy() as c:
            c.doc["scenarios"][0]["values"] = {"devices_count": "three", "segment": "x"}
            c.save()
            with self.assertRaisesRegex(SimulationError, "schema"):
                load_scenarios(c.dir)

    def test_gold_leak_into_scenarios_rejected(self):
        with _Copy() as c:
            c.doc["scenarios"][0]["values"] = None
            c.doc["expected_outcome"] = "VERIFIED"
            c.save()
            with self.assertRaisesRegex(SimulationError, "gold-like"):
                load_scenarios(c.dir)

    def test_missing_state_must_have_null_values(self):
        with _Copy() as c:
            c.doc["scenarios"][2]["values"] = {"devices_count": 1, "segment": "x"}
            c.save()
            with self.assertRaisesRegex(SimulationError, "null iff"):
                load_scenarios(c.dir)

    def test_unknown_function_and_duplicate_id_rejected(self):
        with _Copy() as c:
            c.doc["scenarios"][0]["function_id"] = "expansion.rm_rf"
            c.save()
            with self.assertRaisesRegex(SimulationError, "unknown function"):
                load_scenarios(c.dir)
        with _Copy() as c:
            c.doc["scenarios"][1]["id"] = c.doc["scenarios"][0]["id"]
            c.save()
            with self.assertRaisesRegex(SimulationError, "duplicate"):
                load_scenarios(c.dir)

    def test_gold_must_match_scenarios(self):
        with _Copy() as c:
            rows = load_scenarios(c.dir)
            gold = json.loads((c.dir / "gold_v1.json").read_text(encoding="utf-8"))
            gold["expected"].pop(rows[0].id)
            (c.dir / "gold_v1.json").write_text(json.dumps(gold), encoding="utf-8")
            with self.assertRaises(SimulationError):
                load_gold(rows, c.dir)


class SharedCoreSimulationTests(unittest.TestCase):
    def test_all_scenarios_score_against_gold_through_core(self):
        from scripts.simulate_skills import evaluate
        report = evaluate()
        self.assertEqual(report["passed"], report["total"], report["rows"])
        missing = [r for r in report["rows"] if r["id"].endswith("-missing")]
        self.assertTrue(missing)
        self.assertTrue(all(r["outcome"] == "NOT_READY" and "evidence_id" not in r for r in missing))


if __name__ == "__main__":
    unittest.main()
