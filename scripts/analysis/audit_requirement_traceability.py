"""Reproducible 270-requirement-to-Function traceability, no fake support.

A requirement mapped to a REPLAY_ONLY Function is *not* implemented on a
router. Reports actual registered skills, per-requirement bindings and
firmware-verified vs replay-only coverage separately.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from gateway_pilot.core import ROOT, read_json


def audit(registry_data, requirement_data, *, target_skills=22):
    reqs = requirement_data.get("requirements", [])
    funcs, skills = registry_data.get("functions", []), registry_data.get("skills", [])
    if not isinstance(reqs, list) or not isinstance(funcs, list) or not isinstance(skills, list):
        raise ValueError("invalid_traceability_catalog")
    identifiers = [r["requirement_id"] for r in reqs]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("duplicate_requirement_id")
    available = set(identifiers)
    by_req = defaultdict(list)
    for f in funcs:
        for req in f.get("requirement_refs", ()):
            if req not in available:
                raise ValueError("function_references_unknown_requirement:" + req)
            by_req[req].append({
                "function_id": f["function_id"],
                "status": f["status"],
                "risk": f["risk"],
                "adapter": f["adapter"],
                "skill_ids": list(f["skill_ids"]),
            })
    report = []
    for requirement in reqs:
        rid = requirement["requirement_id"]
        bound = sorted(by_req[rid], key=lambda row: row["function_id"])
        verified = [
            row for row in bound
            if row["status"] == "PROBED_OK" and row["risk"] in {"READ_ONLY", "PROBE"}
        ]
        states = sorted({f["status"] for f in bound})
        report.append({
            "requirement_id": rid, "title": requirement["title"],
            "functions": bound, "states": states,
            "mapped": bool(bound), "firmware_verified": bool(verified),
            "testable_on_replay": any(f["status"] == "REPLAY_ONLY" for f in bound),
        })
    mapped = sum(x["mapped"] for x in report)
    probed = sum(x["firmware_verified"] for x in report)
    return {
        "protocol": "requirement-traceability/v1",
        "source": "data/requirements_v01.json + data/registry_v01.json",
        "declared_skill_count": len(skills),
        "target_skill_count": target_skills,
        "skill_gap": max(0, target_skills - len(skills)),
        "registered_function_count": len(funcs),
        "requirement_count": len(reqs),
        "mapped_requirement_count": mapped,
        "unmapped_requirement_count": len(reqs) - mapped,
        "firmware_verified_requirement_count": probed,
        "replay_only_requirement_count": sum(x["testable_on_replay"] for x in report),
        "coverage_firmware": round(probed / len(reqs), 6) if reqs else 0,
        "rows": report,
        "warning": "A requirement or skill is not an executable Function; REPLAY_ONLY is not firmware support.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Audit requirement-to-Function coverage")
    parser.add_argument("--output", type=Path, default=Path("runs/requirement_traceability.json"))
    parser.add_argument("--require-verified", action="store_true",
                        help="Fail if no firmware-verified requirement is present")
    args = parser.parse_args(argv)
    result = audit(
        read_json(ROOT / "data/registry_v01.json"),
        read_json(ROOT / "data/requirements_v01.json"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                           encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "rows"},
                     indent=2, ensure_ascii=False))
    if args.require_verified and not result["firmware_verified_requirement_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
