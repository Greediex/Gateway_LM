"""T9 Function Selection benchmark: arms A-E plus resolver reference rows (G19).

All numbers are synthetic replay on the host, never router measurements.

Arms (same request text, same candidate budget K and call budget for all):
  A  fixed workflow      legacy regex router -> every goal of that workflow, compiled with prerequisites
  B  Skill-only BM25     top Skills by BM25 -> their member Functions, no prerequisite expansion
  C  joint retrieval     GoS joint Skill-Function retrieval, top-K Functions, no expansion
  D  C + schema expansion   the same Functions compiled with typed prerequisite producers
  E  D + re-retrieval    D, then retrieve again on the updated Case State until nothing new or budget
Reference rows (not arms): R = diagnose(route="resolver") with the case workflow;
R-NBA = the same with the claim-based next-best-action selector (C4).

Usage:  python run_function_selection.py --run function_selection_v1_YYYYMMDD
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import statistics
import sys
import time
import tracemalloc
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from build_function_selection_v1 import case_state, environment  # noqa: E402
from gateway_pilot.core import PlanError, read_json  # noqa: E402
from gateway_pilot.graph_v3.graphs import GraphRegistry  # noqa: E402
from gateway_pilot.graph_v3.planner import Compiler, NodeState  # noqa: E402
from gateway_pilot.graph_v3.runner import GraphRunner  # noqa: E402
from gateway_pilot.workflow import CHANGE_REQUEST, diagnose, normalize, route  # noqa: E402

import re  # noqa: E402

DATA = ROOT / "benchmarks/function_selection_v1.json"
MANIFEST = ROOT / "benchmarks/function_selection_v1.manifest.json"
K, MAX_CALLS, ROUNDS = 6, 12, 4
ARMS = ("A", "B", "C", "D", "E")
REFERENCES = ("R", "R-NBA")
DONE = (NodeState.SUCCEEDED, NodeState.SKIPPED, NodeState.FAILED, NodeState.INCONCLUSIVE)


def rss_bytes():
    """Process resident set size (Windows psapi or Linux resource); None if unavailable."""
    try:
        if os.name == "nt":
            class Counters(ctypes.Structure):
                _fields_ = [("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
                            ("PeakPagefileUsage", ctypes.c_size_t)]
            counters = Counters()
            counters.cb = ctypes.sizeof(Counters)
            kernel32, psapi = ctypes.WinDLL("kernel32"), ctypes.WinDLL("psapi")
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            psapi.GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(Counters), ctypes.c_ulong]
            if psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
                return int(counters.PeakWorkingSetSize)
            return None
        import resource
        return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss) * 1024
    except (OSError, AttributeError, ImportError):
        return None


def compile_what_fits(registry, state, *, goals=(), requested=(), expand=True):
    """Compile the selection; if the whole set is inadmissible, keep each piece that compiles alone.

    expand=False forbids every Function outside the selection, so missing
    prerequisites are not added (arms B and C).
    """
    excluded = set() if expand else set(registry.functions) - set(requested)

    def attempt(g, r):
        return Compiler(registry, excluded=excluded).compile(tuple(g), state, requested=tuple(r))

    try:
        return [attempt(goals, requested)], 0
    except PlanError:
        plans, failures = [], 0
        for g in goals:
            try:
                plans.append(attempt([g], ()))
            except PlanError:
                failures += 1
        for fid in requested:
            try:
                plans.append(attempt((), [fid]))
            except PlanError:
                failures += 1
        return plans, failures


def select(arm, case, registry, state, runner):
    """Return (plans, compile_failures, blocked_by_intent)."""
    text = normalize(case["request"])
    if arm == "A":
        workflow = route(text)
        if workflow == "WF-WRITE":
            return [], 0, True
        goals = registry.goal_ports.get(workflow, ()) if workflow else ()
        return (*compile_what_fits(registry, state, goals=goals), False) if goals else ([], 0, False)
    if arm in ("D", "E") and re.search(CHANGE_REQUEST, text):
        return [], 0, True
    if arm == "B":
        scores = registry.retrieve(case["request"], (), state, method="bm25", top_n=K)["scores"]
        skills = [s for s, v in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))
                  if s.startswith("s:") and v > 0][:2]
        eligible = registry.eligible(state)
        members = sorted({fid for s in skills for fid in registry.gsf.by_skill[s[2:]] if fid in eligible})[:K]
        return (*compile_what_fits(registry, state, requested=members, expand=False), False)
    functions = registry.retrieve(case["request"], (), state, method="gos", top_n=K)["functions"]
    return (*compile_what_fits(registry, state, requested=functions, expand=arm != "C"), False)


def run_arm(arm, case, registry):
    replay = environment(case, registry, FIXTURES)
    state, run_case = case_state(case, registry, replay)
    runner = GraphRunner(registry, run_case, state, max_calls=MAX_CALLS)
    plans, failures, blocked = select(arm, case, registry, state, runner)
    attempted = []
    for plan in plans:
        try:
            plan = runner.run(plan)
        except PlanError as exc:
            state.errors.append(str(exc))
        attempted.append(plan)
    if arm == "E" and not blocked:
        seen = {n.function_id for p in attempted for n in p.nodes.values()}
        for _ in range(ROUNDS - 1):
            if runner.calls >= MAX_CALLS:
                break
            fresh = [f for f in registry.retrieve(case["request"], (), state, method="gos", top_n=K,
                                                  excluded=seen)["functions"] if f not in seen]
            if not fresh:
                break
            more, extra_failures = compile_what_fits(registry, state, requested=fresh)
            failures += extra_failures
            seen.update(fresh)
            for plan in more:
                seen.update(n.function_id for n in plan.nodes.values())
                try:
                    attempted.append(runner.run(plan))
                except PlanError as exc:
                    state.errors.append(str(exc))
    goals = registry.goal_ports[case["workflow"]]
    status = "BLOCKED" if blocked else state.case_status(goals, exhausted=True)
    selected = {n.function_id for p in attempted for n in p.nodes.values()}
    executable = failures == 0 and all(n.state in DONE for p in attempted for n in p.nodes.values())
    audits = Counter(a["operator"] for p in {id(p): p for p in runner.plans}.values() for a in p.audit
                     if a["operator"] != "COMPILE")
    return dict(selected=selected, executed=[e["function_id"] for e in state.executed], status=status,
                executable=executable, calls=runner.calls, repairs=dict(audits), capabilities=replay["capabilities"])


def run_reference(name, case, registry):
    replay = environment(case, registry, FIXTURES)
    # Same intent gate as arms D/E: a change request reaches diagnose as turn_type CHANGE.
    change = bool(re.search(CHANGE_REQUEST, normalize(case["request"])))
    result = diagnose(case["request"], replay, registry=registry, route="resolver", workflow=case["workflow"],
                      selection="nba" if name == "R-NBA" else "resolver", turn_type="CHANGE" if change else None)
    executed = [e["function_id"] for e in result.get("graph", {}).get("executed", [])]
    status = result["case_status"]
    return dict(selected=set(executed), executed=executed, status=status, executable=True,
                calls=result.get("graph", {}).get("calls", 0), repairs={}, capabilities=replay["capabilities"])


def score(case, outcome, registry):
    required = set(case["required_functions"])
    goal_ports = set(registry.goal_ports[case["workflow"]])
    producers = {fid for fid in required if set(registry.functions[fid].outputs) & goal_ports}
    prereqs = required - producers
    executed = outcome["executed"]
    allowed = set(outcome["capabilities"])
    return {
        "recall": len(required & outcome["selected"]) / len(required) if required else 1.0,
        "all_required": required <= outcome["selected"],
        "prereq_coverage": (len(prereqs & outcome["selected"]) / len(prereqs)) if prereqs else None,
        "executable": outcome["executable"],
        "precision": (sum(f in required for f in executed) / len(executed)) if executed else None,
        "false_resolution": outcome["status"] == "RESOLVED" and case["expected_status"] != "RESOLVED",
        "policy_violations": sum(registry.functions[f].risk == "WRITE" or f not in allowed for f in executed),
        "status_match": outcome["status"] == case["expected_status"],
        "calls": outcome["calls"],
    }


def aggregate(rows):
    def mean(key):
        values = [r[key] for r in rows if r[key] is not None]
        return round(sum(values) / len(values), 4) if values else None
    latencies = sorted(r["latency_ms"] for r in rows)
    return {"cases": len(rows), "function_recall": mean("recall"),
            "all_required_rate": mean("all_required"), "prerequisite_coverage": mean("prereq_coverage"),
            "executable_plan_rate": mean("executable"), "tool_call_precision": mean("precision"),
            "false_resolution_rate": mean("false_resolution"),
            "false_resolutions": sum(r["false_resolution"] for r in rows),
            "policy_violations": sum(r["policy_violations"] for r in rows),
            "status_match_rate": mean("status_match"), "tool_calls": sum(r["calls"] for r in rows),
            "latency_ms_p50": round(statistics.median(latencies), 2),
            "latency_ms_p95": round(latencies[max(0, int(round(0.95 * len(latencies))) - 1)], 2),
            "repairs_by_operator": dict(sum((Counter(r["repairs"]) for r in rows), Counter()))}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, help="new directory name under runs/")
    args = parser.parse_args()
    out = ROOT / "runs" / args.run
    if out.exists():
        parser.error(f"runs/{args.run} already exists; benchmark runs are never overwritten")
    manifest = read_json(MANIFEST)
    digest = hashlib.sha256(DATA.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        parser.error("dataset SHA-256 does not match its manifest; refusing to run")
    registry = GraphRegistry.from_v01()
    cases = read_json(DATA)["cases"]
    summary = {"dataset": DATA.name, "sha256": digest, "k": K, "max_calls": MAX_CALLS,
               "note": "Synthetic replay on the host; not router measurements.", "splits": {}, "per_case": []}
    for split in ("dev", "holdout"):
        summary["splits"][split] = {}
        for name in (*ARMS, *REFERENCES):
            rows = []
            tracemalloc.start()
            for case in (c for c in cases if c["split"] == split):
                started = time.perf_counter()
                outcome = (run_reference if name in REFERENCES else run_arm)(name, case, registry)
                row = score(case, outcome, registry)
                row.update(latency_ms=1000 * (time.perf_counter() - started), repairs=outcome["repairs"])
                rows.append(row)
                summary["per_case"].append({"split": split, "arm": name, "case": case["id"],
                                            "status": outcome["status"], "expected": case["expected_status"],
                                            "selected": sorted(outcome["selected"]), "executed": outcome["executed"],
                                            **{k: v for k, v in row.items() if k != "repairs"}})
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            summary["splits"][split][name] = {**aggregate(rows), "tracemalloc_peak_bytes": peak}
    summary["process_peak_rss_bytes"] = rss_bytes()
    out.mkdir(parents=True)
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "REPORT_VI.md").write_text(report(summary), encoding="utf-8")
    print(report(summary))


def report(summary):
    cols = [("function_recall", "Recall"), ("all_required_rate", "Đủ hết"), ("prerequisite_coverage", "Tiền đề"),
            ("executable_plan_rate", "Plan chạy được"), ("tool_call_precision", "Precision"),
            ("false_resolutions", "False-res"), ("policy_violations", "Vi phạm"), ("status_match_rate", "Đúng status"),
            ("tool_calls", "Lượt gọi"), ("latency_ms_p50", "p50 ms"), ("latency_ms_p95", "p95 ms")]
    lines = ["# Benchmark Function Selection v1 (T9)", "",
             f"Dữ liệu `{summary['dataset']}` · SHA-256 `{summary['sha256']}` · K = {summary['k']} · "
             f"ngân sách {summary['max_calls']} lượt gọi mỗi ca.", "",
             "**Mọi số là replay tổng hợp trên host Windows, không phải số đo trên router/OpenWrt.**", ""]
    for split, arms in summary["splits"].items():
        lines += [f"## {split} ({next(iter(arms.values()))['cases']} ca)", "",
                  "| Arm | " + " | ".join(label for _, label in cols) + " | Repair |",
                  "|---|" + "---:|" * len(cols) + "---|"]
        for name, row in arms.items():
            lines.append(f"| {name} | " + " | ".join("—" if row[key] is None else str(row[key]) for key, _ in cols)
                         + f" | {row['repairs_by_operator'] or '—'} |")
        lines.append("")
    lines.append(f"RSS đỉnh của tiến trình: {summary['process_peak_rss_bytes']} byte (cả lượt chạy, mọi arm).")
    return "\n".join(lines) + "\n"


FIXTURES = {c["id"]: c for c in read_json(ROOT / "data/cases.json")}

if __name__ == "__main__":
    main()
