"""COV-D screening over Core facts with scoped synthetic inputs."""

import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeDSimulationTests(unittest.TestCase):
    def scenario(self, state='normal'):
        return next(row for row in load_scenarios('D') if row['id'] == f'D04-{state}')

    def assert_unknown(self, row, **kwargs):
        result = run_scenario(row, batch='D', **kwargs)
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertTrue(result['claims'])
        for claim in result['claims'].values():
            self.assertEqual((claim['value'], claim['evidence']), ('UNKNOWN', []))

    def test_exact_fixtures_and_core_provenance(self):
        report = evaluate('D')
        self.assertEqual((report['total'], report['passed']), (3, 3))
        self.assertEqual({row['id']: row['verdict'] for row in report['rows']}, {
            'D04-normal': 'HEALTHY', 'D04-fault': 'FAULT', 'D04-missing': 'UNKNOWN',
        })
        for case in ('normal', 'fault'):
            with self.subTest(case=case):
                captured = {}
                result = run_scenario(self.scenario(case), batch='D', inspect=captured.update)
                self.assertEqual(result['core_calls'], 3)
                self.assertIsNotNone(captured['neighbors'].state.fact('expansion.neighbor_table'))
                fact = captured['identity'].state.fact('expansion.identity_consistency')
                supported = [c for c in result['claims'].values() if c['value'] == 'TRUE']
                self.assertEqual([c['evidence'] for c in supported], [[fact['id']]])

        for claim in contracts('D')['claims']:
            self.assertTrue(claim['claim_id'].endswith('_v1'))
            self.assertEqual(len(claim['requires']), 1)
            self.assertEqual(claim['excludes'], [])
            self.assertEqual(claim['requires'][0]['field'], 'ip_mac_consistent')
            self.assertIs(type(claim['requires'][0]['value']), bool)

    def test_neighbor_sample_boundaries_and_wrong_types(self):
        for count, failed, verdict in (
            (1, 0, 'HEALTHY'), (2, 0, 'HEALTHY'), (0, 0, 'UNKNOWN'),
            (-1, 0, 'UNKNOWN'), (4, -1, 'UNKNOWN'), (4, 1, 'UNKNOWN'),
            ('4', 0, 'UNKNOWN'), (True, 0, 'UNKNOWN'), (1.5, 0, 'UNKNOWN'),
            (None, 0, 'UNKNOWN'), (4, False, 'UNKNOWN'), (4, '0', 'UNKNOWN'),
        ):
            with self.subTest(count=count, failed=failed):
                row = self.scenario()
                row['sources']['neighbors']['values'] = {'neighbor_count': count, 'failed_entries': failed}
                if verdict == 'UNKNOWN':
                    self.assert_unknown(row)
                else:
                    self.assertEqual(run_scenario(row, batch='D')['verdict'], verdict)

    def test_missing_or_unusable_sources_suppress_even_a_known_mismatch(self):
        fault = self.scenario('fault')
        for alias in fault['sources']:
            with self.subTest(missing=alias):
                row = copy.deepcopy(fault)
                row['sources'][alias]['values'] = None
                self.assert_unknown(row)
        for bad_sample in ({}, {'ip_mac_consistent': 0, 'hostname_conflict': False}):
            with self.subTest(identity=bad_sample):
                row = copy.deepcopy(fault)
                row['sources']['identity']['values'] = bad_sample
                self.assert_unknown(row)
        fault['sources']['neighbors']['values']['neighbor_count'] = 0
        self.assert_unknown(fault)

    def test_rechecks_scope_permissions_and_freshness(self):
        for defect in ('target', 'scope', 'permission', 'timeout', 'stale'):
            with self.subTest(defect=defect):
                def corrupt(sources):
                    state = sources['neighbors'].state
                    fact = state.fact('expansion.neighbor_table')
                    if defect == 'target':
                        fact['target'] = 'foreign'
                    elif defect == 'scope':
                        fact['scope'] = 'client'
                    elif defect == 'permission':
                        state.permissions.clear()
                    elif defect == 'timeout':
                        fact['status'] = 'TIMEOUT'
                    else:
                        fact['age_s'] = fact['ttl_s'] + 1

                self.assert_unknown(self.scenario('fault'), inspect=corrupt)

    def test_gold_is_scorer_only_and_cannot_enter_scenarios_or_config(self):
        original = Path.read_text

        def guarded(path, *args, **kwargs):
            self.assertNotIn('gold', path.name)
            return original(path, *args, **kwargs)

        with patch.object(Path, 'read_text', guarded):
            self.assertEqual(run_scenario(self.scenario(), batch='D')['verdict'], 'HEALTHY')

        sim_dir, diagnostics = batch_paths('D')
        for target, loader in ((sim_dir / 'scenarios.json', load_scenarios), (diagnostics, contracts)):
            with self.subTest(target=target.name):
                def leaking(path, *args, **kwargs):
                    content = original(path, *args, **kwargs)
                    if path == target:
                        document = json.loads(content)
                        container = document['scenarios'][0]['sources']['identity'] if path != diagnostics else document
                        container['expected_verdict'] = 'HEALTHY'
                        return json.dumps(document)
                    return content

                with patch.object(Path, 'read_text', leaking), self.assertRaisesRegex(SimulationError, 'gold-like'):
                    loader('D')
