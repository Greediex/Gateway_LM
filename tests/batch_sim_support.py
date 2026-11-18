"""Shared checks for direct-Skill simulation batches (import the module, not the class,
so unittest discovery does not collect the abstract base)."""
import unittest
from dataclasses import replace
from unittest.mock import patch

from gateway_pilot.skill_expansion.replay_backend import ReplayFixtureError
from gateway_pilot.skill_expansion.simulation import load_scenarios
from scripts.simulate_skills import ROOT, evaluate, run_scenario

__all__ = ["ROOT", "BatchSimulationCase"]


class BatchSimulationCase(unittest.TestCase):
    """Subclasses set SIM, DIAG, SKILLS, BOUNDARIES [(skill, values, verdict)] and BAD."""
    SIM = DIAG = None
    SKILLS = BOUNDARIES = BAD = ()

    @classmethod
    def setUpClass(cls):
        if cls.SIM is None:
            raise unittest.SkipTest("abstract base")
        cls.scenarios = {s.id: s for s in load_scenarios(cls.SIM)}

    def run_values(self, skill, values):
        return run_scenario(replace(self.scenarios[f"{skill}-normal"], values=values), self.DIAG)

    def test_every_skill_has_three_states_and_passes_through_core(self):
        report = evaluate(self.SIM, self.DIAG)
        self.assertEqual((report["passed"], report["total"]), (3 * len(self.SKILLS),) * 2)
        for skill in self.SKILLS:
            self.assertEqual({s.state for s in self.scenarios.values() if s.skill_id == skill},
                             {"normal", "fault", "missing"}, skill)
        for row in report["rows"]:
            if row["id"].endswith("-missing"):
                self.assertEqual((row["outcome"], row["verdict"]), ("NOT_READY", "UNKNOWN"))
            else:
                self.assertEqual(row["outcome"], "VERIFIED")
                self.assertTrue(row["core_calls"] > 0 and row["evidence_id"])

    def test_threshold_boundaries_and_out_of_range_values(self):
        for skill, values, expected in self.BOUNDARIES:
            with self.subTest(skill=skill, values=values):
                result = self.run_values(skill, values)
                self.assertEqual(result["verdict"], expected)
                if expected == "UNKNOWN":
                    # Out-of-range proof is admitted as evidence but supports no Claim.
                    self.assertFalse([c for c in result["claims"].values() if c["value"] == "TRUE"])

    def test_malformed_values_are_rejected_before_any_claim(self):
        for skill, values in self.BAD:
            with self.subTest(skill=skill, values=values), self.assertRaises(ReplayFixtureError):
                self.run_values(skill, values)

    def test_gold_is_never_read_during_execution(self):
        with patch("scripts.simulate_skills.load_claim_gold", side_effect=AssertionError("gold read")), \
                patch("scripts.simulate_skills.load_gold", side_effect=AssertionError("gold read")):
            row = run_scenario(self.scenarios[f"{self.SKILLS[0]}-fault"], self.DIAG)
            self.assertEqual(row["verdict"], "FAULT")

    def test_missing_source_is_unknown_and_never_healthy(self):
        for skill in self.SKILLS:
            row = run_scenario(self.scenarios[f"{skill}-missing"], self.DIAG)
            self.assertEqual((row["outcome"], row["verdict"], row["claims"]), ("NOT_READY", "UNKNOWN", {}), skill)
