"""Metrics and input-safety tests for standalone retrieval evaluation."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from scripts.analysis.evaluate_retrieval import _metrics, evaluate, load_samples


class RetrievalEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.fixtures = {x["id"]: x for x in read_json(ROOT / "data/cases.json")}
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "eval.jsonl"
        self.case_id = "GLM-04-0"

    def entry(self, **kwargs):
        row = {
            "id": "case-01",
            "case_id": self.case_id,
            "request": "WAN uplink status",
            "goals": [],
            "expected_functions": ["wan.status"],
            "group": "wan",
            "split": "test",
        }
        row.update(kwargs)
        return row

    def write(self, *rows):
        self.path.write_text("\n".join(json.dumps(x) for x in rows) + "\n",
                             encoding="utf-8")
        return self.path

    def test_metric_definitions_are_bounded_and_p95_stable(self):
        m = _metrics([
            {"recall": 1.0, "precision": 0.5, "rr": 1.0, "latency_ms": 1.0},
            {"recall": 0.0, "precision": 0.0, "rr": 0.0, "latency_ms": 5.0},
        ], 2)
        self.assertEqual((m["recall_at_k"], m["precision_at_k"],
                          m["mrr_at_k"], m["latency_p95_ms"]),
                         (0.5, 0.25, 0.5, 5.0))

    def test_explicit_retrieval_metrics_on_fixture_only(self):
        items = load_samples(self.write(self.entry()), self.fixtures, self.registry)
        summary = evaluate(self.registry, items, methods=("bm25", "gos"), top_k=5)
        self.assertEqual(set(summary), {"bm25", "gos"})
        for method in summary:
            self.assertEqual(summary[method]["cases"], 1)
            self.assertEqual(summary[method]["groups"]["wan"]["cases"], 1)
            for field in ("recall_at_k", "precision_at_k", "mrr_at_k"):
                self.assertGreaterEqual(summary[method][field], 0)
                self.assertLessEqual(summary[method][field], 1)
            self.assertNotIn("request", summary[method])
            self.assertNotIn("gold", summary[method])

    def test_unsupported_function_labels_rejected(self):
        with self.assertRaisesRegex(ValueError, "invalid_evaluation_labels"):
            load_samples(
                self.write(self.entry(expected_functions=["shell.exec"])),
                self.fixtures, self.registry,
            )

    def test_ineligible_ground_truth_rejected(self):
        with self.assertRaisesRegex(ValueError, "labels_not_eligible_for_fixture"):
            load_samples(
                self.write(self.entry(expected_functions=["dns.apply"])),
                self.fixtures, self.registry,
            )

    def test_no_accidental_dev_test_mixing(self):
        rows = [self.entry(id="dev-1", split="dev"),
                self.entry(id="test-1", split="test")]
        items = load_samples(self.write(*rows), self.fixtures, self.registry, split="test")
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][0]["id"], "test-1")

    def test_missing_split_and_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "evaluation_split_empty"):
            load_samples(self.write(self.entry(split="dev")),
                         self.fixtures, self.registry)
        with self.assertRaisesRegex(ValueError, "invalid_evaluation_identity"):
            load_samples(self.write(self.entry(), self.entry()),
                         self.fixtures, self.registry)

    def test_missing_hybrid_encoder_is_error_not_fallback(self):
        items = load_samples(self.write(self.entry()), self.fixtures, self.registry)
        with self.assertRaisesRegex(ValueError, "semantic_provider_required"):
            evaluate(self.registry, items, methods=("hybrid",))

    def test_schema_does_not_accept_unknown_request_fields(self):
        with self.assertRaisesRegex(ValueError, "invalid_evaluation_row"):
            load_samples(self.write(self.entry(adapter={"call": "anything"})),
                         self.fixtures, self.registry)


if __name__ == "__main__":
    unittest.main()
