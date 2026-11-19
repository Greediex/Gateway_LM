import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.coverage import DIRECT_BATCHES
from gateway_pilot.skill_expansion.simulation import SimulationError, load_scenarios as load_direct
from scripts.simulate_composites import evaluate, run_scenario


class CompositeOSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = contracts("O")
        cls.workflows = cls.doc["workflows"]
        cls.rows = {row["id"]: row for row in load_scenarios("O")}

    def run_normal(self, skill, changes, *, inspect=None):
        row = copy.deepcopy(self.rows[f"{skill}-normal"])
        for alias, fields in changes.items():
            row["sources"][alias]["values"].update(fields)
        return run_scenario(row, batch="O", inspect=inspect)

    def assert_unusable(self, result):
        self.assertEqual(result["verdict"], "UNKNOWN")
        self.assertTrue(result["claims"])
        for claim in result["claims"].values():
            self.assertEqual(claim["value"], "UNKNOWN")
            self.assertEqual(claim["evidence"], [])

    def test_contracts_use_simulated_direct_sources_and_scalar_claims(self):
        skills = {"O01", "O02", "O03", "O06", "O07"}
        self.assertEqual(set(self.workflows), skills)
        self.assertEqual(set(self.rows), {f"{skill}-{case}" for skill in skills
                                         for case in ("normal", "fault", "missing")})
        data_dir = batch_paths("O")[0].parent
        direct_functions = {
            row.function_id for batch in "BCDEFGHIJ"
            for row in load_direct(data_dir / DIRECT_BATCHES[batch][0])
        }
        for skill, workflow in self.workflows.items():
            with self.subTest(skill=skill):
                self.assertTrue(workflow["limitation"].strip())
                self.assertTrue(workflow["require_same_sample_time"])
                function_ids = {spec["function_id"] for spec in workflow["sources"].values()}
                self.assertGreaterEqual(len(function_ids), 2)
                self.assertLessEqual(function_ids, direct_functions)
                claims = [row for row in self.doc["claims"] if row["workflow"] == workflow["workflow_id"]]
                self.assertEqual({row["claim_id"] for row in claims}, set(workflow["claims"]))
                for row in claims:
                    self.assertTrue(row["claim_id"].endswith("_v1"))
                    self.assertEqual(len(row["requires"]), 1)
                    self.assertEqual(row["excludes"], [])
                    predicate, = row["requires"]
                    source = workflow["sources"][predicate["port"]]
                    self.assertIn(predicate["field"], source["value_schema"]["properties"])
                    self.assertIn(predicate["op"], {"eq", "lt", "le", "gt", "ge"})
                    self.assertIn(type(predicate["value"]), {bool, int, float})

    def test_scored_suite_and_original_core_proof_ids(self):
        report = evaluate("O")
        self.assertEqual((report["passed"], report["total"]), (15, 15))
        claim_sources = {row["claim_id"]: row["requires"][0]["port"] for row in self.doc["claims"]}
        for row in self.rows.values():
            with self.subTest(scenario=row["id"]):
                specs = self.workflows[row["skill_id"]]["sources"]
                proofs = {}

                def capture(sources):
                    for alias, source in sources.items():
                        fact = source.state.fact(specs[alias]["function_id"])
                        if fact:
                            self.assertEqual(fact["value"], row["sources"][alias]["values"])
                            proofs[alias] = fact["id"]

                result = run_scenario(row, batch="O", inspect=capture)
                if row["id"].endswith("-missing"):
                    self.assertEqual(sum(s["values"] is None for s in row["sources"].values()), 1)
                    self.assertEqual(len(proofs), len(specs) - 1)
                    self.assert_unusable(result)
                    continue
                self.assertEqual(set(proofs), set(specs))
                self.assertGreaterEqual(result["core_calls"], len(specs))
                self.assertFalse(result["source_errors"])
                positive = {cid: claim for cid, claim in result["claims"].items() if claim["value"] == "TRUE"}
                self.assertTrue(positive)
                for cid, claim in positive.items():
                    self.assertEqual(claim["evidence"], [proofs[claim_sources[cid]]])

    def test_boundary_incomplete_and_mixed_readings(self):
        cases = (
            ("O01", {"signal": {"rssi_dbm": -120, "snr_db": 0}, "upstream": {"loss_pct": 5}}, "HEALTHY"),
            ("O01", {"upstream": {"loss_pct": 5.01}}, "UNKNOWN"),
            ("O01", {"upstream": {"reachable": False, "loss_pct": 99.99}}, "UNKNOWN"),
            ("O02", {"signal": {"rssi_dbm": -75, "snr_db": 20},
                     "airtime": {"channel_utilization_pct": 70}}, "HEALTHY"),
            ("O02", {"signal": {"rssi_dbm": -75.01, "snr_db": 19.99},
                     "airtime": {"channel_utilization_pct": 70.01}}, "FAULT"),
            ("O02", {"signal": {"rssi_dbm": -75.01, "snr_db": 19.99},
                     "airtime": {"channel_utilization_pct": 100}}, "FAULT"),
            ("O02", {"airtime": {"channel_utilization_pct": 70.01}}, "UNKNOWN"),
            ("O03", {"link": {"uptime_seconds": 60}, "events": {"disconnect_events": 3}}, "HEALTHY"),
            ("O03", {"events": {"disconnect_events": 4}}, "FAULT"),
            ("O03", {"events": {"disconnect_events": 9, "observation_window_s": 3599}}, "UNKNOWN"),
            ("O03", {"events": {"disconnect_events": 9, "observation_window_s": 3601}}, "UNKNOWN"),
            ("O03", {"link": {"uptime_seconds": 59}}, "UNKNOWN"),
            ("O03", {"link": {"link_up": False, "uptime_seconds": 0}}, "UNKNOWN"),
            ("O06", {"path": {"latency_ms": 100, "packet_loss_pct": 2}, "jitter": {"jitter_ms": 30}}, "HEALTHY"),
            ("O06", {"path": {"latency_ms": 100.01, "packet_loss_pct": 2.01},
                     "jitter": {"jitter_ms": 30.01}}, "FAULT"),
            ("O06", {"path": {"latency_ms": 101, "packet_loss_pct": 100},
                     "jitter": {"jitter_ms": 31}}, "UNKNOWN"),
            ("O06", {"jitter": {"jitter_ms": 30.01}}, "UNKNOWN"),
            ("O07", {"route": {"default_route_count": 2}, "upstream": {"loss_pct": 5}}, "HEALTHY"),
            ("O07", {"route": {"default_route_count": 0}}, "UNKNOWN"),
            ("O07", {"route": {"default_route": False, "default_route_count": 0}}, "UNKNOWN"),
            ("O07", {"upstream": {"reachable": False, "loss_pct": 100}}, "UNKNOWN"),
        )
        for skill, changes, verdict in cases:
            with self.subTest(skill=skill, changes=changes):
                self.assertEqual(self.run_normal(skill, changes)["verdict"], verdict)

    def test_fields_reject_wrong_types_and_values_outside_their_domains(self):
        for skill, workflow in self.workflows.items():
            for alias, spec in workflow["sources"].items():
                for field, schema in spec["value_schema"]["properties"].items():
                    invalid = [None, "0"]
                    if schema["type"] == "boolean":
                        invalid.append(0)
                    else:
                        invalid.extend([True, schema["minimum"] - 1, float("nan"), float("inf")])
                        if schema["type"] == "integer":
                            invalid.append(1.5)
                        for bound in ("maximum", "exclusiveMaximum"):
                            if bound in schema:
                                invalid.append(schema[bound] + 1)
                    for value in invalid:
                        with self.subTest(skill=skill, alias=alias, field=field, value=value):
                            self.assert_unusable(self.run_normal(skill, {alias: {field: value}}))

    def test_each_source_is_required(self):
        for skill, workflow in self.workflows.items():
            for alias in workflow["sources"]:
                with self.subTest(skill=skill, alias=alias):
                    row = copy.deepcopy(self.rows[f"{skill}-fault"])
                    row["sources"][alias]["values"] = None
                    self.assert_unusable(run_scenario(row, batch="O"))

                    def remove(sources):
                        del sources[alias]

                    result = self.run_normal(skill, {}, inspect=remove)
                    self.assert_unusable(result)
                    self.assertEqual(result["reason"], "missing_or_foreign_source")

    def test_missing_field_times_and_unusable_core_facts(self):
        case = self.rows["O06-normal"]
        row = copy.deepcopy(case)
        del row["sources"]["path"]["values"]["latency_ms"]
        self.assert_unusable(run_scenario(row, batch="O"))
        row = copy.deepcopy(case)
        row["sources"]["path"]["simulated_at"] = "2026-11-19T08:00:01Z"
        self.assertEqual(run_scenario(row, batch="O")["reason"], "different_sample_times")
        for field, value in (("target", "foreign"), ("scope", "client"),
                             ("status", "TIMEOUT"), ("age_s", float("inf"))):
            with self.subTest(field=field):
                def invalidate(sources):
                    fact = sources["path"].state.fact("expansion.latency_loss")
                    fact[field] = value

                self.assert_unusable(run_scenario(case, batch="O", inspect=invalidate))

        def revoke(sources):
            sources["path"].state.permissions.clear()

        self.assert_unusable(run_scenario(case, batch="O", inspect=revoke))

    def test_gold_is_unread_during_execution_and_rejected_in_inputs(self):
        read_text = Path.read_text

        def guard(path, *args, **kwargs):
            self.assertNotEqual(path.name, "gold.json")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", guard):
            for row in load_scenarios("O"):
                run_scenario(row, batch="O")

        directory, diagnostics = batch_paths("O")
        for path, load in ((directory / "scenarios.json", load_scenarios), (diagnostics, contracts)):
            with self.subTest(file=path.name):
                doc = json.loads(read_text(path, encoding="utf-8"))
                if path == diagnostics:
                    holder = doc["workflows"]["O01"]["sources"]["upstream"]["value_schema"]
                else:
                    holder = doc["scenarios"][0]["sources"]["upstream"]["values"]
                holder["expected_verdict"] = "HEALTHY"

                def inject(requested_path, *args, **kwargs):
                    if requested_path == path:
                        return json.dumps(doc)
                    return read_text(requested_path, *args, **kwargs)

                with patch.object(Path, "read_text", inject):
                    with self.assertRaisesRegex(SimulationError, "gold-like"):
                        load("O")
