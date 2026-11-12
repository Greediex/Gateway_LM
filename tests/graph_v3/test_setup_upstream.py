"""Safety tests for idempotent, pinned upstream checkout management."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import setup_upstream


PIN = "a" * 40


class SetupUpstreamTests(unittest.TestCase):
    def test_existing_pinned_checkout_is_verified_without_git_mutation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "third_party" / "GoS" / ".git").mkdir(parents=True)
            with patch.object(setup_upstream, "_head", return_value=PIN) as head:
                with patch.object(setup_upstream.subprocess, "run") as run:
                    path = setup_upstream.ensure_checkout(root, "GoS", "https://example.invalid/gos", PIN)
            self.assertEqual(path, root / "third_party" / "GoS")
            head.assert_called_once_with(path)
            run.assert_not_called()

    def test_wrong_commit_is_rejected_without_automatic_reset(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "third_party" / "GoS" / ".git").mkdir(parents=True)
            with patch.object(setup_upstream, "_head", return_value="b" * 40):
                with patch.object(setup_upstream.subprocess, "run") as run:
                    with self.assertRaisesRegex(RuntimeError, "checkout mismatch"):
                        setup_upstream.ensure_checkout(root, "GoS", "https://example.invalid/gos", PIN)
            run.assert_not_called()

    def test_partial_checkout_is_not_deleted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            checkout = root / "third_party" / "GoS"
            checkout.mkdir(parents=True)
            (checkout / "my-work.txt").write_text("preserve", encoding="utf-8")
            with patch.object(setup_upstream.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "not a Git checkout"):
                    setup_upstream.ensure_checkout(root, "GoS", "https://example.invalid/gos", PIN)
            run.assert_not_called()
            self.assertEqual((checkout / "my-work.txt").read_text(encoding="utf-8"), "preserve")

    def test_new_checkout_clones_and_detaches_pinned_commit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            calls = []

            def fake_run(args, **kwargs):
                calls.append(args)
                if args[1] == "clone":
                    checkout = Path(args[-1])
                    (checkout / ".git").mkdir(parents=True)
                return Mock(returncode=0)

            with patch.object(setup_upstream.subprocess, "run", side_effect=fake_run):
                with patch.object(setup_upstream, "_head", return_value=PIN):
                    path = setup_upstream.ensure_checkout(root, "GoS", "https://example.invalid/gos", PIN)
            self.assertEqual(len(calls), 2)
            self.assertEqual(calls[0][:3], ["git", "clone", "--no-checkout"])
            self.assertEqual(calls[1][-2:], ["--detach", PIN])
            self.assertEqual(path, root / "third_party" / "GoS")


if __name__ == "__main__":
    unittest.main()
