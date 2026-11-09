"""Independent integrity check of a completed pilot run (no inference)."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    args = p.parse_args()
    run = args.run.resolve()
    meta = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    rows = [json.loads(x) for x in (run / "episodes.jsonl").read_text(encoding="utf-8").splitlines()]
    errors = []
    if not meta.get("finished_at"):
        errors.append("Run has not completed")
    seen = Counter((r["case_id"], r["arm"]) for r in rows)
    if any(n != 1 for n in seen.values()):
        errors.append("Duplicate episodes")
    arms = meta["args"]["arms"]
    cases = sorted({r["case_id"] for r in rows})
    if len(rows) != len(cases) * len(arms):
        errors.append("Incomplete paired arms")
    if meta.get("model_metadata") and meta["model_metadata"]["parameter_count"] >= 3_000_000_000:
        errors.append("Model exceeds parameter limit")
    for relative, expected in meta["source_sha256"].items():
        snapshot = run / "source_snapshot" / relative
        if not snapshot.exists() or hashlib.sha256(snapshot.read_bytes()).hexdigest() != expected:
            errors.append("Source snapshot mismatch: " + relative)
    summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
    for arm, reported in summary["arms"].items():
        group = [r for r in rows if r["arm"] == arm]
        if reported["n"] != len(group) or reported["autonomous_success"] != sum(r["autonomous_success"] for r in group):
            errors.append("Summary mismatch: " + arm)
    for row in rows:
        expected_match = all(row["terminal"].get(k) == v for k, v in row["gold"].items())
        expected_success = expected_match and not row["forced_stop"] and not row["runtime_errors"]
        if row["outcome_match"] != expected_match or row["autonomous_success"] != expected_success:
            errors.append("Scoring mismatch: " + row["case_id"] + "/" + row["arm"])
        if len(row["executed"]) != row["tool_calls"] or row["tool_calls"] > meta["args"]["max_tools"]:
            errors.append("Tool count mismatch")
        if any("apply" in x["function_id"] for x in row["executed"]):
            errors.append("Write appeared in read-only run")
        if row["terminal"]["action"] == "FINISH":
            actual_ids = {e["id"] for e in row["evidence"]}
            if not set(row["terminal"].get("evidence_ids", [])).issubset(actual_ids):
                errors.append("Fabricated final citation")
    result = {"status": "PASS" if not errors else "FAIL", "episodes": len(rows),
              "cases": len(cases), "arms": arms, "errors": errors,
              "runtime_error_episodes": sum(bool(r["runtime_errors"]) for r in rows)}
    (run / "integrity_check.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("PILOT_ARTIFACT_CHECK=" + result["status"])
    print(json.dumps(result, indent=2))
    raise SystemExit(bool(errors))


if __name__ == "__main__":
    main()
