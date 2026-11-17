"""Independent contracts for live session selection, repair bounds and invalidation."""
import unittest
from unittest.mock import patch

from gateway_pilot.core import PlanError
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_launcher import FakeLaptopBackend


class SessionExecutionFeaturesTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.backend = FakeLaptopBackend()
        self.entry = composition('live', backend=self.backend, clock=lambda: self.now)
        self.runtime, self.session = self.entry['runtime'], self.entry['session']

    def test_live_gos_selection_audits_real_ready_nodes_on_same_runner(self):
        original = self.session.runner
        runner, plan = self.session.execute(['laptop.route', 'laptop.wifi'])
        self.assertIs(runner, original)
        self.assertEqual(self.session.method, 'gos')
        self.assertEqual(runner.max_repairs, 2)
        self.assertEqual(runner.calls, 3)
        self.assertEqual(len(self.session.retrievals), 3)
        for row in self.session.retrievals:
            self.assertIn(row['selected_ready'], row['ready_set'])
        self.assertTrue(self.session.state.fact('laptop.route'))
        self.assertTrue(self.session.state.fact('laptop.wifi'))

    def test_approved_live_transient_failure_retries_on_same_runner(self):
        runner = self.session.runner
        calls = []
        original = self.backend.sample

        def transient(function, arguments, context):
            calls.append(function['function_id'])
            if len(calls) == 1:
                raise OSError('one transient backend failure')
            return original(function, arguments, context)

        with patch.object(self.backend, 'sample', side_effect=transient):
            actual, plan = self.session.execute(['laptop.route'])
        self.assertIs(actual, runner)
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[:2], ['clients.resolve', 'clients.resolve'])
        self.assertEqual(runner.calls, 3)
        self.assertIsNotNone(self.session.state.fact('laptop.route'))
        self.assertFalse(runner.incomplete)
        self.assertTrue(any(row['operator'] == 'RETRY' for row in plan.audit))
        self.assertEqual(runner.global_replans, 0)
        self.assertEqual(runner.repairs, 0)
        self.assertTrue(all(f.retry_limit == 1 for f in self.runtime.registry.functions.values()))

    def test_persistent_live_failure_stops_after_approved_attempts(self):
        runner = self.session.runner
        with patch.object(self.backend, 'sample', side_effect=OSError('persistent')) as sample:
            actual, _ = self.session.execute(['laptop.route'])
        self.assertIs(actual, runner)
        self.assertEqual(sample.call_count, 2)
        self.assertEqual(runner.calls, 2)
        self.assertIsNone(self.session.state.fact('laptop.route'))
        self.assertTrue(runner.incomplete)
        self.assertLessEqual(runner.global_replans, 1)
        self.assertLessEqual(runner.repairs, 3)

    def test_prior_plan_count_is_included_before_compile_or_io(self):
        self.session._max_plans = 2
        self.session._prior_plans = 1
        self.session.execute(['client.identity'])
        calls = self.backend.calls
        with self.assertRaisesRegex(PlanError, 'session_plan_budget'):
            self.session.execute(['laptop.route'])
        self.assertEqual(self.backend.calls, calls)
        self.assertEqual(len(self.session.runner.plans), 1)
        # Even direct trusted Runner attachment obeys the session validator.
        plan = self.session.runner.compiler().compile(['laptop.route'], self.session.state)
        with self.assertRaisesRegex(PlanError, 'session_plan_budget'):
            self.session.runner.attach(plan)
        self.assertEqual(len(self.session.runner.plans), 1)

    def test_context_revocation_during_call_closes_and_invalidates(self):
        self.session.execute(['client.identity'])
        original = self.backend.sample

        def revoke(function, arguments, context):
            result = original(function, arguments, context)
            self.backend.bssid = '02:00:00:00:00:02'
            return result

        calls = self.backend.calls
        with patch.object(self.backend, 'sample', side_effect=revoke):
            with self.assertRaisesRegex(PlanError, 'session_context_invalid'):
                self.session.execute(['laptop.route', 'laptop.wifi'])
        self.assertTrue(self.session.closed)
        self.assertEqual(self.backend.calls - calls, 1)
        self.assertIsNone(self.session.state.fact('client.identity'))
        self.assertIsNone(self.session.state.fact('laptop.route'))
        self.assertIsNone(self.session.state.fact('laptop.wifi'))

    def test_chat_turn_deadline_stops_before_second_function(self):
        from gateway_pilot.application.skill_chat import SkillChat
        from gateway_pilot.application.skill_launcher import SkillLauncher
        from tests.test_skill_chat import Model, choice

        launcher = SkillLauncher(factory=lambda mode: self.entry, clock=lambda: self.now)
        model = Model([choice(skills=['laptop.route.inspect'])])
        chat = SkillChat(launcher, model_factory=lambda: model,
                         clock=lambda: self.now, max_elapsed_s=1)
        original = self.backend.sample

        def slow(function, arguments, context):
            result = original(function, arguments, context)
            self.now += 2
            return result

        deadline = self.session.runner.deadline_s
        with patch.object(self.backend, 'sample', side_effect=slow):
            result = chat.chat('Kiểm tra route laptop')
        self.assertEqual(self.backend.calls, 1)
        self.assertEqual(result['calls'], 1)
        self.assertIsNone(self.session.state.fact('laptop.route'))
        self.assertEqual(self.session.runner.deadline_s, deadline)


if __name__ == '__main__':
    unittest.main()


class SemanticFailureFallbackTests(unittest.TestCase):
    def test_embedding_error_is_reported_and_gos_still_enters_core(self):
        from gateway_pilot.skill_expansion.deployment import composition
        from tests.test_skill_launcher import FakeLaptopBackend
        class BrokenEncoder:
            local_only=True
            model_id='test-broken-local'
            def encode_many(self,texts):raise RuntimeError('provider unavailable')
        entry=composition('live',backend=FakeLaptopBackend(),clock=lambda:100.)
        entry['runtime'].registry.configure_semantic(BrokenEncoder())
        session=entry['session'];session.method='hybrid'
        session.execute(['laptop.route'])
        self.assertEqual(session.method,'gos')
        self.assertEqual(session.retrievals[0]['semantic_status'],'ERROR')
        self.assertIsNotNone(session.state.fact('laptop.route'))
        self.assertEqual(session.runner.calls,2)
