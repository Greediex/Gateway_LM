"""Shared READ case reuse stays inside Core verification and global budgets."""
import unittest
from types import SimpleNamespace

from gateway_pilot.adapters.bindings import TargetContext
from gateway_pilot.command_catalog.session import ReadSession
from gateway_pilot.core import PlanError
from gateway_pilot.skill_expansion.runtime_bridge import RuntimeSkillBridge, SkillNotReady
from tests.catalog import test_runtime_v02 as fixture_module


class ReadSessionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_module.RuntimeV02Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.runtime = self.fixture.runtime

    def test_reuse_then_refresh_expired_facts_without_resetting_global_counts(self):
        session = self.runtime.open_session()
        runner, first = session.execute(["client.ipv4"])
        ids = [e["id"] for e in session.state.evidence]
        self.assertEqual((runner.calls, self.fixture.backend.calls), (2, 2))
        repeated, second = session.execute(["client.ipv4"])
        self.assertIs(runner, repeated)
        self.assertEqual(len(second.nodes), 0)
        self.assertEqual((runner.calls, self.fixture.backend.calls), (2, 2))
        self.fixture.time += 31
        _, refreshed = session.execute(["client.ipv4"])
        self.assertEqual(len(refreshed.nodes), 2)
        self.assertEqual((runner.calls, self.fixture.backend.calls), (4, 4))
        self.assertNotIn(session.state.fact("client.ipv4")["id"], ids)
        self.assertTrue(all(session.state.usable(e, self.runtime.registry.ports[e["port"]])
                            for e in session.state.evidence if not e.get("_invalidated")))

    def test_global_call_cost_and_plan_limits(self):
        session = self.runtime.open_session(max_calls=2)
        session.execute(["client.ipv4"])
        session.execute(["client.ipv4"])
        with self.assertRaisesRegex(PlanError, "runner_call_or_deadline_budget"):
            session.execute(["wifi.station"])
        self.assertEqual(self.fixture.backend.calls, 2)
        session = self.runtime.open_session(max_plans=1)
        session.execute(["client.ipv4"])
        with self.assertRaisesRegex(PlanError, "session_plan_budget"):
            session.execute(["client.ipv4"])
        session = self.runtime.open_session(cost_budget=0.01)
        with self.assertRaises(PlanError):
            session.execute(["client.ipv4"])
        self.assertEqual(session.runner.calls, 0)

    def test_bad_callback_closes_and_invalidates(self):
        valid = [True]
        session = self.runtime.open_session(context_valid=lambda: valid[0])
        session.execute(["client.ipv4"])
        valid[0] = False
        with self.assertRaisesRegex(PlanError, "session_context_invalid"):
            session.execute(["client.ipv4"])
        self.assertTrue(session.closed)
        self.assertIsNone(session.state.fact("client.ipv4"))
        self.assertEqual(self.fixture.backend.calls, 2)

    def test_callback_exception_is_fail_closed(self):
        valid = [True]
        def callback():
            if not valid[0]:
                raise RuntimeError("private context detail")
            return True
        session = self.runtime.open_session(context_valid=callback)
        session.execute(["client.ipv4"])
        valid[0] = False
        with self.assertRaisesRegex(PlanError, "session_context_check_failed"):
            session.execute(["client.ipv4"])
        self.assertTrue(session.closed)
        self.assertIsNone(session.state.fact("client.ipv4"))

    def test_expiry_clock_rollback_and_close(self):
        for change in (lambda: setattr(self.fixture, "time", self.fixture.time + 300),
                       lambda: setattr(self.fixture, "time", self.fixture.time - 1)):
            session = self.runtime.open_session()
            session.execute(["client.ipv4"])
            change()
            with self.assertRaisesRegex(PlanError, "session_expired_or_clock"):
                session.execute(["client.ipv4"])
            self.assertTrue(session.closed)
            self.assertIsNone(session.state.fact("client.ipv4"))
        session.close()
        with self.assertRaisesRegex(PlanError, "session_closed"):
            session.execute(["client.ipv4"])

    def test_acl_function_binding_backend_or_target_drift_invalidates_everything(self):
        for mutation in (
            lambda rt: setattr(rt, "permissions", frozenset()),
            lambda rt: setattr(rt, "policy_context_id", "f" * 64),
            lambda rt: setattr(rt.registry.functions["clients.resolve"], "version", "99.0.0"),
            lambda rt: setattr(rt, "_binding_pins", {}),
            lambda rt: setattr(self.fixture.backend, "revision", "99.0.0"),
            lambda rt: setattr(rt, "context", TargetContext("client", "other", rt.context.environment_id)),
        ):
            self.fixture.backend.revision = "1.0.0"
            rt = self.fixture.make_runtime()
            session = rt.open_session()
            session.execute(["client.ipv4"])
            before = self.fixture.backend.calls
            mutation(rt)
            with self.assertRaises(PlanError):
                session.execute(["client.ipv4"])
            self.assertTrue(session.closed)
            self.assertEqual(self.fixture.backend.calls, before)
            self.assertIsNone(session.state.fact("client.ipv4"))

    def test_capability_loss_cannot_reuse_cached_success(self):
        session = self.runtime.open_session()
        session.execute(["client.ipv4"])
        self.fixture.backend.supported = False
        with self.assertRaises(PlanError):
            session.execute(["client.ipv4"])
        self.assertIsNone(session.state.fact("client.ipv4"))
        self.assertEqual(self.fixture.backend.calls, 2)
        self.fixture.backend.supported = True
        session.execute(["client.ipv4"])
        self.assertEqual(self.fixture.backend.calls, 4)

    def test_state_cannot_be_retargeted(self):
        session = self.runtime.open_session()
        session.execute(["client.ipv4"])
        session.state.target["client_id"] = "other"
        with self.assertRaisesRegex(PlanError, "session_state_changed"):
            session.execute(["client.ipv4"])
        self.assertTrue(session.closed)

    def test_bridge_accepts_only_same_runtime_genuine_session(self):
        sid = next(iter(self.runtime.registry.skills))
        bridge = RuntimeSkillBridge(self.runtime, SimpleNamespace(skills={sid: object()}))
        snapshot = self.runtime.probe()
        for invalid in (object(), self.fixture.make_runtime().open_session()):
            with self.assertRaisesRegex(SkillNotReady, "runtime_session_mismatch"):
                bridge.execute(sid, snapshot=snapshot, session=invalid)
        session = self.runtime.open_session()
        runner, _ = bridge.execute(sid, snapshot=snapshot, session=session)
        self.assertIs(runner, session.runner)
        self.assertTrue(runner.state.evidence)
        # Replay provenance stays replay; a reusable fact is no hardware proof.
        self.assertTrue(all(e["source"].startswith("synthetic_replay/") for e in runner.state.evidence))


if __name__ == "__main__":
    unittest.main()
