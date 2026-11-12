"""C5 conversation benchmark: legacy regex vs Turn Router vs Turn Router + local LLM advisor.

All numbers are synthetic replay on the host, never router measurements. The
router thresholds were not re-calibrated for this run; the holdout is run once.

Usage:  python -m scripts.benchmarks.run_conversation_benchmark --run conversation_v1_YYYYMMDD [--configs regex,router,advisor]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmarks"))

from build_conversation_v1 import replay as environment  # noqa: E402
from gateway_pilot.assistant import answer  # noqa: E402
from gateway_pilot.core import read_json  # noqa: E402
from gateway_pilot.graph_v3.graphs import GraphRegistry  # noqa: E402
from gateway_pilot.session import SessionStore  # noqa: E402
from gateway_pilot.workflow import MESSAGES, diagnose, normalize, route, workflow_registry  # noqa: E402

DATA = ROOT / "benchmarks/conversation_v1.json"
MANIFEST = ROOT / "benchmarks/conversation_v1.manifest.json"
NON_MEASUREMENT = {"SMALLTALK", "KNOWLEDGE", "CHANGE", "CAPABILITY", "OUT_OF_SCOPE"}
MUST_NOT_RUN = {"SMALLTALK", "KNOWLEDGE", "CHANGE"}


def run_regex(item, ctx):
    """Baseline: the pre-C2 entry point, each turn independent (no session)."""
    outputs = []
    for turn in item["turns"]:
        workflow = route(normalize(turn["message"]))
        result = diagnose(turn["message"], ctx["legacy_replay"], registry=ctx["legacy"])
        kind = "CHANGE" if workflow == "WF-WRITE" else ("DIAGNOSE" if workflow else "UNKNOWN")
        executed = [e["function_id"] for e in result.get("graph", {}).get("executed", [])]
        outputs.append(dict(turn_type=kind, top1=[workflow] if workflow else [], top3=[workflow] if workflow else [],
                            executed=executed, case_status=result["case_status"],
                            answer=result["terminal"]["response"], asked=result["case_status"] == "NEEDS_INPUT"))
    return outputs


def run_router(item, ctx, advisor=None):
    session = SessionStore().get()
    outputs = []
    for turn in item["turns"]:
        result = answer(turn["message"], ctx["replay"], registry=ctx["registry"], session=session, advisor=advisor)
        router = result.get("router") or {}
        hint = router.get("plan_hint") or {}
        top3 = [c["id"] for c in router.get("workflow_candidates", ())]
        top1 = list(hint.get("workflows") or ([result["workflow"]] if result.get("workflow") else top3[:1]))
        if result.get("workflow") and result["turn_type"] == "FOLLOW_UP":
            top1, top3 = [result["workflow"]], [result["workflow"], *top3]
        executed = [e["function_id"] for e in result.get("graph", {}).get("executed", [])]
        outputs.append(dict(turn_type=result["turn_type"], top1=top1, top3=list(dict.fromkeys(top1 + top3)),
                            executed=executed, case_status=result.get("case_status"), answer=result.get("answer", ""),
                            asked=result.get("case_status") == "NEEDS_INPUT" or router.get("action") == "ASK_USER"))
    return outputs


def turn_metrics(label, out):
    wanted = label.get("workflows")
    row = {"turn_type": label["turn_type"], "type_ok": out["turn_type"] == label["turn_type"],
           "calls": len(out["executed"]), "latency_ms": out["latency_ms"]}
    if wanted:
        row["top1"] = set(wanted) <= set(out["top1"])
        row["top3"] = set(wanted) <= set(out["top3"])
    required = set(label.get("required_functions", ()))
    if label["action"] == "RUN" and required:
        row["recall"] = len(required & set(out["executed"])) / len(required)
        row["all_required"] = required <= set(out["executed"])
    if label["action"] != "ASK_USER":
        row["unneeded_clarification"] = out["asked"]
    if label["turn_type"] in NON_MEASUREMENT:
        row["wrong_tool_run"] = bool(out["executed"])
    row["false_resolution"] = out["case_status"] == "RESOLVED" and label.get("expected_status") != "RESOLVED"
    if label["turn_type"] != "OUT_OF_SCOPE":
        text = (out["answer"] or "").strip()
        row["empty_or_unclear"] = not text or MESSAGES["intent_unclear"] in text
    return row


def aggregate(rows):
    def rate(key, subset=None):
        values = [r[key] for r in (subset if subset is not None else rows) if key in r]
        return (round(sum(values) / len(values), 4), len(values)) if values else (None, 0)
    latencies = sorted(r["latency_ms"] for r in rows)
    must = [r for r in rows if r["turn_type"] in MUST_NOT_RUN]
    return {"turns": len(rows), "turn_type_accuracy": rate("type_ok"), "workflow_top1": rate("top1"),
            "workflow_top3": rate("top3"), "function_recall": rate("recall"), "all_required_rate": rate("all_required"),
            "unneeded_clarification_rate": rate("unneeded_clarification"),
            "wrong_tool_run_rate_smalltalk_knowledge_change": rate("wrong_tool_run", must),
            "wrong_tool_run_rate_all_non_measurement": rate("wrong_tool_run"),
            "false_resolution_rate": rate("false_resolution"), "empty_or_unclear_rate_in_scope": rate("empty_or_unclear"),
            "tool_calls": sum(r["calls"] for r in rows), "latency_ms_p50": round(statistics.median(latencies), 1),
            "latency_ms_p95": round(latencies[max(0, int(round(0.95 * len(latencies))) - 1)], 1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--configs", default="regex,router,advisor")
    args = parser.parse_args()
    out_dir = ROOT / "runs" / args.run
    if out_dir.exists():
        parser.error(f"runs/{args.run} already exists; benchmark runs are never overwritten")
    manifest = read_json(MANIFEST)
    digest = hashlib.sha256(DATA.read_bytes()).hexdigest()
    if digest != manifest["sha256"]:
        parser.error("dataset SHA-256 does not match its manifest; refusing to run")
    registry, legacy = GraphRegistry.from_v01(), workflow_registry()
    ctx = {"registry": registry, "replay": environment(registry), "legacy": legacy,
           "legacy_replay": environment(legacy)}
    configs = args.configs.split(",")
    advisor, advisor_note = None, None
    if "advisor" in configs:
        from gateway_pilot.workflow_advisor import OllamaProbeAdvisor
        try:
            advisor = OllamaProbeAdvisor("qwen3:1.7b", endpoint="http://127.0.0.1:11434", timeout=25)
        except (OSError, ValueError, RuntimeError, KeyError) as exc:
            advisor_note = f"advisor unavailable: {type(exc).__name__}"
            configs.remove("advisor")
    items = read_json(DATA)["items"]
    summary = {"dataset": DATA.name, "sha256": digest, "advisor_model": "qwen3:1.7b" if advisor else None,
               "advisor_note": advisor_note, "note": "Synthetic replay on the host; not router measurements.",
               "splits": {}, "per_turn": []}
    for split in ("dev", "holdout"):
        summary["splits"][split] = {}
        for config in configs:
            rows = []
            for item in (i for i in items if i["split"] == split):
                started = time.perf_counter()
                outputs = (run_regex(item, ctx) if config == "regex" else
                           run_router(item, ctx, advisor if config == "advisor" else None))
                per_turn_ms = 1000 * (time.perf_counter() - started) / len(outputs)
                for label, out in zip(item["turns"], outputs):
                    out["latency_ms"] = per_turn_ms
                    row = turn_metrics(label, out)
                    rows.append(row)
                    summary["per_turn"].append({"split": split, "config": config, "item": item["id"],
                                                "message": label["message"], "label": label["turn_type"],
                                                "predicted": out["turn_type"], "top1": out["top1"],
                                                "case_status": out["case_status"], "calls": row["calls"],
                                                **{k: v for k, v in row.items() if k not in ("turn_type", "calls")}})
            summary["splits"][split][config] = aggregate(rows)
    out_dir.mkdir(parents=True)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out_dir / "REPORT_VI.md").write_text(report(summary), encoding="utf-8")
    print(report(summary))


def report(summary):
    keys = [("turn_type_accuracy", "Đúng loại lượt"), ("workflow_top1", "Workflow top-1"),
            ("workflow_top3", "Workflow top-3"), ("function_recall", "Recall Function"),
            ("unneeded_clarification_rate", "Hỏi lại thừa"),
            ("wrong_tool_run_rate_smalltalk_knowledge_change", "Gọi tool sai (S/K/C)"),
            ("false_resolution_rate", "False-res"), ("empty_or_unclear_rate_in_scope", "Rỗng/không hiểu")]
    lines = ["# Benchmark hội thoại v1 (C5)", "", f"Dữ liệu `{summary['dataset']}` · SHA-256 `{summary['sha256']}`.",
             "", "**Mọi số là replay tổng hợp trên host Windows, không phải số đo trên router.** "
             "Mỗi ô: tỉ lệ (số lượt được tính).", ""]
    if summary["advisor_note"]:
        lines += [f"Cấu hình advisor không chạy: {summary['advisor_note']}.", ""]
    for split, configs in summary["splits"].items():
        lines += [f"## {split}", "", "| Cấu hình | " + " | ".join(label for _, label in keys) + " | Lượt gọi | p50 ms | p95 ms |",
                  "|---|" + "---:|" * (len(keys) + 3)]
        for name, row in configs.items():
            cells = ["—" if row[k][0] is None else f"{row[k][0]} ({row[k][1]})" for k, _ in keys]
            lines.append(f"| {name} | " + " | ".join(cells) + f" | {row['tool_calls']} | {row['latency_ms_p50']} | "
                         f"{row['latency_ms_p95']} |")
        lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
