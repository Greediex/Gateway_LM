"""WP-A3: ephemeral approval only; client replay still uses the shared Core."""
import copy
from itertools import product
import unittest
from unittest.mock import patch

from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.core import ROOT, PlanError
from gateway_pilot.skill_expansion import deployment as dep
from gateway_pilot.skill_expansion.client_replay import normal_fixtures
from scripts.prepare_replay_client_approval import proposed_approval
from scripts.simulate_skills import assess_claims


class ClientReplayTests(unittest.TestCase):
    def setUp(self):
        dep.deployment.cache_clear()
        self.addCleanup(dep.deployment.cache_clear)
        self.now = 100.0
        self.pins = proposed_approval()

    def approved_read(self, path, *args, **kwargs):
        doc = read_json(path, *args, **kwargs)
        if str(path).endswith('approvals.json'):
            doc['replay_client'] = copy.deepcopy(self.pins)
        return doc

    def composition(self, backend=None):
        with patch.object(dep, 'read_json', side_effect=self.approved_read):
            return dep.composition('replay_client', backend=backend, clock=lambda: self.now)

    def execute(self, entry, skill):
        return entry['bridge'].execute(skill, snapshot=entry['runtime'].probe(), session=entry['session'])

    def test_production_is_disabled_and_approval_file_unchanged(self):
        path = ROOT / 'config/skill_launcher/approvals.json'
        before = path.read_bytes()
        proposed_approval()
        with self.assertRaisesRegex(PlanError, 'skill_deployment_not_approved'):
            dep.composition('replay_client')
        self.assertEqual(path.read_bytes(), before)

    def test_normal_skills_verify_identity_first_and_reuse_it(self):
        entry = self.composition()
        self.assertEqual(set(entry['actions']), {'A04', 'A06', 'A08'})
        self.assertEqual(entry['runtime'].context.scope, 'client')
        for index, sid in enumerate(('A04', 'A06', 'A08'), 2):
            runner, plan = self.execute(entry, sid)
            self.assertEqual(runner.calls, index)
            identity = runner.state.fact('client.identity')
            self.assertEqual(identity['value']['client_id'], entry['runtime'].context.target_id)
            self.assertEqual(assess_claims(runner.state, sid)['verdict'], 'HEALTHY')
            self.assertTrue(all(e['source'].startswith('synthetic_replay/') for e in runner.state.evidence))
        self.assertEqual(entry['session'].state.evidence[0]['port'], 'client.identity')
        self.assertEqual(entry['backend']._fixture, normal_fixtures())

    def test_all_deployment_pins_fail_closed(self):
        for key in ('registry_digest', 'actions_digest', 'fixtures_digest', 'backend_revision', 'source'):
            with self.subTest(key=key):
                dep.deployment.cache_clear()
                original = self.pins[key]
                self.pins[key] = '0' * 64
                with self.assertRaises(PlanError):
                    self.composition()
                self.pins[key] = original

    def test_fixture_drift_invalidates_session(self):
        entry = self.composition()
        self.execute(entry, 'A04')
        calls = entry['session'].runner.calls
        entry['backend']._fixture.clear()
        with self.assertRaisesRegex(PlanError, 'session_context_invalid'):
            entry['session'].execute(list(entry['actions']['A04']['required_ports']))
        self.assertEqual(entry['session'].runner.calls, calls)
        self.assertTrue(entry['session'].closed)

    def test_missing_permissions_block_before_execution(self):
        entry = self.composition()
        entry['runtime'].permissions = frozenset()
        snapshot = entry['runtime'].probe()
        self.assertTrue(all(f.status != 'AVAILABLE' for f in snapshot.functions))
        with self.assertRaises(PlanError):
            entry['session'].execute(list(entry['actions']['A04']['required_ports']))
        self.assertEqual(entry['session'].runner.calls, 0)

    def test_invalid_samples_never_admit_client_fact(self):
        for defect, stage in product(('target', 'scope', 'schema', 'timeout', 'stale', 'identity'),
                                     ('identity', 'measurement')):
            with self.subTest(defect=defect, stage=stage):
                entry = self.composition()
                backend = entry['backend']
                sample = backend.sample_preview
                def broken(function, arguments, context):
                    is_identity = 'client.identity' in function['outputs']
                    if (stage == 'measurement' and is_identity) or (stage == 'identity' and not is_identity):
                        return ToolResult(observations=sample(function, arguments, context))
                    if defect == 'timeout':
                        raise TimeoutError('synthetic timeout')
                    rows = list(sample(function, arguments, context))
                    for row in rows:
                        if defect == 'target': row['target'] = 'foreign-client'
                        elif defect == 'scope': row['scope'] = 'gateway'
                        elif defect == 'schema': row['value'] = {'malformed': True}
                        elif defect == 'stale': row['age_s'] = row['ttl_s'] + 1
                        elif row['port'] == 'client.identity': row['value']['client_id'] = 'foreign-client'
                        else: row['target'] = 'foreign-client'
                    return ToolResult(observations=tuple(rows))
                with patch.object(backend, 'sample', side_effect=broken):
                    runner, _ = self.execute(entry, 'A04')
                if stage == 'identity':
                    self.assertIsNone(runner.state.fact('client.identity'))
                else:
                    self.assertIsNotNone(runner.state.fact('client.identity'))
                for port in entry['actions']['A04']['required_ports']:
                    self.assertIsNone(runner.state.fact(port))
                self.assertEqual(assess_claims(runner.state, 'A04')['verdict'], 'UNKNOWN')

    def test_facts_expire_on_core_clock(self):
        entry = self.composition()
        runner, _ = self.execute(entry, 'A08')
        fact = runner.state.fact('expansion.client_association')
        runner.state.clock = lambda: fact['_received_at'] + fact['ttl_s'] + 1
        self.assertEqual(assess_claims(runner.state, 'A08')['verdict'], 'UNKNOWN')


if __name__ == '__main__':
    unittest.main()
