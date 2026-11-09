"""Evaluate the HTML-aligned workflow and optionally compare local model probe ordering."""

import argparse
import json
from collections import Counter
from hashlib import sha256
from pathlib import Path
from time import perf_counter

from .core import ROOT, read_json
from .graph_v3.upstream import COMMIT, KERNEL_SHA256
from .workflow import diagnose, replay_from_fixture, workflow_registry
from .workflow_advisor import OllamaProbeAdvisor


PROBE_CASES = (
    ("dns-vi-1", "Laptop An có Wi-Fi nhưng trình duyệt báo không tìm được tên miền.",
     "dns.probe"),
    ("dns-vi-2", "Laptop An đang bắt Wi-Fi. Mở web thì trình duyệt báo lỗi phân giải địa chỉ.",
     "dns.probe"),
    ("dns-en", "Laptop An is on Wi-Fi, but websites fail with a domain name resolution error.",
     "dns.probe"),
    ("ip-vi-1", "Laptop An có Wi-Fi nhưng gõ địa chỉ IP trực tiếp cũng không kết nối được.",
     "client.probe"),
    ("ip-vi-2", "Laptop An vẫn bắt Wi-Fi. Từ máy ping thẳng IP ngoài mạng cũng mất hết gói.",
     "client.probe"),
    ("ip-en", "Laptop An is connected to Wi-Fi but direct IP addresses also time out.",
     "client.probe"),
)


def write_row(stream, row):
    stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    stream.flush()


def run_suite(output, advisor=None):
    manifest = read_json(ROOT / "data" / "frozen_manifest.json")
    for name, digest in manifest["sha256"].items():
        if sha256((ROOT / "data" / name).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Frozen fixture changed: {name}")
    output.mkdir(parents=True)
    registry = workflow_registry()
    cases = read_json(ROOT / "data" / "cases.json")
    counts = {"dev": Counter(), "test": Counter()}
    differences = []
    with (output / "core.jsonl").open("x", encoding="utf-8") as stream:
        for case in cases:
            row = diagnose(case["request"], replay_from_fixture(case, registry), registry=registry, dynamic=False)
            actual = {key: row["terminal"][key] for key in ("action", "diagnosis")}
            route_match = row["workflow"] == case["workflow"]
            verdict_match = actual == case["gold"]
            counts[case["split"]].update(cases=1, route_match=route_match, verdict_match=verdict_match,
                                         calls=row.get("graph", {}).get("calls", 0))
            if not route_match or not verdict_match:
                differences.append({"case_id": case["id"], "expected": case["gold"], "actual": actual})
            write_row(stream, {"case_id": case["id"], "split": case["split"], **row})
    summary = {"execution": "synthetic_replay", "core": counts, "differences": differences,
               "dataset_sha256": manifest["sha256"], "gos": {"commit": COMMIT, "sha256": KERNEL_SHA256},
               "advisor": None}
    if advisor is not None:
        reference = next(case for case in cases if case["id"] == "GLM-21-0")
        totals = Counter()
        with (output / "advisor.jsonl").open("x", encoding="utf-8") as stream:
            for case_id, request, expected in PROBE_CASES:
                replay = replay_from_fixture(reference, registry)
                replay["capabilities"] = [*replay["capabilities"], "client.probe"]
                dns_fault = expected == "dns.probe"
                replay["world"]["dns.probe"] = {**replay["world"]["dns.probe"],
                                                "rcode": "SERVFAIL" if dns_fault else "NOERROR"}
                replay["devices"][0]["world"]["client.probe"] = {"loss_pct": 0 if dns_fault else 80}
                baseline = diagnose(request, replay, registry=registry, dynamic=False)
                started = perf_counter()
                row = diagnose(request, replay, registry=registry, advisor=advisor, dynamic=False)
                wall_s = perf_counter() - started
                events = row.get("graph", {}).get("advice", [])
                selected = events[0]["selected"] if events and events[0]["accepted"] else None
                diagnosis = "gateway_dns_failure" if dns_fault else "client_path_loss"
                calls = row["graph"]["calls"]
                base_calls = baseline["graph"]["calls"]
                totals.update(cases=1, requests=len(events), accepted=selected is not None,
                              preferred_probe_match=selected == expected,
                              core_terminal_match=row["terminal"]["diagnosis"] == diagnosis,
                              core_only_calls=base_calls, assisted_calls=calls)
                write_row(stream, {"case_id": case_id, "expected_first_probe": expected,
                                   "expected_diagnosis": diagnosis, "core_only_calls": base_calls,
                                   "wall_s": wall_s, **row})
                print(f"{case_id}: selected={selected} expected={expected} calls={base_calls}->{calls}",
                      flush=True)
        summary["advisor"] = {"model": advisor.model, "parameter_count": advisor.parameter_count,
                              **totals, "scope": "six curated synthetic probe-order cases"}
    sources = [*sorted((ROOT / "gateway_pilot" / "graph_v3").glob("*.py")),
               *(ROOT / "gateway_pilot" / name for name in
                 ("workflow.py", "workflow_advisor.py", "workflow_eval.py", "core.py", "run.py"))]
    summary["source_sha256"] = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                                for path in sources}
    with (output / "summary.json").open("x", encoding="utf-8") as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", help="Optional local Ollama advisor with fewer than 3B parameters")
    args = parser.parse_args()
    advisor = OllamaProbeAdvisor(args.model) if args.model else None
    summary = run_suite(args.output, advisor)
    print(json.dumps({"core": summary["core"], "advisor": summary["advisor"]}, ensure_ascii=True))


if __name__ == "__main__":
    main()
