"""Structural retrieval coverage only; never substitutes for model results."""
import json
from collections import defaultdict

from gateway_pilot.core import ROOT, Registry, new_state, read_json


def main():
    registry = Registry()
    rows = []
    for c in read_json(ROOT / "data/cases.json"):
        if c["split"] != "test":
            continue
        state = new_state(c, registry)
        seeds = []
        for port in registry.data["workflow_evidence"][c["workflow"]]:
            seeds += [fid for fid in registry.producers.get(port, [])
                      if fid in state.capabilities and registry.functions[fid]["risk"] == "READ"]
        needed = set(registry.closure(seeds, state))
        for arm in ("flat", "retrieval", "graph"):
            candidates = registry.candidates(c, state, arm, k=4)
            coverage = len(needed & set(candidates)) / len(needed) if needed else 1
            rows.append({"case_id": c["id"], "workflow": c["workflow"], "arm": arm,
                         "required_read_functions": sorted(needed), "exposed": candidates,
                         "function_goal_coverage": coverage})
    grouped = defaultdict(list)
    for row in rows:
        grouped[row["arm"]].append(row["function_goal_coverage"])
    result = {"kind": "Static contract-based catalog coverage; no model calls or gold fault labels",
              "mean_goal_function_coverage": {arm: sum(xs) / len(xs) for arm, xs in grouped.items()},
              "rows": rows}
    (ROOT / "docs/catalog_coverage.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["mean_goal_function_coverage"], indent=2))


if __name__ == "__main__":
    main()
