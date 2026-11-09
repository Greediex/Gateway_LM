"""Deterministic WF-054 replay baseline for sustained resource pressure."""


THRESHOLDS = {
    "cpu_pct": (90, "high"),
    "available_ram_pct": (10, "low"),
    "storage_used_pct": (90, "high"),
    "dhcp_success_pct": (90, "low"),
    "radio_busy_pct": (85, "high"),
    "dhcp_pool_free_pct": (10, "low"),
    "conntrack_used_pct": (90, "high"),
}


def monitor_window(samples, now):
    """Assess three chronological observations of one target, boot and config."""
    result = {"workflow_id": "WF-054", "method": "sustained_threshold", "alerts": [],
              "case_status": "INCONCLUSIVE", "reason": None, "missing_metrics": list(THRESHOLDS)}
    window = samples[-3:]
    if len(window) != 3:
        return {**result, "reason": "missing_window_samples"}
    if any(not isinstance(row, dict) for row in window):
        return {**result, "reason": "invalid_window_samples"}
    required = ("id", "target", "source", "boot_id", "config_version")
    if any(not isinstance(row.get(key), str) or not row[key] for row in window for key in required):
        return {**result, "reason": "missing_provenance"}
    if (len({row["id"] for row in window}) != len(window)
            or any(len({row[key] for row in window}) != 1 for key in required[1:])):
        return {**result, "reason": "inconsistent_window_provenance"}
    times = [row.get("observed_at") for row in window]
    if (any(type(t) is not int for t in times) or not 0 <= now - times[-1] <= 120
            or any(not 0 < end - start <= 120 for start, end in zip(times, times[1:]))):
        return {**result, "reason": "stale_or_unordered_window"}
    metrics = [row.get("metrics") for row in window]
    if any(not isinstance(values, dict) for values in metrics):
        return {**result, "reason": "missing_measurements"}
    missing = []
    for name, (threshold, direction) in THRESHOLDS.items():
        values = [sample.get(name) for sample in metrics]
        if any(type(value) not in (int, float) or not 0 <= value <= 100 for value in values):
            missing.append(name)
            continue
        breached = all(value >= threshold if direction == "high" else value <= threshold for value in values)
        if breached:
            result["alerts"].append({"metric": name, "values": values, "threshold": threshold,
                                     "direction": direction, "target": window[-1]["target"],
                                     "source": window[-1]["source"],
                                     "evidence_ids": [row["id"] for row in window]})
    result["missing_metrics"] = missing
    if len(missing) == len(THRESHOLDS):
        result["reason"] = "missing_measurements"
    else:
        result["case_status"] = "PARTIAL" if missing else "RESOLVED"
    return result
