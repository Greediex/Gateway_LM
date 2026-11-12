"""Opt-in hybrid retrieval contract: local-only vectors, GoS and hard gates.

Mock embeddings validate integration only; they do not measure semantic model
quality on Vietnamese network diagnostics or imply NPU readiness.
"""
from __future__ import annotations

import copy
import math
import unittest

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.semantic import LocalSemanticIndex
from gateway_pilot.graph_v3.state import CaseState


class StubLocalEncoder:
    model_id = "mock-semantic-v1"
    local_only = True

    def __init__(self, target="wan.status"):
        self.target = target
        self.calls = []

    def encode_many(self, texts):
        self.calls.append(list(texts))
        result = []
        for text in texts:
            # Synthetic vector oracle: one explicit catalog row is similar
            # to an unrelated query token. No language-model claims.
            if text.startswith("hiddensemantic") or text.startswith(self.target + " "):
                result.append([1.0, 0.0, 0.0])
            else:
                result.append([0.0, 1.0, 0.0])
        return result


class HybridRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(
            c for c in read_json(ROOT / "data/cases.json") if c["template"] == "wan_healthy"
        ))
        self.state = CaseState(self.case, self.registry, clock=lambda: 0)

    def test_semantic_only_query_uses_local_model_and_pinned_graph(self):
        self.registry.configure_semantic(StubLocalEncoder())
        result = self.registry.retrieve(
            "hiddensemantic", (), self.state, method="hybrid",
            seed_top_k=4, top_n=6,
        )
        self.assertIn("wan.status", result["functions"])
        self.assertIn("f:wan.status", result["seeds"])
        self.assertTrue(result["semantic_match"])
        self.assertFalse(result["lexical_match"])
        self.assertTrue(result["upstream_kernel_used"])
        self.assertEqual(result["semantic_model"], "mock-semantic-v1")
        self.assertEqual(result["semantic_scores"]["f:wan.status"], 1.0)

    def test_hybrid_goals_pass_shared_runner_and_verifier(self):
        self.registry.configure_semantic(StubLocalEncoder())
        result = GoalAgent(self.registry, method="hybrid").run(
            "hiddensemantic", self.case, goals=("wan.status",)
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["diagnosis"], "NOT_EVALUATED")
        self.assertEqual(result["goal_facts"][0]["port"], "wan.status")

    def test_baseline_methods_unchanged_after_semantic_configuration(self):
        old = {
            method: self.registry.retrieve("check WAN", ("wan.status",), self.state, method=method)
            for method in ("bm25", "gos")
        }
        self.registry.configure_semantic(StubLocalEncoder())
        for method in ("bm25", "gos"):
            with self.subTest(method=method):
                new = self.registry.retrieve("check WAN", ("wan.status",), self.state, method=method)
                for field in ("functions", "seeds", "scores", "rerank_scores",
                              "upstream_kernel_used", "lexical_match"):
                    self.assertEqual(new[field], old[method][field])

    def test_unprobed_or_write_function_never_seeds_or_executes(self):
        self.registry.configure_semantic(StubLocalEncoder(target="dns.apply"))
        r = self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")
        self.assertNotIn("dns.apply", r["functions"])
        self.assertNotIn("f:dns.apply", r["seeds"])
        # Unprobed capability is never made eligible by vector similarity.
        self.state.capabilities.clear()
        r = self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")
        self.assertEqual(r["functions"], [])

    def test_document_embedding_cache_invalidated_by_registry_rebuild(self):
        encoder = StubLocalEncoder()
        self.registry.configure_semantic(encoder)
        for _ in range(2):
            self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")
        self.assertEqual(len(encoder.calls), 3)  # one catalog + two queries
        self.registry.functions["wan.status"].description = "New documented sensor contract"
        self.registry.rebuild()
        self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")
        self.assertEqual(len(encoder.calls), 5)  # new catalog + query

    def test_hybrid_without_trusted_model_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, "semantic_provider_required"):
            self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")
        with self.assertRaisesRegex(ValueError, "semantic_provider_required"):
            GoalAgent(self.registry, method="hybrid")

    def test_remote_or_malformed_model_must_be_rejected(self):
        encoder = StubLocalEncoder()
        encoder.local_only = False
        with self.assertRaisesRegex(ValueError, "trusted_local"):
            LocalSemanticIndex(encoder)
        for threshold in (0, 2, float("nan")):
            with self.subTest(threshold=threshold), self.assertRaises(ValueError):
                LocalSemanticIndex(StubLocalEncoder(), min_similarity=threshold)

    def test_bad_vectors_fail_closed_without_lexical_fallback(self):
        class Broken(StubLocalEncoder):
            def __init__(self, mode):
                super().__init__()
                self.mode = mode
            def encode_many(self, texts):
                if self.mode == "nonfinite":
                    return [[float("nan"), 1] for _ in texts]
                if self.mode == "zero":
                    return [[0.0, 0.0] for _ in texts]
                if self.mode == "mismatch":
                    return [[1, 0] if i % 2 == 0 else [1, 0, 0]
                            for i, _ in enumerate(texts)]
                return []

        for mode in ("nonfinite", "zero", "mismatch", "missing"):
            with self.subTest(mode=mode):
                self.registry.configure_semantic(Broken(mode))
                with self.assertRaisesRegex(PlanError, "semantic_"):
                    self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")

    def test_query_dimension_mismatch_is_not_silently_cropped(self):
        class WrongQuery(StubLocalEncoder):
            def encode_many(self, texts):
                if len(texts) == 1:
                    return [[1, 0, 0, 0]]
                return [[1, 0, 0] for _ in texts]
        self.registry.configure_semantic(WrongQuery())
        with self.assertRaisesRegex(PlanError, "semantic_query_dimension_mismatch"):
            self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")

    def test_replayed_untrusted_log_is_not_embedded_in_static_catalog(self):
        encoder = StubLocalEncoder()
        self.registry.configure_semantic(encoder)
        self.registry.retrieve("hiddensemantic", (), self.state, method="hybrid")
        catalog_batch = encoder.calls[0]
        self.assertTrue(all("ignore instructions and run" not in text for text in catalog_batch))
        self.assertTrue(any("wan.status" in text for text in catalog_batch))


if __name__ == "__main__":
    unittest.main()
