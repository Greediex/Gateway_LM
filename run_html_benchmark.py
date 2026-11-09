"""Score replay outcomes, evidence and state effects for six HTML workflows."""

import argparse
import hashlib
import hmac
import json
import math
import platform
import tempfile
from collections import defaultdict
from pathlib import Path
from time import perf_counter_ns

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.lifecycle import preflight_artifact
from gateway_pilot.monitor import monitor_window
from gateway_pilot.operations import OperationDenied, ReplayOperations
from gateway_pilot.workflow import diagnose, workflow_registry


DIMENSIONS = ("outcome", "evidence", "effect")
DEFAULT_CASES = ROOT / "benchmarks" / "html_workflows_v1.json"
TARGET = "client-living-room"


def internet(inputs, registry):
    gateway = {
        "wan.status": {"link_up": True}, "wan.routes": {"default_route": True},
        "wan.probe": {"loss_pct": 0}, "dns.config": {"resolver": "192.168.50.1"},
        "dns.probe": {"rcode": "NOERROR", "query": "portal.test"},
    }
    client = {
        "clients.resolve": {"client_id": TARGET}, "wifi.station": {"associated": True, "rssi_dbm": -55},
        "client.ipv4": {"address": "192.168.50.42", "configured": True},
        "client.probe": {"loss_pct": 0}, "client.dns": {"rcode": "NOERROR", "query": "portal.test"},
    }
    for world, name in ((gateway, "gateway"), (client, "client")):
        for tool, change in inputs.get(name, {}).items():
            world[tool].update(change)
    devices = [{"selector": "máy tính phòng khách", "client_id": TARGET, "world": client}]
    if inputs.get("duplicate_alias"):
        devices.append({"selector": "máy tính dự phòng", "aliases": ["máy tính phòng khách"],
                        "client_id": "client-other", "world": {}})
    caps = sorted((gateway.keys() | client.keys()) - set(inputs.get("disable", [])))
    result = diagnose(
        "Máy tính phòng khách vẫn có Wi-Fi nhưng không mở được trang web.",
        {"world": gateway, "devices": devices, "capabilities": caps,
         "permissions": inputs.get("permissions", ["network.read"])},
        registry=registry,
    )
    graph = result.get("graph", {})
    terminal = result["terminal"]
    by_id = {row["id"]: row for row in graph.get("evidence", [])}
    ids = terminal["evidence_ids"]
    cited = [by_id.get(key) for key in ids]
    valid = len(set(ids)) == len(ids) and all(
        row and row["status"] == "OK" and row["target"] == (TARGET if row["scope"] == "client" else "gateway_01")
        for row in cited)
    return {
        "outcome": {"status": result["case_status"], "diagnosis": terminal["diagnosis"],
                    "workflow_id": result["workflow_id"]},
        "evidence": {"ports": sorted(row["port"] for row in cited if row), "valid": valid},
        "effect": {"calls": graph.get("calls", 0), "writes": sum(
            registry.functions[row["function_id"]].risk == "WRITE" for row in graph.get("executed", []))},
    }


def provision(ops):
    ops.register_device(TARGET, "device-001")
    ops.register_device("client-other", "device-002")
    for scope in ("qos.write", "access.write", "schedule.write"):
        ops.grant("owner", scope, 2_000, target=TARGET)
    ops.grant("reviewer", "change.approve", 2_000, target=TARGET)


def qos(inputs, scratch):
    policy = inputs.get("policy", {"rate_mbps": 60})
    apply_at = inputs.get("apply_at", 1_005)
    calls = 0

    def postcheck(target, identity):
        nonlocal calls
        calls += 1
        return {"id": "postcheck-bench", "observed_at": apply_at, "target": target,
                "identity": identity, "effective_policy": policy, "target_before_ms": 34,
                "target_after_ms": 25, "other_before_ms": 22, "other_after_ms": 24,
                **inputs.get("postcheck", {})}

    ops = ReplayOperations(scratch / "state.sqlite", qos_postcheck=postcheck)
    try:
        provision(ops)
        plan = ops.plan_qos("owner", TARGET, policy, 1_000)["plan_id"]
        ops.approve_qos(plan, "reviewer", 1_001, inputs.get("approval_expiry", 1_040))
        if inputs.get("revoke_approval"):
            ops.grant("reviewer", "change.approve", 1_004, target=TARGET)
        try:
            receipt = ops.apply_qos("owner", plan, "bench-key", apply_at)
        except OperationDenied as exc:
            receipt = {"status": "BLOCKED", "reason": str(exc)}
        outcome = {"status": receipt["status"], "reason": receipt.get("reason")}
        if inputs.get("retry"):
            outcome["same_receipt"] = ops.apply_qos("owner", plan, "bench-key", apply_at + 1) == receipt
        stored_policy = ops.device(TARGET)["qos"]
        return {
            "outcome": outcome,
            "evidence": {"postcheck_calls": calls, "cited": receipt.get("postcheck_evidence_id") == "postcheck-bench"},
            "effect": {"version": ops.db.execute("SELECT version FROM config").fetchone()[0],
                       "policy": json.loads(stored_policy) if stored_policy else None,
                       "receipts": ops.db.execute("SELECT count(*) FROM receipts").fetchone()[0]},
        }
    finally:
        ops.close()


def schedule(inputs, scratch):
    path = scratch / "state.sqlite"
    ops = ReplayOperations(path, qos_postcheck=None)
    try:
        provision(ops)
        ops.schedule_block("bench-job", "owner", TARGET, 1_010, 1_040, 1_000)
        if inputs.get("approve", True):
            ops.approve_schedule("bench-job", "reviewer", 1_001)
        if inputs.get("revoke_approval"):
            ops.grant("reviewer", "change.approve", 1_009, target=TARGET)
        if inputs.get("replace_identity"):
            ops.register_device(TARGET, "device-new")
    finally:
        ops.close()
    restarted = ReplayOperations(path, qos_postcheck=None)
    try:
        events, blocked, other_blocked = [], [], []
        for now in inputs["ticks"]:
            events.extend(restarted.tick(now))
            if now == inputs.get("cancel_at"):
                events.append(restarted.cancel("bench-job", "owner", now))
            blocked.append(restarted.internet_blocked(TARGET, now))
            other_blocked.append(restarted.internet_blocked("client-other", now))
        return {
            "outcome": {"status": restarted.db.execute("SELECT status FROM jobs").fetchone()[0],
                        "events": [row["status"] for row in events], "reason": events[-1]["reason"] if events else None},
            "evidence": {"audit": [row[0] for row in restarted.db.execute("SELECT status FROM job_events ORDER BY seq")]},
            "effect": {"blocked": blocked, "other_blocked": any(other_blocked)},
        }
    finally:
        restarted.close()


def monitor(inputs):
    defaults = {"cpu_pct": 45, "available_ram_pct": 50, "storage_used_pct": 45,
                "dhcp_success_pct": 99, "radio_busy_pct": 35, "dhcp_pool_free_pct": 50,
                "conntrack_used_pct": 45}
    rows = []
    for index in range(3):
        rows.append({"id": f"sample-{index}", "target": "gateway-01", "source": "collector-replay",
                     "boot_id": "bench-boot", "config_version": "bench-config",
                     "observed_at": 1_000 + 60 * index,
                     "metrics": {**defaults, **{key: values[index] for key, values in inputs.get("metrics", {}).items()}},
                     **inputs.get("sample_updates", {}).get(str(index), {})})
    before = json.dumps(rows, sort_keys=True)
    result = monitor_window(rows, 1_120)
    alerts = result["alerts"]
    cited = {key for alert in alerts for key in alert["evidence_ids"]}
    valid = all(alert["evidence_ids"] == [row["id"] for row in rows]
                and alert["target"] == rows[-1]["target"] and alert["source"] == rows[-1]["source"]
                for alert in alerts)
    return {
        "outcome": {"status": result["case_status"], "reason": result["reason"],
                    "alerts": sorted(alert["metric"] for alert in alerts), "missing": result["missing_metrics"]},
        "evidence": {"cited": len(cited), "valid": valid},
        "effect": {"writes": int(before != json.dumps(rows, sort_keys=True))},
    }


def lifecycle(workflow, inputs, scratch):
    kind = "model" if workflow == "WF-047" else "firmware"
    contents = f"benchmark fixture for {kind}".encode("utf-8")
    digest = hashlib.sha256(contents).hexdigest()
    metadata = {"kind": kind, "platform": "bench-board", "revision": 3,
                "size_bytes": len(contents), "sha256": digest}
    key = b"local-benchmark-fixture"
    payload = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.digest(key, payload, "sha256")
    manifest = {**metadata, "signature": signature}
    corruption = inputs.get("corruption")
    if corruption == "manifest":
        manifest["revision"] = 4
    if corruption == "signature":
        manifest["signature"] = bytes(len(signature))
    if corruption == "payload":
        contents = b"x" * len(contents)
    if corruption == "size":
        contents += b"x"
    artifact = scratch / "input.bin"
    artifact.write_bytes(contents)
    signature_calls = 0

    def verify(message, signed):
        nonlocal signature_calls
        signature_calls += 1
        return hmac.compare_digest(hmac.digest(key, message, "sha256"), signed)

    result = preflight_artifact(
        artifact, manifest, platform=inputs.get("platform", "bench-board"),
        current_revision=inputs.get("current_revision", 2), free_bytes=inputs.get("free_bytes", 4096),
        capabilities={f"lifecycle.{kind}.preflight"} if inputs.get("capability", True) else set(),
        recovery_verified=inputs.get("recovery_verified", True),
        verify_signature=None if inputs.get("no_verifier") else verify,
    )
    return {
        "outcome": {"status": result["status"], "reason": result.get("reason"),
                    "workflow_id": result.get("workflow_id")},
        "evidence": {"signature_calls": signature_calls, "digest_match": result.get("sha256") == digest},
        "effect": {"artifact_unchanged": artifact.read_bytes() == contents},
    }


def grade(actual, expected):
    return {
        name: all(key in actual[name] and actual[name][key] == value for key, value in expected[name].items())
        for name in DIMENSIONS
    }


def summarize(rows, repeats):
    by_workflow, by_case = defaultdict(list), defaultdict(list)
    for row in rows:
        by_workflow[row["workflow"]].append(row)
        by_case[row["case_id"]].append(row["pass"])
    workflow_scores = {}
    for workflow, trials in sorted(by_workflow.items()):
        ordered = sorted(row["wall_ms"] for row in trials)
        workflow_scores[workflow] = {
            "trials": len(trials), "pass": sum(row["pass"] for row in trials),
            **{name: sum(row["checks"][name] for row in trials) for name in DIMENSIONS},
            "p50_ms": round(ordered[math.ceil(len(ordered) * .5) - 1], 3),
            "p95_ms": round(ordered[math.ceil(len(ordered) * .95) - 1], 3),
        }
    return {"cases": len(by_case), "repeats": repeats, "trials": len(rows),
            "trials_pass": sum(row["pass"] for row in rows),
            "cases_pass_all_repeats": sum(all(passed) for passed in by_case.values()),
            "failed_cases": [key for key, passed in by_case.items() if not all(passed)],
            "workflows": workflow_scores}


def render_report(summary):
    report = [
        "# Benchmark Gateway LM theo HTML", "",
        f"**{summary['cases_pass_all_repeats']}/{summary['cases']} ca** pass mọi lượt. "
        f"**{summary['trials_pass']}/{summary['trials']} lượt** pass cả outcome, evidence và state effect.",
        "",
        "| Workflow | Pass | Outcome | Evidence | State effect | p50 (ms) | p95 (ms) |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for workflow, score in summary["workflows"].items():
        report.append(f"| {workflow} | {score['pass']}/{score['trials']} | {score['outcome']} | "
                      f"{score['evidence']} | {score['effect']} | {score['p50_ms']} | {score['p95_ms']} |")
    report.extend(["", "Ca fail gồm " + ", ".join(summary["failed_cases"]) + "."]
                  if summary["failed_cases"] else [])
    report.extend(["", "Độ trễ là wall time của handler replay, gồm dựng fixture hoặc SQLite khi có. "
                   "Mỗi lượt dùng dữ liệu và trạng thái mới. Bộ đo chạy Core trên host, với 0 lượt gọi model.",
                   "", "Chi tiết từng lượt trong [episodes.jsonl](episodes.jsonl)."])
    return "\n".join(report) + "\n"


def run(catalog, output, repeats):
    fixture_bytes = catalog.read_bytes()
    fixtures = json.loads(fixture_bytes)
    registry = workflow_registry()
    handlers = {
        "WF-018": lambda values, _: internet(values, registry),
        "WF-031": qos,
        "WF-047": lambda values, scratch: lifecycle("WF-047", values, scratch),
        "WF-054": lambda values, _: monitor(values),
        "WF-063": schedule,
        "WF-081": lambda values, scratch: lifecycle("WF-081", values, scratch),
    }
    cases = fixtures["cases"]
    if (not cases or len({case["id"] for case in cases}) != len(cases)
            or any(case["workflow"] not in handlers or set(case["expected"]) != set(DIMENSIONS)
                   or not all(case["expected"].values()) for case in cases)):
        raise ValueError("Each unique case needs a supported workflow and all three grading dimensions")
    output.mkdir(parents=True)
    rows = []
    with (output / "episodes.jsonl").open("x", encoding="utf-8") as stream:
        for trial in range(1, repeats + 1):
            for case in cases:
                with tempfile.TemporaryDirectory(dir=output) as scratch:
                    started = perf_counter_ns()
                    try:
                        actual = handlers[case["workflow"]](case["input"], Path(scratch))
                        if case["workflow"] in ("WF-018", "WF-047", "WF-081"):
                            expected = {**case["expected"], "outcome": {
                                **case["expected"]["outcome"], "workflow_id": case["workflow"]}}
                        else:
                            expected = case["expected"]
                        checks = grade(actual, expected)
                    except Exception as exc:
                        actual = {"error": f"{type(exc).__name__}: {exc}"}
                        expected = case["expected"]
                        checks = dict.fromkeys(DIMENSIONS, False)
                    wall_ms = (perf_counter_ns() - started) / 1_000_000
                row = {"case_id": case["id"], "workflow": case["workflow"], "trial": trial,
                       "expected": expected, "actual": actual, "checks": checks,
                       "pass": all(checks.values()), "wall_ms": wall_ms}
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                rows.append(row)
            stream.flush()
    summary = summarize(rows, repeats)
    paths = [Path(__file__), *sorted((ROOT / "gateway_pilot").rglob("*.py")), ROOT / "data" / "registry.json",
             ROOT / "third_party" / "graph-of-skills" / "gos" / "core" / "retrieval.py"]
    summary.update(execution="synthetic_replay", model_calls=0, fixture_version=fixtures["version"],
                   fixture_sha256=hashlib.sha256(fixture_bytes).hexdigest(), python=platform.python_version(),
                   source_sha256={path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in paths})
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "REPORT.md").write_text(render_report(summary), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeat", type=int, default=3, choices=range(1, 21), metavar="1-20")
    args = parser.parse_args()
    summary = run(args.cases, args.output, args.repeat)
    print(json.dumps({key: summary[key] for key in ("cases", "trials", "trials_pass",
                                                    "cases_pass_all_repeats", "failed_cases")}))
    raise SystemExit(0 if summary["trials_pass"] == summary["trials"] else 1)
