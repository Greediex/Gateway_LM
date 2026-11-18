"""WP-S2: scaffold worksheets are skeletons only: no gold, never loadable as real scenarios."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from gateway_pilot.skill_expansion.simulation import PORTS_DIR, _no_gold
from scripts.scaffold_batch import worksheet

ROOT = Path(__file__).resolve().parents[1]
LETTERS = "ABCDEFGHIJKLMNO"


class ScaffoldBatchTests(unittest.TestCase):
    def test_every_batch_builds_with_eight_unique_skills(self):
        for letter in LETTERS:
            sheet = worksheet(letter)
            ids = [s["skill_id"] for s in sheet["skills"]]
            self.assertEqual(len(ids), 8, letter)
            self.assertEqual(len(set(ids)), 8, letter)
            self.assertTrue(sheet["skeleton_only"])

    def test_worksheet_never_contains_gold_like_keys(self):
        for letter in LETTERS:
            sheet = worksheet(letter)
            for skill in sheet["skills"]:
                declared = frozenset(skill.get("claim_fields", {}))
                _no_gold(skill, f"worksheet-{letter}.{skill['skill_id']}", declared)

    def test_port_field_named_expected_is_allowed_only_when_declared(self):
        from gateway_pilot.skill_expansion.simulation import SimulationError
        _no_gold({"expected_routes": []}, "x", frozenset({"expected_routes"}))
        with self.assertRaises(SimulationError):
            _no_gold({"expected_routes": []}, "x")
        with self.assertRaises(SimulationError):
            _no_gold({"expected_routes": [], "verdict": "ok"}, "x", frozenset({"expected_routes"}))

    def test_stub_values_cannot_pass_port_schema(self):
        stubs = 0
        for letter in LETTERS:
            for skill in worksheet(letter)["skills"]:
                for sc in skill.get("scenarios", []):
                    self.assertEqual((sc["state"] == "missing"), sc["values"] is None)
                    if sc["values"] is None:
                        continue
                    stubs += 1
                    schema = json.loads((PORTS_DIR / f"{sc['function_id']}.json").read_text())["schema"]
                    self.assertFalse(Draft202012Validator(schema).is_valid(sc["values"]), sc["id"])
        self.assertGreater(stubs, 0)

    def test_direct_skills_get_three_states_and_others_get_design_notes(self):
        for skill in worksheet("B")["skills"]:
            if "scenarios" in skill:
                self.assertEqual([s["state"] for s in skill["scenarios"]], ["normal", "fault", "missing"])
                self.assertEqual({s["id"] for s in skill["scenarios"]},
                                 {skill["skill_id"] + "-" + x for x in ("normal", "fault", "missing")})
            else:
                self.assertIn("needs", skill)
        composite = [s for s in worksheet("O")["skills"]]
        self.assertTrue(all("scenarios" not in s and "no fake READ Function" in s["needs"] for s in composite))

    def test_unknown_batch_is_rejected_and_cli_writes_file(self):
        for bad in ("Z", "", "AA", "1"):
            with self.assertRaises(ValueError):
                worksheet(bad)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "b.json"
            run = subprocess.run([sys.executable, "-m", "scripts.scaffold_batch", "b", "--out", str(out)],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(out.read_text())["batch"], "COV-B")
            bad = subprocess.run([sys.executable, "-m", "scripts.scaffold_batch", "Z"],
                                 cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(bad.returncode, 0)


if __name__ == "__main__":
    unittest.main()
