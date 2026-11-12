"""Run the HTML operations examples in an isolated local replay directory."""

import argparse
import hashlib
import hmac
import json
from pathlib import Path

from gateway_pilot.lifecycle import preflight_artifact
from gateway_pilot.monitor import THRESHOLDS, monitor_window
from gateway_pilot.operations import ReplayOperations


def run(output):
    output.mkdir(parents=True)
    now = 1_800_000_000
    target, identity = "laptop-an", "replay-device-01"
    policy = {"rate_mbps": 50}

    def postcheck(device, observed_identity):
        return {"id": "qos-postcheck-1", "observed_at": now + 2, "target": device,
                "identity": observed_identity, "effective_policy": policy,
                "target_before_ms": 35, "target_after_ms": 27,
                "other_before_ms": 25, "other_after_ms": 27}

    database = output / "replay.sqlite"
    ops = ReplayOperations(database, qos_postcheck=postcheck)
    try:
        ops.register_device(target, identity)
        for scope in ("qos.write", "schedule.write", "access.write"):
            ops.grant("owner", scope, now + 900, target=target)
        ops.grant("reviewer", "change.approve", now + 900, target=target)
        plan = ops.plan_qos("owner", target, policy, now)
        ops.approve_qos(plan["plan_id"], "reviewer", now + 1, now + 60)
        receipt = ops.apply_qos("owner", plan["plan_id"], "qos-replay-1", now + 2)
        ops.schedule_block("replay-job-1", "owner", target, now + 30, now + 90, now + 2)
        approval = ops.approve_schedule("replay-job-1", "reviewer", now + 3)
    finally:
        ops.close()
    reopened = ReplayOperations(database, qos_postcheck=postcheck)
    try:
        activation = reopened.tick(now + 30)
        active = reopened.internet_blocked(target, now + 30)
        expiration = reopened.tick(now + 90)
        ended = not reopened.internet_blocked(target, now + 90)
    finally:
        reopened.close()

    metrics = {metric: 50 for metric in THRESHOLDS}
    metrics.update(dhcp_pool_free_pct=3, radio_busy_pct=92)
    samples = [{"id": f"monitor-{i}", "source": "synthetic_replay", "target": "gateway-01",
                "boot_id": "boot-1", "config_version": "cfg-1", "observed_at": now + 60 * i,
                "metrics": metrics} for i in range(3)]
    monitored = monitor_window(samples, now + 120)
    artifact = output / "fixture-artifact.bin"
    artifact.write_bytes(b"test fixture, not firmware")
    metadata = {"kind": "firmware", "platform": "replay-board", "revision": 2,
                "size_bytes": artifact.stat().st_size,
                "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}
    key = b"fixture-only"
    payload = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
    manifest = {**metadata, "signature": hmac.digest(key, payload, "sha256")}
    preflight = preflight_artifact(
        artifact, manifest, platform="replay-board", current_revision=1, free_bytes=10_000,
        capabilities={"lifecycle.firmware.preflight"}, recovery_verified=True,
        verify_signature=lambda message, signature: hmac.compare_digest(hmac.digest(key, message, "sha256"), signature),
    )
    trace = {
        "execution": "synthetic_replay", "WF-031": {"plan": plan, "receipt": receipt},
        "WF-063": {"approval": approval, "activation": activation, "blocked_in_window": active,
                   "expiration": expiration, "unblocked_after_window": ended},
        "WF-054": monitored, "WF-081": preflight,
    }
    if (receipt["status"] != "APPLIED" or not active or not ended
            or monitored["case_status"] != "RESOLVED" or preflight["status"] != "PREFLIGHT_OK"):
        raise RuntimeError(f"Operations replay did not satisfy its expected transitions: {trace}")
    with (output / "trace.json").open("x", encoding="utf-8") as stream:
        json.dump(trace, stream, ensure_ascii=False, indent=2)
    return trace


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
    print("OPERATIONS_REPLAY_OK")
