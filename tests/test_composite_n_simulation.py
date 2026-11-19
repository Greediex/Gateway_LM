import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeNSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = contracts("N")
        cls.workflows = cls.doc["workflows"]
        cls.rows = {row["id"]: row for row in load_scenarios("N")}

    def run_normal(self, skill, changes):
        row = copy.deepcopy(self.rows[f"{skill}-normal"])
        for alias, fields in changes.items():
            row["sources"][alias]["values"].update(fields)
        return run_scenario(row, batch="N")

    def assert_unusable(self, result):
        self.assertEqual(result["verdict"], "UNKNOWN")
        self.assertTrue(result["claims"])
        for claim in result["claims"].values():
            self.assertEqual(claim["value"], "UNKNOWN")
            self.assertEqual(claim["evidence"], [])

    def test_direct_sources_and_single_field_claims(self):
        skills = {"N02", "N06", "N08"}
        self.assertEqual(set(self.workflows), skills)
        self.assertEqual(set(self.rows), {f"{skill}-{kind}" for skill in skills
                                         for kind in ("normal", "fault", "missing")})
        data_dir = batch_paths("N")[0].parent
        mappings = json.loads((data_dir / "skill_function_mapping_120.json").read_text(encoding="utf-8"))
        direct = {fid for row in mappings if row["proposal_mode"] == "PROPOSED_READ_METADATA"
                  for fid in row["declared_v02_function_refs"]}
        for skill, workflow in self.workflows.items():
            with self.subTest(skill=skill):
                self.assertTrue(workflow["limitation"].strip())
                self.assertTrue(workflow["require_same_sample_time"])
                functions = {s["function_id"] for s in workflow["sources"].values()}
                self.assertEqual(len(functions), 2)
                self.assertLessEqual(functions, direct)
                claims = [c for c in self.doc["claims"] if c["workflow"] == workflow["workflow_id"]]
                self.assertEqual({c["claim_id"] for c in claims}, set(workflow["claims"]))
                for claim in claims:
                    self.assertTrue(claim["claim_id"].endswith("_v1"))
                    self.assertEqual(claim["excludes"], [])
                    predicate, = claim["requires"]
                    source = workflow["sources"][predicate["port"]]
                    self.assertIn(predicate["field"], source["value_schema"]["properties"])
                    self.assertIn(predicate["op"], {"eq", "gt"})
                    self.assertIn(type(predicate["value"]), {int, bool})

    def test_scored_scenarios_and_core_evidence(self):
        report = evaluate("N")
        self.assertEqual((report["passed"], report["total"]), (9, 9))
        claim_alias = {c["claim_id"]: c["requires"][0]["port"] for c in self.doc["claims"]}
        for row in self.rows.values():
            with self.subTest(scenario=row["id"]):
                specs = self.workflows[row["skill_id"]]["sources"]
                proofs = {}

                def capture(sources):
                    for alias, source in sources.items():
                        fid = specs[alias]["function_id"]
                        fact = source.state.fact(fid)
                        if fact is not None:
                            self.assertEqual(source.state.registry.functions[fid].risk, "READ_ONLY")
                            self.assertEqual(fact["value"], row["sources"][alias]["values"])
                            proofs[alias] = fact["id"]

                result = run_scenario(row, batch="N", inspect=capture)
                if row["id"].endswith("-missing"):
                    self.assertEqual(sum(s["values"] is None for s in row["sources"].values()), 1)
                    self.assertEqual(len(proofs), len(specs) - 1)
                    self.assert_unusable(result)
                    continue
                self.assertEqual(set(proofs), set(specs))
                self.assertEqual(result["core_calls"], len(specs))
                self.assertFalse(result["source_errors"])
                supported = {cid: c for cid, c in result["claims"].items() if c["value"] == "TRUE"}
                self.assertTrue(supported)
                for cid, claim in supported.items():
                    self.assertEqual(claim["evidence"], [proofs[claim_alias[cid]]])

    def test_boundary_and_inconclusive_readings(self):
        cases = (
            ("N02", {"firewall": {"rules_count": 1, "invalid_rules": 0}}, "HEALTHY"),
            ("N02", {"firewall": {"rules_count": 1, "invalid_rules": 1}}, "FAULT"),
            ("N02", {"firewall": {"rules_count": 0}}, "UNKNOWN"),
            ("N02", {"firewall": {"rules_count": 1, "invalid_rules": 2}}, "UNKNOWN"),
            ("N02", {"snapshot": {"snapshot_available": False, "configuration_revision": ""}}, "UNKNOWN"),
            ("N02", {"snapshot": {"configuration_revision": "  "}}, "UNKNOWN"),
            ("N06", {"drift": {"drift_count": 0}}, "HEALTHY"),
            ("N06", {"drift": {"drift_count": 1}}, "UNKNOWN"),
            ("N06", {"snapshot": {"snapshot_available": False, "configuration_revision": ""}}, "UNKNOWN"),
            ("N06", {"snapshot": {"snapshot_available": False, "configuration_revision": ""},
                     "drift": {"drift_count": 1}}, "FAULT"),
            ("N06", {"snapshot": {"configuration_revision": ""}}, "UNKNOWN"),
            ("N06", {"snapshot": {"snapshot_available": False}}, "UNKNOWN"),
            ("N08", {"incidents": {"incident_events": 0, "open_incidents": 0}}, "HEALTHY"),
            ("N08", {"incidents": {"open_incidents": 1}}, "FAULT"),
            ("N08", {"snapshot": {"snapshot_available": False, "configuration_revision": ""}}, "UNKNOWN"),
            ("N08", {"snapshot": {"configuration_revision": ""}}, "UNKNOWN"),
        )
        for skill, changes, verdict in cases:
            with self.subTest(skill=skill, changes=changes):
                self.assertEqual(self.run_normal(skill, changes)["verdict"], verdict)

    def test_invalid_types_and_numeric_domains(self):
        values_by_type = {
            "integer": (None, "0", True, -1, 1.5, float("nan"), float("inf")),
            "boolean": (None, "true", 1),
            "string": (None, 1, []),
        }
        for skill, workflow in self.workflows.items():
            for alias, spec in workflow["sources"].items():
                for field, schema in spec["value_schema"]["properties"].items():
                    for value in values_by_type[schema["type"]]:
                        with self.subTest(skill=skill, source=alias, field=field, value=value):
                            self.assert_unusable(self.run_normal(skill, {alias: {field: value}}))

    def test_every_source_and_field_is_required(self):
        for skill, workflow in self.workflows.items():
            for alias, spec in workflow["sources"].items():
                row = copy.deepcopy(self.rows[f"{skill}-fault"])
                row["sources"][alias]["values"] = None
                with self.subTest(skill=skill, missing_source=alias):
                    self.assert_unusable(run_scenario(row, batch="N"))
                for field in spec["value_schema"]["required"]:
                    row = copy.deepcopy(self.rows[f"{skill}-fault"])
                    del row["sources"][alias]["values"][field]
                    with self.subTest(skill=skill, missing_field=field):
                        self.assert_unusable(run_scenario(row, batch="N"))

    def test_unusable_core_facts_and_unaligned_samples(self):
        row = copy.deepcopy(self.rows["N02-fault"])
        row["sources"]["snapshot"]["simulated_at"] = "2026-11-19T08:00:01Z"
        self.assert_unusable(run_scenario(row, batch="N"))
        row = self.rows["N02-fault"]
        for field, value in (("target", "foreign"), ("scope", "client"),
                             ("status", "TIMEOUT"), ("age_s", float("inf"))):
            with self.subTest(field=field):
                def invalidate(sources):
                    sources["firewall"].state.fact("expansion.firewall_audit")[field] = value

                self.assert_unusable(run_scenario(row, batch="N", inspect=invalidate))

        def revoke(sources):
            sources["firewall"].state.permissions.clear()

        self.assert_unusable(run_scenario(row, batch="N", inspect=revoke))

    def test_gold_is_scorer_only_and_rejected_in_scenario_and_config(self):
        read_text = Path.read_text

        def guard(path, *args, **kwargs):
            self.assertNotEqual(path.name, "gold.json")
            return read_text(path, *args, **kwargs)

        with patch.object(Path, "read_text", guard):
            for row in load_scenarios("N"):
                run_scenario(row, batch="N")

        directory, diagnostics = batch_paths("N")
        for path, loader in ((directory / "scenarios.json", load_scenarios), (diagnostics, contracts)):
            with self.subTest(path=path):
                doc = json.loads(read_text(path, encoding="utf-8"))
                if path == diagnostics:
                    holder = doc["workflows"]["N02"]["sources"]["firewall"]["value_schema"]
                else:
                    holder = doc["scenarios"][0]["sources"]["firewall"]["values"]
                holder["expected_verdict"] = "HEALTHY"

                def inject(requested, *args, **kwargs):
                    return json.dumps(doc) if requested == path else read_text(requested, *args, **kwargs)

                with patch.object(Path, "read_text", inject):
                    with self.assertRaisesRegex(SimulationError, "gold-like"):
                        loader("N")
