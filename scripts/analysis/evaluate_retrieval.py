"""Offline, reproducible Function-retrieval evaluation (not an RCA benchmark).

No prompt/world/gold data is copied into the result artifact. Hybrid requires
a trusted, fully local embedding model. Frozen benchmark datasets are never
modified; examples are expressly illustrative, not held-out test results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import time
from pathlib import Path

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.semantic import LocalSentenceTransformerEncoder
from gateway_pilot.graph_v3.state import CaseState


ALLOWED_METHODS = ("bm25", "gos", "hybrid")


def _average(values):
    return round(sum(values) / len(values), 6) if values else 0.0


def _metrics(samples, k):
    if not samples:
        raise ValueError("evaluation_requires_samples")
    elapsed = sorted(sample["latency_ms"] for sample in samples)
    p95_index = max(0, math.ceil(len(elapsed) * 0.95) - 1)
    return {
        "cases": len(samples),
        "recall_at_k": _average([x["recall"] for x in samples]),
        "precision_at_k": _average([x["precision"] for x in samples]),
        "mrr_at_k": _average([x["rr"] for x in samples]),
        "latency_mean_ms": _average(elapsed),
        "latency_p95_ms": round(elapsed[p95_index], 3),
        "top_k": k,
    }


def load_samples(path, fixtures, registry, *, split="test", max_cases=500):
    path = Path(path)
    if not path.is_file() or path.stat().st_size > 5_000_000:
        raise ValueError("invalid_evaluation_file")
    items = []
    seen = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        row = json.loads(raw)
        if not isinstance(row, dict) or set(row) != {
            "id", "case_id", "request", "goals", "expected_functions", "group", "split"
        }:
            raise ValueError("invalid_evaluation_row")
        if row["split"] != split:
            continue
        if (not isinstance(row["id"], str) or not 1 <= len(row["id"]) <= 128
                or row["id"] in seen
                or not isinstance(row["group"], str) or not 1 <= len(row["group"]) <= 64
                or not isinstance(row["request"], str) or not 1 <= len(row["request"]) <= 2000):
            raise ValueError("invalid_evaluation_identity")
        seen.add(row["id"])
        case = fixtures.get(row["case_id"])
        if case is None:
            raise ValueError("unknown_evaluation_fixture")
        goals, expected = row["goals"], row["expected_functions"]
        if (not isinstance(goals, list) or any(not isinstance(g, str) or g not in registry.ports
                                              for g in goals)
                or not isinstance(expected, list) or not expected or
                any(not isinstance(fid, str) or fid not in registry.functions for fid in expected)
                or len(set(expected)) != len(expected)):
            raise ValueError("invalid_evaluation_labels")
        state = CaseState(case, registry)
        if not set(expected).issubset(registry.eligible(state)):
            raise ValueError("labels_not_eligible_for_fixture")
        items.append((row, state))
        if len(items) > max_cases:
            raise ValueError("too_many_evaluation_cases")
    if not items:
        raise ValueError("evaluation_split_empty")
    return items


def evaluate(registry, items, *, methods=("bm25", "gos"), top_k=5):
    if (not methods or any(method not in ALLOWED_METHODS for method in methods)
            or type(top_k) is not int or not 1 <= top_k <= 25):
        raise ValueError("invalid_evaluation_config")
    outcome = {}
    for method in methods:
        if method == "hybrid" and getattr(registry, "_semantic_index", None) is None:
            raise ValueError("semantic_provider_required")
        rows, groups = [], {}
        for row, state in items:
            start = time.perf_counter()
            retrieval = registry.retrieve(
                row["request"], row["goals"], state, k=top_k, method=method
            )
            latency_ms = (time.perf_counter() - start) * 1000
            predicted = retrieval["functions"][:top_k]
            expected = set(row["expected_functions"])
            hits = expected.intersection(predicted)
            first_hit = next((i + 1 for i, fid in enumerate(predicted) if fid in expected), None)
            sample = {
                "recall": len(hits) / len(expected),
                "precision": len(hits) / top_k,
                "rr": 1 / first_hit if first_hit is not None else 0.0,
                "latency_ms": latency_ms,
            }
            rows.append(sample)
            groups.setdefault(row["group"], []).append(sample)
        outcome[method] = {
            **_metrics(rows, top_k),
            "groups": {name: _metrics(samples, top_k)
                       for name, samples in sorted(groups.items())},
        }
    return outcome


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare Function retrieval on a labeled JSONL suite")
    parser.add_argument("--input", type=Path, required=True,
                        help="UTF-8 JSONL: id, case_id, request, goals, expected_functions, group, split")
    parser.add_argument("--output", type=Path, default=Path("runs/retrieval-eval.json"))
    parser.add_argument("--methods", nargs="+", choices=ALLOWED_METHODS,
                        default=["bm25", "gos"])
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--split", default="test")
    parser.add_argument("--max-cases", type=int, default=500)
    parser.add_argument("--registry", choices=("legacy", "v01"), default="v01")
    parser.add_argument("--semantic-model-dir", type=Path)
    parser.add_argument("--min-similarity", type=float, default=0.62)
    args = parser.parse_args(argv)
    if args.max_cases < 1 or not args.split or len(args.split) > 64:
        parser.error("invalid split or max-cases")
    if ("hybrid" in args.methods) != (args.semantic_model_dir is not None):
        parser.error("hybrid must be paired with --semantic-model-dir")
    registry = GraphRegistry.from_v01() if args.registry == "v01" else GraphRegistry()
    if args.semantic_model_dir is not None:
        registry.configure_semantic(
            LocalSentenceTransformerEncoder(args.semantic_model_dir),
            min_similarity=args.min_similarity,
        )
    fixture_rows = read_json(ROOT / "data/cases.json")
    fixtures = {c["id"]: c for c in fixture_rows}
    items = load_samples(args.input, fixtures, registry,
                         split=args.split, max_cases=args.max_cases)
    metrics = evaluate(registry, items, methods=args.methods, top_k=args.top_k)
    artifact = {
        "protocol": "retrieval-eval/v1",
        "data_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "split": args.split,
        "fixture_source": "synthetic_replay",
        "registry": args.registry,
        "model": (registry._semantic_index.model_id
                  if getattr(registry, "_semantic_index", None) is not None else None),
        "methods": metrics,
        "disclaimer": "Function retrieval only; no RCA accuracy or router hardware claims",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps(artifact, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
