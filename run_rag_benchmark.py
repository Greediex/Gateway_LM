"""Compare BM25, dependency closure and anchored GoS, then measure the pinned PPR cache."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from time import perf_counter_ns

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.upstream import _cached_transition, rank
from gateway_pilot.rag import DEFAULT_CATALOG, REPLAY_FIRMWARE, REPLAY_PRODUCT, RunbookIndex


def matrix_benchmark():
    results = []
    for count in (64, 128):
        names = [f"node-{index:03}" for index in range(count)]
        edges = [(names[i], names[i + 1], "dependency", 1.) for i in range(count - 1)]
        # Different queries, identical graph. Import and first model-free PPR call are outside timing.
        rank(names, edges, {names[-1]: 1})
        times = {"cold": [], "warm": []}
        same = True
        for index in range(24):
            seeds = {names[(7 * index) % count]: 1}
            _cached_transition.cache_clear()
            before = perf_counter_ns()
            cold = rank(names, edges, seeds)
            times["cold"].append((perf_counter_ns() - before) / 1_000_000)
            before = perf_counter_ns()
            warm = rank(names, edges, seeds)
            times["warm"].append((perf_counter_ns() - before) / 1_000_000)
            same &= cold == warm
        results.append({"nodes": count, "pairs": 24, "same_scores": same,
                        "cold_p50_ms": median(times["cold"]), "warm_p50_ms": median(times["warm"])})
    return results


def run(output):
    output.mkdir(parents=True)
    cases_path = ROOT / "benchmarks" / "rag_cases_v1.json"
    docs = read_json(DEFAULT_CATALOG)
    docs.append({**docs[0], "id": "wrong-version-bait", "firmware": "synthetic-replay-v0",
                 "title": "zebraorbital exactphrase", "keywords": "zebraorbital exactphrase", "requires": []})
    catalog = output / "catalog.json"
    catalog.write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    index = RunbookIndex(catalog)
    cases = read_json(cases_path)
    profiles = {doc["id"]: (doc["product"], doc["firmware"]) for doc in docs}
    scores = {}
    with (output / "episodes.jsonl").open("x", encoding="utf-8") as stream:
        for method in ("bm25", "closure", "gos"):
            metrics = Counter()
            for case in cases:
                product = case.get("product", REPLAY_PRODUCT)
                firmware = case.get("firmware", REPLAY_FIRMWARE)
                result = index.retrieve(case["query"], product=product, firmware=firmware,
                                        permissions=set() if case.get("deny_docs") else {"docs.read"},
                                        method=method, k=2, max_bytes=case.get("max_bytes", 1600))
                selected = [doc["id"] for doc in result["documents"]]
                leak = any(profiles[key] != (product, firmware) for key in selected)
                if case.get("deny_docs"):
                    leak |= bool(selected) or "source" in result
                if "primary" in case:
                    hit = bool(selected) and selected[0] == case["primary"]
                    bundle = set(case["required"]) <= set(selected)
                    metrics.update(answerable=1, hit_at_1=hit, bundle_at_2=bundle)
                else:
                    hit = not selected and result["reason"] == case["reason"]
                    bundle = hit
                    metrics.update(abstention_cases=1, correct_abstentions=hit)
                metrics.update(profile_leaks=leak)
                stream.write(json.dumps({"case_id": case["id"], "method": method, "top2": selected,
                                         "reason": result["reason"], "primary_match": hit,
                                         "bundle_complete": bundle, "profile_leak": leak}) + "\n")
            scores[method] = dict(metrics)
    summary = {"scope": "authored replay runbooks and queries", "model_calls": 0, "retrieval": scores,
               "matrix_cache": matrix_benchmark(),
               "fixture_sha256": hashlib.sha256(cases_path.read_bytes()).hexdigest(),
               "catalog_sha256": index.source["sha256"]}
    (output / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    print(json.dumps(run(parser.parse_args().output), ensure_ascii=True))
