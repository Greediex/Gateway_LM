"""WP-S2: print a worksheet for one COV batch from the 120-Skill catalog data.

Usage: python -m scripts.scaffold_batch B [--out FILE]

The worksheet lists, per Skill, its type, declared Function/port fields and
three scenario stubs (normal/fault/missing). Stub values are ``TODO:<type>``
placeholders that fail port-schema validation on purpose, so a skeleton cannot
be loaded as a real scenario. Gold/expected verdicts are never generated: they
are written by a person or Codex in a separate scorer-only file (L1, L5).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateway_pilot.skill_expansion.catalog import DATA_DIR
from gateway_pilot.skill_expansion.coverage import build_coverage
from gateway_pilot.skill_expansion.simulation import PORTS_DIR

STATES = ("normal", "fault", "missing")


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _port_fields(function_id: str) -> dict | None:
    path = PORTS_DIR / f"{function_id}.json"
    if not path.is_file():
        return None
    schema = _json(path)["schema"]
    return {name: spec.get("type", "any") for name, spec in schema.get("properties", {}).items()}


def worksheet(letter: str) -> dict:
    batch = f"COV-{letter}"
    rows = [r for r in build_coverage() if r.batch == batch]
    if len(rows) != 8:
        raise ValueError(f"unknown batch {letter!r}; expected a letter A-O")
    mapping = {m["skill_id"]: m for m in _json(DATA_DIR / "skill_function_mapping_120.json")}
    skills = []
    for row in rows:
        sid, m = row.skill_id, mapping[row.skill_id]
        functions = m.get("declared_v02_function_refs", [])
        item = {"skill_id": sid, "name": row.name, "type": row.skill_type,
                "simulation_verified": row.simulation_verified, "functions": functions,
                "suggested_evidence_functions": m.get("suggested_evidence_functions", [])}
        if row.skill_type == "direct" and len(functions) == 1:
            fields = _port_fields(functions[0])
            if fields is None:
                item["needs"] = f"no port schema for {functions[0]}: create a reviewed contract first"
            else:
                item["claim_fields"] = fields
                item["scenarios"] = [
                    {"id": f"{sid}-{state}", "skill_id": sid, "state": state,
                     "simulated_at": "TODO:iso8601", "function_id": functions[0],
                     "values": None if state == "missing"
                     else {k: f"TODO:{t}" for k, t in fields.items()}}
                    for state in STATES]
        else:
            item["needs"] = ("workflow/Claim design over existing evidence; "
                             "missing source must give UNKNOWN, no fake READ Function"
                             if row.skill_type in ("composite", "history")
                             else "legacy/change/multi-function: design by hand")
        skills.append(item)
    return {"format": "gateway-lm.batch-worksheet/v1", "batch": batch, "skeleton_only": True,
            "next_steps": ["WP-X1: fill values, add Claims and a separate gold file for direct Skills",
                           "WP-X2: workflows/Claims for composite and history Skills",
                           "WP-X3: replay profile, acceptance.json, rerun coverage"],
            "skills": skills}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("batch", help="batch letter A-O")
    parser.add_argument("--out", type=Path, help="write to FILE instead of stdout")
    args = parser.parse_args()
    try:
        text = json.dumps(worksheet(args.batch.upper()), ensure_ascii=False, indent=2) + "\n"
    except ValueError as exc:
        parser.error(str(exc))
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
