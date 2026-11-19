import copy
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.coverage import DIRECT_BATCHES
from gateway_pilot.skill_expansion.simulation import load_scenarios as load_direct
from scripts.simulate_composites import evaluate, run_scenario


class CompositeSSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.diagnostics = contracts("S")
        cls.workflows = cls.diagnostics["workflows"]
        cls.rows = {row["id"]: row for row in load_scenarios("S")}

    def assert_unusable(self, result):
        self.assertEqual(result["verdict"], "UNKNOWN")
        self.assertTrue(result["claims"])
        for claim in result["claims"].values():
            self.assertEqual((claim["value"], claim["evidence"]), ("UNKNOWN", []))

    def test_contracts_reuse_direct_functions_and_scalar_claims(self):
        expected = {
            "SK02": {"A08", "B04"},
            "SK04": {"E02", "E03", "E08"},
            "SK08": {"H03", "H05"},
        }
        directory = batch_paths("S")[0].parent
        functions = {
            row.skill_id: row.function_id
            for batch in "ABEH"
            for row in load_direct(directory / DIRECT_BATCHES[batch][0])
        }
        self.assertEqual(set(self.workflows), set(expected))
        self.assertEqual(set(self.rows), {f"{skill}-{case}" for skill in expected
                                         for case in ("normal", "fault", "missing")})
        for skill, workflow in self.workflows.items():
            with self.subTest(skill=skill):
                self.assertEqual({spec["function_id"] for spec in workflow["sources"].values()},
                                 {functions[sid] for sid in expected[skill]})
                self.assertTrue(workflow["limitation"].strip())
                self.assertTrue(workflow["require_same_sample_time"])
                claims = [claim for claim in self.diagnostics["claims"]
                          if claim["workflow"] == workflow["workflow_id"]]
                self.assertEqual({claim["claim_id"] for claim in claims}, set(workflow["claims"]))
                for claim in claims:
                    self.assertTrue(claim["claim_id"].endswith("_v1"))
                    self.assertEqual(claim["excludes"], [])
                    self.assertEqual(len(claim["requires"]), 1)
                    predicate = claim["requires"][0]
                    source = workflow["sources"][predicate["port"]]
                    self.assertIn(predicate["field"], source["value_schema"]["properties"])
                    self.assertIn(predicate["op"], {"lt", "le", "gt", "ge"})
                    self.assertIn(type(predicate["value"]), {int, float})
                for source in workflow["sources"].values():
                    for field in source["value_schema"]["properties"].values():
                        if field["type"] in {"integer", "number"}:
                            self.assertLessEqual(field["minimum"], field["maximum"])

    def test_scenarios_score_and_claims_reference_original_core_evidence(self):
        report = evaluate("S")
        self.assertEqual((report["passed"], report["total"]), (9, 9))
        claim_aliases = {claim["claim_id"]: claim["requires"][0]["port"]
                         for claim in self.diagnostics["claims"]}
        read_text = Path.read_text

        def guard(path, *args, **kwargs):
            self.assertNotEqual(path.name, "gold.json")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", guard):
            for row in load_scenarios("S"):
                with self.subTest(scenario=row["id"]):
                    specs = self.workflows[row["skill_id"]]["sources"]
                    proofs = {}

                    def capture(sources):
                        for alias, source in sources.items():
                            fact = source.state.fact(specs[alias]["function_id"])
                            if fact:
                                self.assertEqual(fact["value"], row["sources"][alias]["values"])
                                proofs[alias] = fact["id"]

                    result = run_scenario(row, batch="S", inspect=capture)
                    omitted = {alias for alias, sample in row["sources"].items()
                               if sample["values"] is None}
                    self.assertEqual(set(proofs), set(specs) - omitted)
                    self.assertGreaterEqual(result["core_calls"], len(proofs))
                    if row["id"].endswith("-missing"):
                        self.assertEqual(len(omitted), 1)
                        self.assert_unusable(result)
                        continue
                    self.assertFalse(omitted)
                    self.assertFalse(result["source_errors"])
                    true_claims = {cid: claim for cid, claim in result["claims"].items()
                                   if claim["value"] == "TRUE"}
                    self.assertTrue(true_claims)
                    for cid, claim in true_claims.items():
                        self.assertEqual(claim["evidence"], [proofs[claim_aliases[cid]]])

    def test_boundaries_scope_and_mixed_readings(self):
        cases = (
            ("SK02", "signal", {"rssi_dbm": -75, "snr_db": 20}, "HEALTHY"),
            ("SK02", "signal", {"rssi_dbm": -75.01, "snr_db": 19.99}, "FAULT"),
            ("SK02", "signal", {"rssi_dbm": -76}, "UNKNOWN"),
            ("SK02", "signal", {"snr_db": 121}, "UNKNOWN"),
            ("SK02", "association", {"associated": False}, "UNKNOWN"),
            ("SK02", "association", {"access_point_id": " "}, "UNKNOWN"),
            ("SK04", "link", {"uptime_seconds": 60}, "HEALTHY"),
            ("SK04", "link", {"uptime_seconds": 59}, "UNKNOWN"),
            ("SK04", "route", {"default_route": False, "default_route_count": 0}, "UNKNOWN"),
            ("SK04", "route", {"default_route_count": 2}, "UNKNOWN"),
            ("SK04", "upstream", {"loss_pct": 5}, "HEALTHY"),
            ("SK04", "upstream", {"loss_pct": 5.01}, "FAULT"),
            ("SK04", "upstream", {"loss_pct": 100}, "UNKNOWN"),
            ("SK04", "upstream", {"reachable": False, "loss_pct": 99}, "UNKNOWN"),
            ("SK08", "storage", {"used_pct": 89.99}, "HEALTHY"),
            ("SK08", "temperature", {"celsius": 84.99}, "HEALTHY"),
            ("SK08", "storage", {"used_pct": 90}, "UNKNOWN"),
            ("SK08", "temperature", {"celsius": 85}, "UNKNOWN"),
            ("SK08", "temperature", {"celsius": 126}, "UNKNOWN"),
        )
        for skill, alias, changes, verdict in cases:
            with self.subTest(skill=skill, alias=alias, changes=changes):
                row = copy.deepcopy(self.rows[f"{skill}-normal"])
                row["sources"][alias]["values"].update(changes)
                self.assertEqual(run_scenario(row, batch="S")["verdict"], verdict)

    def test_each_source_is_required(self):
        for skill, workflow in self.workflows.items():
            for alias in workflow["sources"]:
                with self.subTest(skill=skill, alias=alias):
                    row = copy.deepcopy(self.rows[f"{skill}-fault"])
                    row["sources"][alias]["values"] = None
                    self.assert_unusable(run_scenario(row, batch="S"))

    def test_core_fact_checks_and_bad_samples_fail_closed(self):
        row = self.rows["SK04-normal"]
        for field, value in (("target", "foreign"), ("scope", "client"),
                             ("status", "TIMEOUT"), ("age_s", float("inf"))):
            with self.subTest(field=field):
                def invalidate(sources):
                    fact = sources["upstream"].state.fact("expansion.upstream_probe")
                    fact[field] = value

                self.assert_unusable(run_scenario(row, batch="S", inspect=invalidate))

        def revoke(sources):
            sources["route"].state.permissions.clear()

        self.assert_unusable(run_scenario(row, batch="S", inspect=revoke))
        malformed = copy.deepcopy(row)
        malformed["sources"]["upstream"]["values"]["loss_pct"] = "5"
        self.assert_unusable(run_scenario(malformed, batch="S"))
        skewed = copy.deepcopy(row)
        skewed["sources"]["upstream"]["simulated_at"] = "2026-11-19T09:00:01Z"
        result = run_scenario(skewed, batch="S")
        self.assert_unusable(result)
        self.assertEqual(result["reason"], "different_sample_times")
