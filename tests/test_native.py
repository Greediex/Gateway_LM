import json
import unittest
from argparse import Namespace
from unittest.mock import patch

from gateway_pilot.core import Registry, new_state, read_json, ROOT
from gateway_pilot.run import prompt
from gateway_pilot.native_run import extract_catalog, native_tools, native_decision


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.registry = Registry()
        self.case = next(c for c in read_json(ROOT / "data/cases.json") if c["template"] == "wan_down")
        self.messages = prompt(self.case, new_state(self.case, self.registry), self.registry, ["wan.status"], 10)
        self.args = Namespace(endpoint="http://127.0.0.1:11434", model="qwen3:1.7b", seed=42, timeout=120)

    def test_extract_only_exposed_functions_and_labels(self):
        catalog, labels = extract_catalog(self.messages)
        self.assertEqual([f["id"] for f in catalog], ["wan.status"])
        self.assertIn("wan_link_down", labels)

    def test_native_schema_empty_diagnostic_arguments(self):
        catalog, labels = extract_catalog(self.messages)
        tools, mapping = native_tools(catalog, labels)
        self.assertEqual(mapping["wan_status"], "wan.status")
        self.assertEqual(tools[0]["function"]["parameters"]["properties"], {})

    def test_native_call_translation(self):
        raw = {"message": {"tool_calls": [{"function": {"name": "wan_status", "arguments": {}}}]}}
        with patch("gateway_pilot.native_run.run.http_json", return_value=raw):
            d, meta = native_decision(self.args, self.messages)
        self.assertEqual(d, {"action": "CALL_TOOL", "function_id": "wan.status", "arguments": {}})
        self.assertEqual(len(meta["native_tool_calls"]), 1)

    def test_native_terminal_translation(self):
        raw = {"message": {"tool_calls": [{"function": {"name": "finish_case", "arguments": {
            "diagnosis": "wan_link_down", "evidence_ids": ["e1"]}}}]}}
        with patch("gateway_pilot.native_run.run.http_json", return_value=raw):
            d, _ = native_decision(self.args, self.messages)
        self.assertEqual(d["action"], "FINISH")
        self.assertEqual(d["evidence_ids"], ["e1"])

    def test_multiple_native_calls_not_silently_executed(self):
        call = {"function": {"name": "wan_status", "arguments": {}}}
        with patch("gateway_pilot.native_run.run.http_json", return_value={"message": {"tool_calls": [call, call]}}):
            d, meta = native_decision(self.args, self.messages)
        self.assertIsNone(d)
        self.assertEqual(meta["native_protocol_error"], "expected_one_tool_call")

    def test_native_does_not_fallback_to_freeform_text(self):
        with patch("gateway_pilot.native_run.run.http_json", return_value={"message": {"content": '{"action":"FINISH"}'}}):
            d, _ = native_decision(self.args, self.messages)
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
