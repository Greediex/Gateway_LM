"""Summarize *externally captured* model inference timings on the target.

Never produce synthetic TTFT/throughput data. Hardware provenance and
firmware/NPU measurements are independent inputs; CI cannot sign them.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path


FIELDS = {
    "sample_id", "model_sha256", "backend", "input_tokens", "output_tokens",
    "ttft_ms", "total_ms", "rss_peak_bytes",
}


def percentile(values, fraction):
    ordered = sorted(values)
    index = max(0, math.ceil(len(ordered)*fraction)-1)
    return round(ordered[index], 3)


def summarize(rows, hardware):
    if not isinstance(rows, list) or not 2 <= len(rows) <= 5000:
        raise ValueError("invalid_inference_sample_count")
    ids, models, backends, data = set(), set(), set(), []
    for row in rows:
        if not isinstance(row, dict) or set(row) != FIELDS:
            raise ValueError("invalid_inference_record")
        sid, model, backend = row["sample_id"], row["model_sha256"], row["backend"]
        if (not isinstance(sid, str) or not sid or len(sid) > 128
                or sid in ids or not isinstance(model, str)
                or len(model) != 64 or any(c not in "0123456789abcdef" for c in model)
                or backend not in {"qnn_htp", "cpu", "gpu", "other"}):
            raise ValueError("invalid_inference_metadata")
        ids.add(sid)
        models.add(model)
        backends.add(backend)
        if any(type(row[k]) is not int or row[k] < 0 for k in (
            "input_tokens", "output_tokens", "rss_peak_bytes"
        )):
            raise ValueError("invalid_inference_token_or_memory")
        if any(type(row[k]) not in (int, float) or
               not math.isfinite(row[k]) or row[k] < 0 for k in (
                   "ttft_ms", "total_ms"
               )) or row["total_ms"] < row["ttft_ms"]:
            raise ValueError("invalid_inference_time")
        data.append(row)
    if len(models) != 1 or len(backends) != 1:
        raise ValueError("inference_model_backend_mixed")
    if not isinstance(hardware, dict) or "device_acceptance_possible" not in hardware:
        raise ValueError("hardware_report_required")
    backend = next(iter(backends))
    claimed_openwrt = (
        hardware.get("platform") == "openwrt"
        and hardware.get("device_acceptance_possible") is True
    )
    npu_present = (
        isinstance(hardware.get("metrics"), dict)
        and isinstance(hardware["metrics"].get("npu_util_percent"), dict)
        and hardware["metrics"]["npu_util_percent"].get("mean") is not None
    )
    # A claimed backend name in JSONL cannot prove HTP execution. Need an
    # independent NPU telemetry report from the same on-device session.
    can_review = claimed_openwrt and (
        backend != "qnn_htp" or npu_present
    )
    total = [x["total_ms"] for x in data]
    ttft = [x["ttft_ms"] for x in data]
    rss = [x["rss_peak_bytes"] for x in data]
    token_s = [
        1000*x["output_tokens"] / max(1, x["total_ms"]-x["ttft_ms"])
        for x in data if x["output_tokens"] > 0
    ]
    return {
        "protocol": "on-device-inference-summary/v1",
        "model_sha256": next(iter(models)),
        "backend": backend,
        "samples": len(data),
        "total_ms_p50": percentile(total, .5),
        "total_ms_p95": percentile(total, .95),
        "ttft_ms_p50": percentile(ttft, .5),
        "ttft_ms_p95": percentile(ttft, .95),
        "rss_peak_bytes_max": max(rss),
        "decode_tokens_per_second_median": (
            round(statistics.median(token_s), 3) if token_s else None
        ),
        "eligible_for_independent_device_review": can_review,
        "acceptance_status": "REQUIRES_MANUAL_BOARD_ATTESTATION_AND_THRESHOLDS"
                             if can_review else "NOT_DEVICE_VALIDATED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read external inference JSONL + board metrics")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--hardware-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    p = args.input
    if not p.is_file() or p.stat().st_size > 10_000_000:
        parser.error("invalid inference input file")
    rows = [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    board = json.loads(args.hardware_report.read_text(encoding="utf-8"))
    result = summarize(rows, board)
    result["timing_log_sha256"] = hashlib.sha256(p.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
