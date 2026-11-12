"""Unit tests for non-destructive repository hygiene checks."""
import tempfile
import unittest
from pathlib import Path

from scripts.check_project import broken_links, suspicious_tracked


class ProjectHygieneTests(unittest.TestCase):
    def test_local_links_resolve_relative_to_each_document(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "docs").mkdir()
            (root / "README.md").write_text(
                "[Docs](docs/INDEX.md) [External](https://example.org/a) [Anchor](#intro)",
                encoding="utf-8",
            )
            (root / "docs" / "INDEX.md").write_text(
                "[Back](../README.md) [Anchor](#docs)", encoding="utf-8",
            )
            self.assertEqual(broken_links(root, ("README.md", "docs/INDEX.md")), [])

    def test_broken_local_link_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("[Missing](docs/NO_SUCH_DOC.md)", encoding="utf-8")
            self.assertEqual(
                broken_links(root, ("README.md",)),
                ["README.md: broken local link docs/NO_SUCH_DOC.md"],
            )

    def test_generated_artifacts_are_rejected(self):
        bad = suspicious_tracked([
            "runs/experiment.jsonl", "pkg/__pycache__/code.pyc", ".venv/lib/abc",
            "models/model.onnx", "docs/report.md", "gateway_pilot/core.py",
        ])
        self.assertEqual(bad, [
            "runs/experiment.jsonl", "pkg/__pycache__/code.pyc", ".venv/lib/abc",
            "models/model.onnx",
        ])


if __name__ == "__main__":
    unittest.main()
