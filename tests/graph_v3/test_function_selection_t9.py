"""T9: Function Selection benchmark data integrity and a smoke run of every arm."""
import hashlib
import re
import unittest
from collections import Counter

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry

from scripts.benchmarks import run_function_selection as bench

DATA = read_json(ROOT / "benchmarks/function_selection_v1.json")


class FunctionSelectionT9Tests(unittest.TestCase):
    def test_dataset_is_locked_by_its_manifest(self):
        manifest = read_json(ROOT / "benchmarks/function_selection_v1.manifest.json")
        digest = hashlib.sha256((ROOT / "benchmarks/function_selection_v1.json").read_bytes()).hexdigest()
        self.assertEqual(digest, manifest["sha256"])
        self.assertEqual(manifest["splits"], {"dev": 30, "holdout": 30})

    def test_cases_cover_five_workflows_by_six_conditions_without_requirement_ids(self):
        cases = DATA["cases"]
        self.assertGreaterEqual(len(cases), 30)
        grid = Counter((c["workflow"], c["condition"]) for c in cases)
        self.assertEqual(len(grid), 5 * 6)
        self.assertTrue(all(count == 2 for count in grid.values()))  # one dev, one holdout phrasing
        registry = GraphRegistry.from_v01()
        for case in cases:
            self.assertTrue(set(case["required_functions"]) <= set(registry.functions))
            self.assertFalse(any(re.fullmatch(r"F\d{3}", f) for f in case["required_functions"]))
            if case["condition"] == "write_request":
                self.assertEqual((case["required_functions"], case["expected_status"]), ([], "BLOCKED"))
            if case["condition"] == "missing_capability":
                self.assertNotEqual(case["expected_status"], "RESOLVED")

    def test_labels_include_prerequisite_producers(self):
        dns = next(c for c in DATA["cases"] if c["id"] == "FS-WF-023-normal-dev")
        self.assertIn("dns.config", dns["required_functions"])  # input of dns.probe
        self.assertIn("wan.status", dns["required_functions"])  # prerequisite chain of wan.probe

    def test_every_arm_runs_one_case_without_policy_violation(self):
        registry = GraphRegistry.from_v01()
        case = next(c for c in DATA["cases"] if c["id"] == "FS-WF-018-normal-dev")
        for arm in (*bench.ARMS, *bench.REFERENCES):
            with self.subTest(arm):
                runner = bench.run_reference if arm in bench.REFERENCES else bench.run_arm
                row = bench.score(case, runner(arm, case, registry), registry)
                self.assertEqual(row["policy_violations"], 0)
                self.assertFalse(row["false_resolution"])

    def test_write_request_is_blocked_without_calls_in_arms_d_and_e(self):
        registry = GraphRegistry.from_v01()
        case = next(c for c in DATA["cases"] if c["id"] == "FS-WF-023-write_request-dev")
        for arm in ("D", "E"):
            outcome = bench.run_arm(arm, case, registry)
            self.assertEqual((outcome["status"], outcome["executed"]), ("BLOCKED", []))


if __name__ == "__main__":
    unittest.main()
