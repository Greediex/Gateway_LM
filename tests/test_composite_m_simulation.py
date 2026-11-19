import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeMEvidenceSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = {row["id"]: row for row in load_scenarios("M")}
        cls.workflow_specs = contracts("M")["workflows"]

    def run_normal(self, skill, changes=None, *, inspect=None):
        row = copy.deepcopy(self.rows[f"{skill}-normal"])
        for alias, fields in (changes or {}).items():
            row["sources"][alias]["values"].update(fields)
        return run_scenario(row, batch="M", inspect=inspect)

    def assert_unusable(self, result):
        self.assertEqual(result["verdict"], "UNKNOWN")
        self.assertTrue(result["claims"])
        for claim in result["claims"].values():
            self.assertEqual(claim["value"], "UNKNOWN")
            self.assertEqual(claim["evidence"], [])

    def test_scored_suite_and_single_field_claims(self):
        skills = {"M03", "M05", "M06", "M08"}
        self.assertEqual(set(self.workflow_specs), skills)
        self.assertEqual(set(self.rows), {f"{skill}-{case}" for skill in skills
                                         for case in ("normal", "fault", "missing")})
        for row in contracts("M")["claims"]:
            self.assertTrue(row["claim_id"].endswith("_v1"))
            self.assertEqual(len(row["requires"]), 1)
            self.assertFalse(row["excludes"])
            comparison, = row["requires"]
            self.assertTrue(comparison["field"])
            self.assertIn(comparison["op"], {"eq", "lt", "le", "gt", "ge"})
            self.assertIn(type(comparison["value"]), {bool, int})
        report = evaluate("M")
        self.assertEqual((report["passed"], report["total"]), (12, 12))
        for row in report["rows"]:
            with self.subTest(scenario=row["id"]):
                self.assertTrue(row["limitation"].strip())
                positive = [c for c in row["claims"].values() if c["value"] == "TRUE"]
                if row["id"].endswith("-missing"):
                    self.assertEqual(row["core_calls"], 1)
                    missing_alias, = (alias for alias, sample in self.rows[row["id"]]["sources"].items()
                                      if sample["values"] is None)
                    function_id = self.workflow_specs[row["skill_id"]]["sources"][missing_alias]["function_id"]
                    self.assertEqual(row["source_errors"], {missing_alias: f"function_not_available:{function_id}"})
                    self.assert_unusable(row)
                    self.assertFalse(positive)
                else:
                    self.assertEqual(row["core_calls"], 2)
                    self.assertFalse(row["source_errors"])
                    self.assertEqual(len(positive), 2 if row["skill_id"] == "M06" else 1)
                    self.assertTrue(all(c["evidence"] for c in positive))

    def test_boundaries_and_disagreement(self):
        cases = (
            ("M03", {"history": {"samples": 0, "window_seconds": 1}}, "FAULT"),
            ("M03", {"history": {"samples": 1}}, "FAULT"),
            ("M03", {"history": {"samples": 2}}, "HEALTHY"),
            ("M03", {"inventory": {"node_count": 1, "edge_count": 0}}, "HEALTHY"),
            ("M03", {"inventory": {"node_count": 0}}, "UNKNOWN"),
            ("M05", {"history": {"samples": 1}}, "UNKNOWN"),
            ("M05", {"history": {"samples": 2, "window_seconds": 1}}, "HEALTHY"),
            ("M05", {"probe": {"reachable": False, "loss_pct": 100}}, "FAULT"),
            ("M06", {"probe": {"loss_pct": 5}, "path": {"packet_loss_pct": 2, "latency_ms": 0}},
             "HEALTHY"),
            ("M06", {"probe": {"loss_pct": 5.01}, "path": {"packet_loss_pct": 2.01}}, "FAULT"),
            ("M06", {"probe": {"loss_pct": 100}, "path": {"packet_loss_pct": 100}}, "FAULT"),
            ("M06", {"probe": {"loss_pct": 5.01}, "path": {"packet_loss_pct": 2}}, "UNKNOWN"),
            ("M06", {"probe": {"loss_pct": 5}, "path": {"packet_loss_pct": 2.01}}, "UNKNOWN"),
            ("M06", {"probe": {"reachable": False, "loss_pct": 100}}, "UNKNOWN"),
            ("M08", {"incidents": {"incident_events": 0, "open_incidents": 0}}, "HEALTHY"),
            ("M08", {"incidents": {"open_incidents": 1}}, "FAULT"),
            ("M08", {"history": {"samples": 1}}, "UNKNOWN"),
        )
        for skill, changes, verdict in cases:
            with self.subTest(skill=skill, changes=changes):
                result = self.run_normal(skill, changes)
                self.assertEqual(result["verdict"], verdict)
                if skill == "M06" and verdict == "UNKNOWN" and "path" in changes:
                    positive = [claim for claim in result["claims"].values() if claim["value"] == "TRUE"]
                    self.assertEqual({claim["severity"] for claim in positive}, {"HEALTHY", "FAULT"})
                    self.assertEqual(len({eid for claim in positive for eid in claim["evidence"]}), 2)

    def test_bad_number_domains_and_types(self):
        cases = (
            ("M03", "inventory", "node_count", (-1, True, "3")),
            ("M03", "inventory", "edge_count", (-1, 1.5)),
            ("M03", "history", "samples", (-1, 2.5, False, None)),
            ("M03", "history", "window_seconds", (-1, 0, "60")),
            ("M05", "probe", "reachable", (0, "false", None)),
            ("M05", "probe", "loss_pct", (-0.01, 100.01, "0")),
            ("M06", "probe", "loss_pct", (-0.01, 100.01, float("nan"))),
            ("M06", "path", "packet_loss_pct", (-0.01, 100.01, True, float("inf"))),
            ("M06", "path", "latency_ms", (-0.01, "25", float("inf"))),
            ("M08", "incidents", "incident_events", (-1, False)),
            ("M08", "incidents", "open_incidents", (-1, "0", 0.5)),
        )
        for skill, alias, field, invalid_values in cases:
            for value in invalid_values:
                with self.subTest(skill=skill, alias=alias, field=field, value=value):
                    self.assert_unusable(self.run_normal(skill, {alias: {field: value}}))

    def test_missing_sources_on_both_sides(self):
        for skill, workflow in self.workflow_specs.items():
            for alias in workflow["sources"]:
                with self.subTest(skill=skill, alias=alias):
                    row = copy.deepcopy(self.rows[f"{skill}-normal"])
                    row["sources"][alias]["values"] = None
                    self.assert_unusable(run_scenario(row, batch="M"))

                    def remove(sources):
                        del sources[alias]

                    result = self.run_normal(skill, inspect=remove)
                    self.assert_unusable(result)
                    self.assertEqual(result["reason"], "missing_or_foreign_source")

    def test_missing_field_and_different_sample_times(self):
        row = copy.deepcopy(self.rows["M08-normal"])
        del row["sources"]["incidents"]["values"]["open_incidents"]
        self.assert_unusable(run_scenario(row, batch="M"))
        row = copy.deepcopy(self.rows["M06-normal"])
        row["sources"]["path"]["simulated_at"] = "2026-11-19T08:00:01Z"
        result = run_scenario(row, batch="M")
        self.assert_unusable(result)
        self.assertEqual(result["reason"], "different_sample_times")

    def test_unusable_core_facts(self):
        for alias, spec in self.workflow_specs["M06"]["sources"].items():
            for defect in ("target", "scope", "permission", "timeout", "stale"):
                with self.subTest(alias=alias, defect=defect):
                    def invalidate(sources):
                        state = sources[alias].state
                        fact = state.fact(spec["function_id"])
                        if defect == "permission":
                            state.permissions.clear()
                        elif defect == "timeout":
                            fact["status"] = "TIMEOUT"
                        elif defect == "stale":
                            fact["age_s"] = fact["ttl_s"] + 1
                        else:
                            fact[defect] = "foreign"

                    result = self.run_normal("M06", inspect=invalidate)
                    self.assert_unusable(result)
                    self.assertEqual(result["reason"], f"unusable_source:{alias}")

    def test_m08_explanation_cites_the_original_incident_fact(self):
        for case in ("normal", "fault"):
            with self.subTest(case=case):
                captured = {}

                def capture(sources):
                    for alias, spec in self.workflow_specs["M08"]["sources"].items():
                        state = sources[alias].state
                        fact = state.fact(spec["function_id"])
                        self.assertIsNotNone(fact)
                        captured[alias] = fact

                row = self.rows[f"M08-{case}"]
                result = run_scenario(row, batch="M", inspect=capture)
                claim, = (claim for claim in result["claims"].values() if claim["value"] == "TRUE")
                self.assertEqual(claim["evidence"], [captured["incidents"]["id"]])
                self.assertEqual(captured["incidents"]["value"], row["sources"]["incidents"]["values"])
                self.assertNotIn(captured["history"]["id"], claim["evidence"])

    def test_gold_is_unread_during_execution_and_rejected_in_inputs(self):
        read_text = Path.read_text

        def guarded_read(path, *args, **kwargs):
            self.assertNotEqual(path.name, "gold.json")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", guarded_read):
            for row in load_scenarios("M"):
                run_scenario(row, batch="M")

        sim_dir, diagnostics = batch_paths("M")
        for path, loader in ((sim_dir / "scenarios.json", load_scenarios), (diagnostics, contracts)):
            with self.subTest(path=path.name):
                doc = json.loads(read_text(path, encoding="utf-8"))
                if path == diagnostics:
                    container = doc["workflows"]["M03"]
                else:
                    container = doc["scenarios"][0]["sources"]["history"]["values"]
                container["expected_verdict"] = "HEALTHY"

                def inject_gold(requested_path, *args, **kwargs):
                    if requested_path == path:
                        return json.dumps(doc)
                    return read_text(requested_path, *args, **kwargs)

                with patch.object(Path, "read_text", inject_gold):
                    with self.assertRaisesRegex(SimulationError, "gold-like"):
                        loader("M")
