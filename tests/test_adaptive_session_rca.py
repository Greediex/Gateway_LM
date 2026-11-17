"""Adaptive RCA reuses the catalog session and its bounded execution kernel."""
import unittest
from unittest.mock import patch

from gateway_pilot.core import PlanError
from gateway_pilot.graph_v3.rca_agent import RCAAgent
from gateway_pilot.graph_v3.task_runtime import TaskRuntime
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_launcher import FakeLaptopBackend


class AdaptiveSessionRCATests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.backend = FakeLaptopBackend()
        entry = composition('live', backend=self.backend, clock=lambda: self.now)
        self.runtime, self.session = entry['runtime'], entry['session']
        self.agent = RCAAgent(self.runtime.registry)

    def run_task(self, **options):
        args = dict(request='Diagnose laptop connection', workflows=['LAPTOP-ROUTE'],
                    allowed_ports=['laptop.route'], diagnostic=True)
        args.update(options)
        return TaskRuntime.run_session(self.session, **args)

    def test_same_runner_state_and_existing_facts_are_reused(self):
        runner, state = self.session.runner, self.session.state
        self.session.execute(['client.identity'])
        calls = runner.calls
        with patch('gateway_pilot.graph_v3.runner.GraphRunner.__init__', side_effect=AssertionError('new runner')):
            result = self.run_task()
        self.assertIs(self.session.runner, runner)
        self.assertIs(self.session.state, state)
        self.assertEqual(result['calls_added'], 1)
        self.assertEqual(runner.calls, calls + 1)
        self.assertEqual(result['status'], 'HEALTHY_OBSERVED')
        self.assertEqual(result['steps'][0]['goal'], 'laptop.route')
        self.assertTrue(result['assessments'][0]['evidence_ids'])

    def test_lookup_and_already_sufficient_evidence_need_no_measurements(self):
        lookup = self.run_task(diagnostic=False)
        self.assertEqual((lookup['calls_added'], self.backend.calls), (0, 0))
        self.assertEqual(lookup['assessments'][0]['decision'], 'INCONCLUSIVE')
        self.session.execute(['laptop.route'])
        calls = self.backend.calls
        result = self.run_task()
        self.assertEqual(result['steps'], [])
        self.assertEqual(self.backend.calls, calls)

    def test_allowed_ports_filter_and_unregistered_ports_fail_closed(self):
        result = self.run_task(allowed_ports=['laptop.wifi'])
        self.assertEqual(result['reason'], 'no_admissible_evidence_goal')
        self.assertEqual(self.backend.calls, 0)
        with self.assertRaisesRegex(PlanError, 'rca_session_limits'):
            self.run_task(allowed_ports=['shell.exec'])

    def test_revoked_capability_invalidates_cached_proof(self):
        self.session.execute(['laptop.route'])
        calls = self.backend.calls
        with patch.object(self.backend, 'supports', return_value=False):
            result = self.run_task()
        self.assertIsNone(self.session.state.fact('laptop.route'))
        self.assertIsNone(result['diagnosis'])
        self.assertEqual(result['status'], 'INCONCLUSIVE')
        self.assertEqual(self.backend.calls, calls)

    def test_deadline_call_and_step_budgets_are_cumulative(self):
        original = self.session.runner.deadline_s
        result = self.run_task(deadline=self.now)
        self.assertEqual(result['reason'], 'rca_deadline_exhausted')
        self.assertEqual(self.backend.calls, 0)
        self.assertEqual(self.session.runner.deadline_s, original)
        result = self.run_task(max_steps=0)
        self.assertEqual(result['steps'], [])
        self.session.runner.max_calls = 1
        result = self.run_task()
        self.assertEqual(self.backend.calls, 1)
        self.assertEqual(result['status'], 'INCONCLUSIVE')
        self.assertEqual(result['reason'], 'rca_execution_budget_exhausted')
        self.assertEqual(self.session.runner.calls, 1)

    def test_failure_does_not_repeat_or_invent_a_claim(self):
        with patch.object(self.backend, 'sample', side_effect=OSError('unavailable')):
            result = self.run_task()
        self.assertEqual(result['status'], 'INCONCLUSIVE')
        self.assertIsNone(result['diagnosis'])
        self.assertLessEqual(len(result['steps']), 1)
        self.assertEqual(result['reason'], 'rca_no_progress')

    def test_step_limit_and_deadline_between_dependency_calls(self):
        result = self.run_task(workflows=['LAPTOP-ROUTE', 'LAPTOP-WIFI'],
                               allowed_ports=['laptop.route', 'laptop.wifi'], max_steps=1)
        self.assertEqual(len(result['steps']), 1)
        self.assertEqual(result['reason'], 'rca_step_budget_exhausted')
        self.assertEqual(sum(a['decision'] == 'INCONCLUSIVE'
                             for a in result['assessments']), 1)
        entry = composition('live', backend=self.backend, clock=lambda: self.now)
        session = entry['session']
        original = self.backend.sample

        def slow(function, arguments, context):
            result = original(function, arguments, context)
            self.now += 2
            return result

        calls = self.backend.calls
        with patch.object(self.backend, 'sample', side_effect=slow):
            result = TaskRuntime.run_session(session, request='Diagnose route',
                workflows=['LAPTOP-ROUTE'], allowed_ports=['laptop.route'],
                diagnostic=True, deadline=self.now + 1)
        self.assertEqual(self.backend.calls - calls, 1)
        self.assertEqual(result['reason'], 'rca_deadline_exhausted')
        self.assertEqual(result['status'], 'INCONCLUSIVE')

    def test_observation_only_claim_does_not_prove_a_fault(self):
        # Claim contracts are installed before the session pins are captured.
        from gateway_pilot.graph_v3.claims import ClaimBook
        entry = composition('live', backend=FakeLaptopBackend(), clock=lambda: self.now)
        rt = entry['runtime']
        rt.registry.workflows = {'OBS': dict(status='SUPPORTED', kind='DIAGNOSE',
                                             target_scope='client', claims=['route_seen'])}
        rt.registry.claim_book = ClaimBook([dict(claim_id='route_seen', diagnosis='route_seen',
            severity='OBSERVATION', scope='client', workflow='OBS', message_key='route_seen',
            requires=[dict(port='laptop.route', field='has_route', op='eq', value=True)],
            excludes=[])], rt.registry.ports, rt.registry.workflows)
        session = rt.open_session()
        session.execute(['laptop.route'])
        result = RCAAgent(rt.registry).diagnose_session(session, workflows=['OBS'],
                                                      allowed_ports=['laptop.route'])
        self.assertEqual(result['status'], 'INCONCLUSIVE')
        self.assertIsNone(result['diagnosis'])
        self.assertEqual(len(result['assessments'][0]['observed_patterns']), 1)
        self.assertEqual(result['calls_added'], 0)


if __name__ == '__main__':
    unittest.main()
