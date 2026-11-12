"""Local model, calibration and Ubus CLI transport safety tests."""
from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
from gateway_pilot.graph_v3.state import CaseState
from scripts.analysis.evaluate_goal_proposals import (
    assess, calibrate, evaluate_suite, read_suite,
)
from gateway_pilot.adapters.ubus_cli import UbusCliReadTransport


class LocalModelCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry.from_v01()
        self.fixtures = {x["id"]: x for x in read_json(ROOT / "data/cases.json")}
        self.case = "GLM-04-0"

    def rows(self):
        base = dict(case_id=self.case, group="wan", expected_goals=["wan.status"], kind="READ")
        return [
            dict(base, id="d-good", split="dev", request="wan status please"),
            dict(base, id="d-bad", split="dev", request="system resources please",
                 expected_goals=["system.resources"]),
            dict(base, id="t-good", split="test", request="router wan link"),
            dict(base, id="t-bad", split="test", request="change wifi password",
                 kind="WRITE", expected_goals=[]),
        ]

    @staticmethod
    def proposal(confidence, span):
        return {
            "goals": ["wan.status"], "confidence": confidence,
            "spans": {"wan.status": span}, "needs_clarification": False,
        }

    def test_calibration_selects_dev_threshold_without_test_leakage(self):
        rows = self.rows()
        outputs = {
            "d-good": self.proposal(.98, "wan status"),
            "d-bad": self.proposal(.78, "system resources"),
            "t-good": self.proposal(.91, "wan link"),
            "t-bad": self.proposal(.99, "wifi password"),
        }
        result = evaluate_suite(rows, outputs, self.registry, self.fixtures)
        self.assertGreaterEqual(result["threshold"], .8)
        self.assertEqual(result["dev"]["wrong"], 0)
        self.assertEqual(result["test"]["unsafe_acceptances"], 0)
        self.assertEqual(result["test"]["correct"], 1)
        self.assertEqual(result["threshold_selected_from"], "dev_only")

    def test_calibration_abstains_when_no_safe_threshold(self):
        rows = self.rows()[:2]
        outputs = {
            "d-good": self.proposal(.5, "wan status"),
            "d-bad": self.proposal(.99, "system resources"),
        }
        with self.assertRaisesRegex(ValueError, "no_safe_goal_threshold"):
            calibrate(rows, outputs, self.registry, self.fixtures)

    def test_read_suite_checks_split_schema_and_invalid_labels(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "suite.jsonl"
            rows = self.rows()
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            self.assertEqual(len(read_suite(path, self.registry, self.fixtures)), 4)
            rows[1]["id"] = rows[0]["id"]
            path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_goal_suite_row"):
                read_suite(path, self.registry, self.fixtures)

    def test_real_ollama_adapter_requires_loopback_and_verified_model(self):
        with patch("gateway_pilot.graph_v3.ollama_goal_model.http_json",
                   return_value={"model_info": {"general.parameter_count": 600_000_000}}) as call:
            model = OllamaGoalModel("qwen3:0.6b")
            self.assertEqual(model.parameter_count, 600_000_000)
            self.assertTrue(model.local_only)
            self.assertEqual(call.call_args.args[1], "show")
        for endpoint in ("https://api.example.com", "http://8.8.8.8:11434",
                         "http://alice:pass@localhost:11434",
                         "http://localhost:11434/path"):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                OllamaGoalModel("qwen3:0.6b", endpoint=endpoint)

    def test_ollama_return_is_proposal_not_tool_execution(self):
        with patch("gateway_pilot.graph_v3.ollama_goal_model.http_json",
                   side_effect=[
                       {"model_info": {"general.parameter_count": 600_000_000}},
                       {"message": {"content": json.dumps(self.proposal(.91, "wan status"))}},
                   ]) as call:
            model = OllamaGoalModel("qwen3:0.6b")
            proposal = model.propose_goals(
                "wan status", ({"port": "wan.status", "description": "Link telemetry"},)
            )
            self.assertEqual(proposal["goals"], ["wan.status"])
            req = call.call_args.args[2]
            self.assertEqual(req["messages"][0]["role"], "system")
            self.assertNotIn("tools", req)
            self.assertFalse(req["stream"])
            self.assertEqual(req["format"]["properties"]["goals"]["items"]["enum"],
                             ["wan.status"])


class UbusCliIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.patch = patch("gateway_pilot.adapters.ubus_cli.shutil.which",
                           return_value="/sbin/ubus")
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.transport = UbusCliReadTransport(timeout_s=1)

    @staticmethod
    def result(stdout, returncode=0):
        return subprocess.CompletedProcess(["/sbin/ubus"], returncode, stdout, "")

    def test_exact_ubus_object_and_method_and_json_read(self):
        with patch("gateway_pilot.adapters.ubus_cli.subprocess.run", side_effect=[
            self.result("'status': {\n  'verbose': false\n}\n"),
            self.result('{"up":true,"uptime":24}\n')
        ]) as call:
            self.assertTrue(self.transport.probe("network.interface.wan", "status"))
            result = self.transport.read("network.interface.wan", "status", {})
            self.assertEqual(result["up"], True)
            self.assertEqual(call.call_count, 2)
            self.assertEqual(call.call_args.kwargs["shell"], False)
            self.assertEqual(call.call_args.args[0],
                             ["/sbin/ubus", "-S", "call", "network.interface.wan",
                              "status", "{}"])

    def test_absent_method_does_not_pass_probe(self):
        with patch("gateway_pilot.adapters.ubus_cli.subprocess.run",
                   return_value=self.result("'down': {}\n")):
            self.assertFalse(self.transport.probe("network.interface.wan", "status"))

    def test_shell_injection_and_arbitrary_binary_are_rejected(self):
        with self.assertRaises(ValueError):
            UbusCliReadTransport(executable="/bin/sh")
        with self.assertRaises(ValueError):
            self.transport.probe("network.interface.wan; reboot", "status")
        with self.assertRaises(ValueError):
            self.transport.read("network.interface.wan", "status;reboot", {})

    def test_timeout_nonzero_malformed_or_oversized_output_fails_closed(self):
        with patch("gateway_pilot.adapters.ubus_cli.subprocess.run",
                   side_effect=subprocess.TimeoutExpired(["ubus"], 1)):
            self.assertFalse(self.transport.probe("network.interface.wan", "status"))
            with self.assertRaises(PlanError):
                self.transport.read("network.interface.wan", "status", {})
        with patch("gateway_pilot.adapters.ubus_cli.subprocess.run",
                   return_value=self.result("", 1)):
            self.assertFalse(self.transport.probe("network.interface.wan", "status"))
        for result in ("not json", "[]"):
            with self.subTest(result=result):
                with patch("gateway_pilot.adapters.ubus_cli.subprocess.run",
                           return_value=self.result(result)):
                    with self.assertRaises(PlanError):
                        self.transport.read("network.interface.wan", "status", {})


if __name__ == "__main__":
    unittest.main()
