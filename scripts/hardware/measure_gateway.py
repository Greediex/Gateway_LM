"""On-device Linux/OpenWrt CPU, RAM, process RSS and optional NPU benchmark.

No device data is ever invented. On a GitHub Ubuntu runner this measures
the RUNNER, not the target Wi-Fi gateway, and acceptance stays false.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import statistics
import time
from pathlib import Path


def _read(path):
    return Path(path).read_text(encoding="utf-8", errors="replace")


def _cpu_ticks():
    line = next((s for s in _read("/proc/stat").splitlines() if s.startswith("cpu ")), None)
    if not line:
        raise ValueError("cpu_ticks_missing")
    ticks = [int(v) for v in line.split()[1:]]
    if len(ticks) < 5:
        raise ValueError("cpu_ticks_invalid")
    return sum(ticks), ticks[3] + ticks[4]


def _meminfo():
    result = {}
    for line in _read("/proc/meminfo").splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        try:
            result[key] = int(value.strip().split()[0]) * 1024
        except (IndexError, ValueError):
            continue
    if "MemTotal" not in result or "MemAvailable" not in result:
        raise ValueError("meminfo_missing")
    return result


def _rss_bytes(pid):
    if pid is None:
        return None
    if type(pid) is not int or pid <= 0:
        raise ValueError("invalid_monitor_pid")
    for line in _read(f"/proc/{pid}/status").splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    raise ValueError("process_rss_unavailable")


def _npu_counter(path):
    if path is None:
        return None
    path = Path(path).resolve()
    # Operator may select a documented NPU sysfs counter only.
    if not path.is_relative_to(Path("/sys")) or not path.is_file():
        raise ValueError("npu_counter_must_be_existing_sysfs_file")
    value = float(_read(path).strip())
    if not (0 <= value <= 100):
        raise ValueError("npu_counter_requires_percent_0_to_100")
    return value


def capture(*, samples=5, interval=0.2, pid=None, npu_counter=None,
            sleep=time.sleep, clock=time.time):
    if (type(samples) is not int or not 2 <= samples <= 200
            or type(interval) not in (float, int) or not 0 <= interval <= 60):
        raise ValueError("invalid_hardware_sample_budget")
    openwrt = Path("/etc/openwrt_release")
    firmware_text = _read(openwrt) if openwrt.exists() else None
    profile = {
        "platform": "openwrt" if firmware_text else "generic_linux_host",
        "firmware_release_sha256": (
            hashlib.sha256(firmware_text.encode("utf-8")).hexdigest()
            if firmware_text else None
        ),
        "device_model": (
            _read("/proc/device-tree/model").strip("\x00\n")
            if Path("/proc/device-tree/model").is_file() else None
        ),
        "timestamp_unix": clock(), "samples": samples, "interval_s": interval,
        "pid": pid, "cpu_percent": [], "used_ram_bytes": [],
        "available_ram_bytes": [], "process_rss_bytes": [],
        "npu_util_percent": [], "missing_npu_counter": npu_counter is None,
    }
    ticks = _cpu_ticks()
    for i in range(samples):
        sleep(interval)
        next_ticks = _cpu_ticks()
        elapsed = next_ticks[0] - ticks[0]
        idle = next_ticks[1] - ticks[1]
        if elapsed <= 0 or not 0 <= idle <= elapsed:
            raise ValueError("cpu_ticks_nonmonotonic")
        profile["cpu_percent"].append(round(100*(elapsed-idle)/elapsed, 3))
        mem = _meminfo()
        profile["used_ram_bytes"].append(mem["MemTotal"]-mem["MemAvailable"])
        profile["available_ram_bytes"].append(mem["MemAvailable"])
        profile["process_rss_bytes"].append(_rss_bytes(pid))
        profile["npu_util_percent"].append(_npu_counter(npu_counter))
        ticks = next_ticks
    def stats(values):
        data = [v for v in values if v is not None]
        return {
            "mean": round(statistics.mean(data), 3) if data else None,
            "peak": max(data) if data else None,
        }
    profile["metrics"] = {
        key: stats(profile[key])
        for key in ("cpu_percent", "used_ram_bytes", "available_ram_bytes",
                    "process_rss_bytes", "npu_util_percent")
    }
    profile["device_acceptance_possible"] = (
        profile["platform"] == "openwrt"
        and pid is not None
        and npu_counter is not None
        and all(v is not None for v in profile["npu_util_percent"])
    )
    profile["verdict"] = (
        "MEASURED_ONLY_NEEDS_FUNCTIONAL_AND_PERFORMANCE_THRESHOLDS"
        if profile["device_acceptance_possible"] else
        "NOT_HARDWARE_ACCEPTANCE"
    )
    return profile


def main(argv=None):
    parser = argparse.ArgumentParser(description="Collect authentic OpenWrt host/device metrics")
    parser.add_argument("--output", type=Path, default=Path("runs/hardware_metrics.json"))
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--interval", type=float, default=0.2)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--npu-counter", type=Path,
                        help="Firmware-specific existing /sys/... percentage counter")
    parser.add_argument("--require-device", action="store_true",
                        help="Return nonzero unless OpenWrt, monitored PID and NPU are present")
    args = parser.parse_args(argv)
    result = capture(samples=args.samples, interval=args.interval,
                     pid=args.pid, npu_counter=args.npu_counter)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False)+"\n",
                           encoding="utf-8")
    print(json.dumps({"platform": result["platform"], "verdict": result["verdict"],
                      "metrics": result["metrics"]}, indent=2))
    return 2 if args.require_device and not result["device_acceptance_possible"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
