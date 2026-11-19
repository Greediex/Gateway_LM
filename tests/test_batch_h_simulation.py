"""COV-H direct READ simulations for router system health."""

import tests.batch_sim_support as support

SIM = support.ROOT / "data/skill_expansion_v1/simulation_h_v1"
DIAG = support.ROOT / "config/skill_launcher/replay_h.diagnostics.json"
SKILLS = ("H02", "H03", "H04", "H05", "H06", "H07", "H08")

BOUNDARIES = [
    ("H02", {"running_services": 1, "failed_services": 0}, "HEALTHY"),
    ("H02", {"running_services": 0, "failed_services": 0}, "UNKNOWN"),
    ("H02", {"running_services": 0, "failed_services": 1}, "FAULT"),
    ("H02", {"running_services": -1, "failed_services": 1}, "UNKNOWN"),
    ("H02", {"running_services": 1, "failed_services": -1}, "UNKNOWN"),
    ("H03", {"used_pct": 0.0, "wear_pct": 0.0}, "HEALTHY"),
    ("H03", {"used_pct": 89.9, "wear_pct": 79.9}, "HEALTHY"),
    ("H03", {"used_pct": 90.0, "wear_pct": 79.9}, "FAULT"),
    ("H03", {"used_pct": 89.9, "wear_pct": 80.0}, "FAULT"),
    ("H03", {"used_pct": 100.0, "wear_pct": 100.0}, "FAULT"),
    ("H03", {"used_pct": 100.1, "wear_pct": 80.0}, "UNKNOWN"),
    ("H03", {"used_pct": 90.0, "wear_pct": 100.1}, "UNKNOWN"),
    ("H03", {"used_pct": -0.1, "wear_pct": 80.0}, "UNKNOWN"),
    ("H03", {"used_pct": 90.0, "wear_pct": -0.1}, "UNKNOWN"),
    ("H04", {"error_count": 0, "warning_count": 0}, "HEALTHY"),
    ("H04", {"error_count": 0, "warning_count": 1}, "UNKNOWN"),
    ("H04", {"error_count": 1, "warning_count": 0}, "FAULT"),
    ("H04", {"error_count": -1, "warning_count": 0}, "UNKNOWN"),
    ("H04", {"error_count": 1, "warning_count": -1}, "UNKNOWN"),
    ("H05", {"celsius": -0.1}, "UNKNOWN"),
    ("H05", {"celsius": 0.0}, "HEALTHY"),
    ("H05", {"celsius": 84.9}, "HEALTHY"),
    ("H05", {"celsius": 85.0}, "FAULT"),
    ("H05", {"celsius": 125.0}, "FAULT"),
    ("H05", {"celsius": 125.1}, "UNKNOWN"),
    ("H06", {"driver_errors": -1}, "UNKNOWN"),
    ("H06", {"driver_errors": 0}, "HEALTHY"),
    ("H06", {"driver_errors": 1}, "FAULT"),
    ("H07", {"boot_count": 0, "crash_count": 0}, "UNKNOWN"),
    ("H07", {"boot_count": 0, "crash_count": 1}, "UNKNOWN"),
    ("H07", {"boot_count": 1, "crash_count": 0}, "HEALTHY"),
    ("H07", {"boot_count": 1, "crash_count": 1}, "FAULT"),
    ("H07", {"boot_count": 2, "crash_count": 0}, "UNKNOWN"),
    ("H07", {"boot_count": -1, "crash_count": 1}, "UNKNOWN"),
    ("H07", {"boot_count": 1, "crash_count": -1}, "UNKNOWN"),
    ("H08", {"version": "demo-synthetic", "free_storage_mb": -0.1}, "UNKNOWN"),
    ("H08", {"version": "demo-synthetic", "free_storage_mb": 0.0}, "FAULT"),
    ("H08", {"version": "demo-synthetic", "free_storage_mb": 63.9}, "FAULT"),
    ("H08", {"version": "demo-synthetic", "free_storage_mb": 64.0}, "HEALTHY"),
]

BAD = [
    ("H02", {"running_services": True, "failed_services": 0}),
    ("H03", {"used_pct": "89.9", "wear_pct": 0.0}),
    ("H04", {"error_count": 0, "warning_count": 1.5}),
    ("H05", {"celsius": None}),
    ("H06", {"driver_errors": [0]}),
    ("H07", {"boot_count": 1, "crash_count": "0"}),
    ("H08", {"version": 1, "free_storage_mb": 64.0}),
    ("H08", {"version": "demo-synthetic", "free_storage_mb": False}),
]


class BatchHTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD
