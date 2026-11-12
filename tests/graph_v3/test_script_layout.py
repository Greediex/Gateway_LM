"""Regression: root is small without breaking imports or frozen metadata."""
from __future__ import annotations

import importlib
import subprocess
import sys
import unittest

from gateway_pilot.core import ROOT

ANALYSIS = (
    "analyze_catalog", "audit_html", "compare_interfaces",
    "inspect_case", "verify_run", "write_analysis",
)
BENCHMARKS = (
    "run_conversation_benchmark", "run_dynamic_benchmark",
    "run_function_selection", "run_html_benchmark",
    "run_operations_replay", "run_rag_benchmark",
)
ROOT_ENTRYPOINTS = {"setup_upstream.py", "prepare_data.py"}


class ScriptLayoutTests(unittest.TestCase):
    def test_root_only_contains_stable_bootstrap_and_data_generator(self):
        self.assertEqual({path.name for path in ROOT.glob("*.py")}, ROOT_ENTRYPOINTS)

    def test_all_moved_modules_import_without_execution(self):
        for group, names in (("analysis", ANALYSIS), ("benchmarks", BENCHMARKS)):
            for name in names:
                with self.subTest(module=name):
                    module = importlib.import_module(f"scripts.{group}.{name}")
                    self.assertTrue(module.__file__)

    def test_benchmark_data_root_remains_repository_root(self):
        for name in ("run_conversation_benchmark", "run_function_selection"):
            module = importlib.import_module(f"scripts.benchmarks.{name}")
            self.assertEqual(module.ROOT, ROOT)
        self.assertTrue((ROOT / "prepare_data.py").is_file())

    def test_cli_module_entrypoints_offer_help(self):
        examples = (
            "scripts.benchmarks.run_function_selection",
            "scripts.benchmarks.run_dynamic_benchmark",
            "scripts.analysis.audit_html",
            "scripts.analysis.verify_run",
        )
        for name in examples:
            with self.subTest(module=name):
                cmd = subprocess.run(
                    [sys.executable, "-m", name, "--help"],
                    cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=20,
                )
                self.assertEqual(cmd.returncode, 0, cmd.stderr)
                self.assertIn("usage:", cmd.stdout.lower())


if __name__ == "__main__":
    unittest.main()
