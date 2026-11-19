"""COV-I screening rules and fail-closed source validation over Core replay."""
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import assess, batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeISimulationTests(unittest.TestCase):
    def scenario(self):
        return next(row for row in load_scenarios('I') if row['id'] == 'I07-fault')

    def assert_unknown(self, result):
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertTrue(result['claims'])
        for claim in result['claims'].values():
            self.assertEqual(claim['value'], 'UNKNOWN')
            self.assertEqual(claim['evidence'], [])

    def test_three_scored_scenarios_use_core_and_single_field_claims(self):
        report = evaluate('I')
        self.assertEqual((report['passed'], report['total']), (3, 3))
        self.assertCountEqual([row['id'] for row in report['rows']],
                              ['I07-normal', 'I07-fault', 'I07-missing'])
        for row in report['rows']:
            with self.subTest(scenario=row['id']):
                self.assertTrue(row['limitation'])
                if row['id'] == 'I07-missing':
                    self.assertGreater(row['core_calls'], 0)
                    self.assert_unknown(row)
                else:
                    self.assertGreaterEqual(row['core_calls'], 2)
                    self.assertFalse(row['source_errors'])
                    proof = [claim for claim in row['claims'].values() if claim['value'] == 'TRUE']
                    self.assertEqual(len(proof), 1)
                    self.assertEqual(proof[0]['severity'], row['verdict'])
                    evidence_id, = proof[0]['evidence']
                    self.assertTrue(evidence_id.startswith('expansion.identity_consistency:'))

        for claim in contracts('I')['claims']:
            self.assertTrue(claim['claim_id'].endswith('_v1'))
            self.assertFalse(claim['excludes'])
            predicate, = claim['requires']
            self.assertEqual((predicate['port'], predicate['field'], predicate['op']),
                             ('identity', 'hostname_conflict', 'eq'))
            self.assertIsInstance(predicate['value'], bool)

    def test_boundary_and_insufficient_samples(self):
        for alias, field, value, verdict in (
            ('identity', 'hostname_conflict', False, 'HEALTHY'),
            ('identity', 'hostname_conflict', True, 'FAULT'),
            ('identity', 'ip_mac_consistent', False, 'UNKNOWN'),
            ('association', 'associated', False, 'UNKNOWN'),
            ('association', 'access_point_id', '', 'UNKNOWN'),
            ('association', 'access_point_id', ' \t', 'UNKNOWN'),
            ('association', 'access_point_id', 'a', 'FAULT'),
        ):
            with self.subTest(alias=alias, field=field, value=value):
                row = self.scenario()
                row['sources'][alias]['values'][field] = value
                result = run_scenario(row, batch='I')
                self.assertEqual(result['verdict'], verdict)
                if verdict == 'UNKNOWN':
                    self.assert_unknown(result)

        row = self.scenario()
        row['sources']['association']['simulated_at'] = '2026-11-19T08:00:01Z'
        result = run_scenario(row, batch='I')
        self.assertEqual(result['reason'], 'different_sample_times')
        self.assert_unknown(result)

    def test_wrong_types_and_missing_sources(self):
        for alias, field, values in (
            ('identity', 'hostname_conflict', ('false', 0, 1, None)),
            ('identity', 'ip_mac_consistent', ('true', 1, None)),
            ('association', 'associated', ('true', 1, None)),
            ('association', 'access_point_id', (True, 1, [], None)),
        ):
            for value in values:
                with self.subTest(alias=alias, field=field, value=value):
                    row = self.scenario()
                    row['sources'][alias]['values'][field] = value
                    self.assert_unknown(run_scenario(row, batch='I'))

        for alias in self.scenario()['sources']:
            for values in (None, {}):
                with self.subTest(alias=alias, values=values):
                    row = self.scenario()
                    row['sources'][alias]['values'] = values
                    self.assert_unknown(run_scenario(row, batch='I'))

        def remove_association(sources):
            del sources['association']

        self.assert_unknown(run_scenario(self.scenario(), batch='I', inspect=remove_association))
        self.assert_unknown(assess('I07', {}, batch='I'))

    def test_unusable_core_facts(self):
        for alias in self.scenario()['sources']:
            for defect in ('target', 'scope', 'permission', 'timeout', 'stale'):
                with self.subTest(alias=alias, defect=defect):
                    def invalidate(sources):
                        state = sources[alias].state
                        spec = contracts('I')['workflows']['I07']['sources'][alias]
                        fact = state.fact(spec['function_id'])
                        if defect == 'permission':
                            state.permissions.clear()
                        elif defect == 'timeout':
                            fact['status'] = 'TIMEOUT'
                        elif defect == 'stale':
                            fact['age_s'] = fact['ttl_s']
                        else:
                            fact[defect] = 'foreign'

                    self.assert_unknown(run_scenario(self.scenario(), batch='I', inspect=invalidate))

    def test_gold_is_unread_during_execution_and_rejected_in_inputs(self):
        read_text = Path.read_text

        def guarded_read(path, *args, **kwargs):
            self.assertNotEqual(path.name, 'gold.json')
            return read_text(path, *args, **kwargs)

        with patch.object(Path, 'read_text', guarded_read):
            self.assertEqual(run_scenario(self.scenario(), batch='I')['verdict'], 'FAULT')

        sim_dir, diagnostics = batch_paths('I')
        for path, loader in ((sim_dir / 'scenarios.json', load_scenarios), (diagnostics, contracts)):
            with self.subTest(path=path.name):
                document = json.loads(read_text(path, encoding='utf-8'))
                if path == diagnostics:
                    container = document['workflows']['I07']
                else:
                    container = document['scenarios'][0]['sources']['identity']['values']
                container['expected_verdict'] = 'HEALTHY'

                def inject_gold(requested_path, *args, **kwargs):
                    if requested_path == path:
                        return json.dumps(document)
                    return read_text(requested_path, *args, **kwargs)

                with patch.object(Path, 'read_text', inject_gold):
                    with self.assertRaisesRegex(SimulationError, 'gold-like'):
                        loader('I')
