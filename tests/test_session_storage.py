"""Trusted local READ durability: integrity, binding, freshness, global limits."""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from gateway_pilot.application.session_storage import SessionStorage
from gateway_pilot.core import PlanError
from tests.catalog import test_runtime_v02 as fixture_module


class SessionStorageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.RuntimeV02Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage = SessionStorage(Path(self.tmp.name) / "private", clock=lambda: self.fixture.time)
        self.request, self.goals = "READ session evidence", ("client.ipv4",)
        self.session = self.fixture.runtime.open_session(max_calls=3, max_plans=3)
        self.storage.bind(self.session, "operator-session")

    def save(self):
        self.session.execute(self.goals, request="secret user prompt")
        return self.storage.checkpoint(self.session, self.request, self.goals)

    def resume(self, **changes):
        description = self.storage.describe("operator-session")
        session = self.fixture.make_runtime().open_session(case_id=description["case_id"], **changes)
        self.storage.bind(session, "operator-session")
        return session

    def test_generated_key_and_private_files_no_raw_prompts(self):
        self.assertEqual(self.save(), 2)
        self.assertEqual(os.stat(self.storage.directory).st_mode & 0o777, 0o700)
        for path in self.storage.directory.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn(b"secret user prompt", path.read_bytes())
        other = SessionStorage(self.storage.directory)
        self.assertEqual(other.secret, self.storage.secret)
        self.assertEqual(len(other.history()), 1)
        self.assertNotIn("192.0.2.10", json.dumps(other.history()))

    def test_cross_process_style_resume_preserves_facts_counts_limits_and_deadline(self):
        self.save()
        self.fixture.time += 5
        session = self.resume()
        self.assertEqual(self.storage.restore(session, "operator-session", self.request, self.goals), 2)
        self.assertEqual(session.runner.calls, 2)
        self.assertEqual(session.runner.max_calls, 3)
        self.assertEqual(session._prior_plans, 1)
        self.assertEqual(session.expires_at, self.session.expires_at)
        self.assertEqual(session.runner.started, self.session.runner.started)
        self.assertEqual(session.runner.spent, self.session.runner.spent)
        self.assertGreaterEqual(session.state.fact("client.ipv4")["age_s"], 5)
        session.execute(self.goals)
        self.assertEqual(self.fixture.backend.calls, 2)
        session.execute(self.goals)
        with self.assertRaisesRegex(PlanError, "session_plan_budget"):
            session.execute(self.goals)

    def test_restore_fails_on_checkpoint_behind_durable_journal(self):
        self.save()
        self.session.execute(("wifi.station",))
        with self.assertRaisesRegex(PlanError, "storage_checkpoint_journal_count_mismatch"):
            self.storage.restore(self.session, "operator-session", self.request, self.goals)
        self.assertEqual(self.session.runner.calls, 3)
        self.assertTrue(self.session.closed)

    def test_per_execute_journal_scopes_do_not_conflict(self):
        self.session.execute(self.goals, request="first private query")
        self.session.execute(("wifi.station",), request="second private query")
        journals = list(self.storage.directory.glob("*.journal.json"))
        self.assertEqual(len(journals), 2)
        for path in journals:
            content = path.read_text()
            self.assertNotIn("private query", content)
            self.assertEqual(json.loads(content)["entries"][0]["event"]["reason"], "read_step_terminal")

    def test_tamper_fails_closed_without_admitting_facts(self):
        self.save()
        session = self.resume()
        path = next(self.storage.directory.glob("*.checkpoint.json"))
        envelope = json.loads(path.read_text())
        envelope["body"]["budget"]["calls"] = 0
        path.write_text(json.dumps(envelope))
        with self.assertRaisesRegex(PlanError, "storage_signature_invalid"):
            self.storage.restore(session, "operator-session", self.request, self.goals)
        self.assertTrue(session.closed)
        self.assertEqual(session.state.evidence, [])

    def test_expired_session_and_wrong_context_fail_closed(self):
        self.save()
        session = self.resume()
        session.state.case_id = "foreign-case"
        with self.assertRaisesRegex(PlanError, "storage_context_mismatch"):
            self.storage.restore(session, "operator-session", self.request, self.goals)
        self.assertTrue(session.closed)
        self.fixture.time += 301
        session = self.resume()
        with self.assertRaisesRegex(PlanError, "storage_session_expired"):
            self.storage.restore(session, "operator-session", self.request, self.goals)
        self.assertTrue(session.closed)

    def test_wrong_operator_handle_request_goals_and_stricter_budget_fail(self):
        self.save()
        for request, goals, sid, options in (
            (self.request, self.goals, "other", {}),
            ("other", self.goals, "operator-session", {}),
            (self.request, ("wifi.station",), "operator-session", {}),
            (self.request, self.goals, "operator-session", {"max_calls": 1}),
        ):
            session = self.resume(**options)
            with self.assertRaises(PlanError):
                self.storage.restore(session, sid, request, goals)
            self.assertTrue(session.closed)
            self.assertEqual(session.state.evidence, [])

    def test_explicit_close_revokes_restore_and_keeps_summary(self):
        self.save()
        self.storage.close("operator-session")
        self.assertTrue(self.session.closed)
        with self.assertRaisesRegex(PlanError, "storage_session_closed"):
            self.storage.describe("operator-session")
        self.assertEqual(self.storage.history()[0]["status"], "CLOSED")

    def test_stale_facts_are_not_rejuvenated_by_resume(self):
        self.save()
        self.fixture.time += 31
        session = self.resume()
        self.assertEqual(self.storage.restore(session, "operator-session", self.request, self.goals), 0)
        self.assertIsNone(session.state.fact("client.ipv4"))
        self.assertEqual(session.runner.calls, 2)

    def test_journal_tamper_or_deletion_rejects_restore(self):
        for delete in (False, True):
            with self.subTest(delete=delete):
                if not delete:
                    self.save()
                path = next(self.storage.directory.glob("*.journal.json"))
                original = path.read_bytes()
                if delete:
                    path.unlink()
                else:
                    body = json.loads(original)
                    body["entries"][0]["event"]["reason"] = "forged"
                    path.write_text(json.dumps(body))
                session = self.resume()
                with self.assertRaises(PlanError):
                    self.storage.restore(session, "operator-session", self.request, self.goals)
                self.assertTrue(session.closed)
                path.write_bytes(original)

    def test_signed_malformed_budget_and_other_os_boot_are_rejected(self):
        self.save()
        path = next(self.storage.directory.glob("*.checkpoint.json"))
        original = self.storage._read(path)
        for change in (lambda body: body["budget"].update(calls=-1),
                       lambda body: body.update(host_boot_id="other-os-boot")):
            body = json.loads(json.dumps(original))
            change(body)
            self.storage._write(path, body)
            session = self.resume()
            with self.assertRaises(PlanError):
                self.storage.restore(session, "operator-session", self.request, self.goals)
            self.assertTrue(session.closed)
            self.assertEqual(session.state.evidence, [])

    def test_repairs_global_replans_exclusions_and_attempts_survive_resume(self):
        self.save()
        runner = self.session.runner
        runner.max_repairs, runner.repairs, runner.global_replans = 2, 2, 1
        runner.excluded.add("wifi.station")
        runner.incomplete = True
        self.session.state.attempts["client.ipv4"] = 2
        runner.target_attempts["synthetic-client"] = {"wifi.station": 1}
        self.storage.checkpoint(self.session, self.request, self.goals)
        session = self.resume(max_repairs=2)
        self.storage.restore(session, "operator-session", self.request, self.goals)
        self.assertEqual((session.runner.repairs, session.runner.max_repairs,
                          session.runner.global_replans), (2, 2, 1))
        self.assertIn("wifi.station", session.runner.excluded)
        self.assertTrue(session.runner.incomplete)
        self.assertEqual(session.state.attempts["client.ipv4"], 2)
        self.assertEqual(session.runner.target_attempts["synthetic-client"]["wifi.station"], 1)
        with self.assertRaisesRegex(PlanError, "repair_incomplete"):
            session.runner.global_replan(SimpleNamespace(audit=[], revision=1),
                                         SimpleNamespace(id="node"), "test-exhaustion")

    def test_signed_foreign_exclusion_or_repair_counter_rejected(self):
        self.save()
        path = next(self.storage.directory.glob("*.checkpoint.json"))
        original = self.storage._read(path)
        for mutate in (lambda body: body["execution"].update(excluded=["foreign.function"]),
                       lambda body: body["budget"].update(global_replans=2),
                       lambda body: body["execution"].update(attempts={"client.ipv4": -1})):
            body = json.loads(json.dumps(original))
            mutate(body)
            self.storage._write(path, body)
            session = self.resume()
            with self.assertRaises(PlanError):
                self.storage.restore(session, "operator-session", self.request, self.goals)
            self.assertTrue(session.closed)
            self.assertEqual(session.state.evidence, [])

    def test_invalid_local_paths_ids_history_limit_and_symlink_key(self):
        for sid in ("../outside", "", None, "a" * 65):
            with self.assertRaises(PlanError):
                self.storage.bind(self.fixture.runtime.open_session(), sid)
        for limit in (0, 101, True):
            with self.assertRaises(ValueError):
                self.storage.history(limit=limit)
        alias = Path(self.tmp.name) / "alias"
        alias.symlink_to(self.storage.directory, target_is_directory=True)
        with self.assertRaises(PlanError):
            SessionStorage(alias)


if __name__ == "__main__":
    unittest.main()
