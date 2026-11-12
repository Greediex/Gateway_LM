"""Honest hardware telemetry and requirement mapping acceptance contracts."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.core import ROOT, read_json
from scripts.analysis.audit_requirement_traceability import audit
from scripts.hardware.measure_gateway import capture, _npu_counter


class TraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.reg = read_json(ROOT / "data/registry_v01.json")
        self.reqs = read_json(ROOT / "data/requirements_v01.json")

    def test_270_requirements_are_not_270_executable_functions(self):
        r = audit(self.reg, self.reqs)
        self.assertEqual(r["requirement_count"], len(self.reqs["requirements"]))
        self.assertEqual(r["registered_function_count"], len(self.reg["functions"]))
        self.assertEqual(r["declared_skill_count"], len(self.reg["skills"]))
        self.assertEqual(
            r["mapped_requirement_count"] + r["unmapped_requirement_count"],
            r["requirement_count"]
        )
        self.assertEqual(r["firmware_verified_requirement_count"], 0)
        self.assertGreater(r["unmapped_requirement_count"], 0)
        self.assertGreater(r["skill_gap"], 0)

    def test_invalid_requirement_reference_and_duplicate_requirement_are_rejected(self):
        d = copy.deepcopy(self.reg)
        d["functions"][0]["requirement_refs"] = ["NON_EXISTENT_F999"]
        with self.assertRaisesRegex(ValueError, "unknown_requirement"):
            audit(d, self.reqs)
        d = copy.deepcopy(self.reqs)
        d["requirements"].append(copy.deepcopy(d["requirements"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_requirement"):
            audit(self.reg, d)

    def test_probed_only_counts_as_hardware_coverage_not_replay(self):
        d = copy.deepcopy(self.reg)
        fid = next(f for f in d["functions"] if f.get("requirement_refs"))
        fid["status"] = "PROBED_OK"
        result = audit(d, self.reqs)
        self.assertGreater(result["firmware_verified_requirement_count"], 0)
        self.assertEqual(result["coverage_firmware"],
                         round(result["firmware_verified_requirement_count"] / 270, 6))


class HardwareCaptureTests(unittest.TestCase):
    def test_host_capture_never_claims_gateway_acceptance(self):
        ticks = iter([(100, 20), (200, 30), (300, 40)])
        with patch("scripts.hardware.measure_gateway._cpu_ticks",
                   side_effect=lambda: next(ticks)), patch(
            "scripts.hardware.measure_gateway._meminfo",
            return_value={"MemTotal": 1024, "MemAvailable": 300}
        ), patch("scripts.hardware.measure_gateway._rss_bytes",
                 return_value=None), patch(
            "scripts.hardware.measure_gateway.Path.exists", return_value=False
        ), patch(
            "scripts.hardware.measure_gateway.Path.is_file", return_value=False
        ):
            result = capture(samples=2, interval=0, sleep=lambda _: None, clock=lambda: 123)
        self.assertEqual(result["platform"], "generic_linux_host")
        self.assertEqual(result["verdict"], "NOT_HARDWARE_ACCEPTANCE")
        self.assertFalse(result["device_acceptance_possible"])
        self.assertIsNone(result["metrics"]["npu_util_percent"]["mean"])
        self.assertEqual(result["metrics"]["cpu_percent"]["mean"], 90)
        self.assertEqual(result["metrics"]["available_ram_bytes"]["peak"], 300)

    def test_no_fake_npu_counter(self):
        self.assertIsNone(_npu_counter(None))
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "npu"
            p.write_text("99", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "existing_sysfs_file"):
                _npu_counter(p)

    def test_invalid_hardware_sample_config_is_rejected(self):
        with self.assertRaises(ValueError):
            capture(samples=1)
        with self.assertRaises(ValueError):
            capture(samples=2, interval=-1)


if __name__ == "__main__":
    unittest.main()
