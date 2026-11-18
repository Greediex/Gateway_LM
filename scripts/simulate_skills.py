"""Run COV-02 scenarios through the shared v0.2 Core and score against gold.

Synthetic only, uses the disposable sandbox in ``core_replay_smoke_v2.smoke``.
This checks Core evidence admission per scenario; it is NOT a Skill-level
diagnosis or Claim and does not mark any Skill "Simulation verified" alone.
"""
from __future__ import annotations

import argparse
import json

from gateway_pilot.skill_expansion.runtime_bridge import SkillNotReady
from gateway_pilot.skill_expansion.simulation import load_gold, load_scenarios
from scripts.core_replay_smoke_v2 import smoke


def run_scenario(sc) -> dict:
    try:
        result = smoke(sc.function_id, values=sc.values, omit=sc.values is None)
    except SkillNotReady as exc:
        return {"id": sc.id, "outcome": "NOT_READY", "reason": str(exc)}
    if result["fact_value"] != sc.values:
        return {"id": sc.id, "outcome": "VALUE_MISMATCH"}
    return {"id": sc.id, "outcome": "VERIFIED", "evidence_id": result["evidence_id"],
            "core_calls": result["core_calls"]}


def evaluate() -> dict:
    scenarios = load_scenarios()
    rows = [run_scenario(sc) for sc in scenarios]
    gold = load_gold(scenarios)  # loaded only after all runs finished
    for row in rows:
        row["pass"] = row["outcome"] == gold[row["id"]]
    return {"synthetic_only": True, "total": len(rows),
            "passed": sum(r["pass"] for r in rows), "rows": rows}


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["passed"] == report["total"] else 1)
