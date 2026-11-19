"""C06 replay screening requires agreement between verified STP and loss samples."""

import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import assess, batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeCSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = {row['id']: row for row in load_scenarios('C')}

    def scenario(self, name='fault'):
        return deepcopy(self.scenarios[f'C06-{name}'])

    def assert_no_claim_evidence(self, result):
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertTrue(result['claims'])
        for claim in result['claims'].values():
            self.assertEqual((claim['value'], claim['evidence']), ('UNKNOWN', []))

    def test_exact_scenarios_and_verified_claim_provenance(self):
        report = evaluate('C')
        self.assertEqual((report['total'], report['passed']), (3, 3))
        self.assertEqual({row['id']: (row['verdict'], row['core_calls']) for row in report['rows']}, {
            'C06-normal': ('HEALTHY', 3), 'C06-fault': ('FAULT', 3), 'C06-missing': ('UNKNOWN', 2),
        })
        self.assert_no_claim_evidence(next(row for row in report['rows'] if row['id'] == 'C06-missing'))

        document = contracts('C')
        workflow = document['workflows']['C06']
        self.assertTrue(workflow['limitation'].strip())
        for claim in document['claims']:
            self.assertTrue(claim['claim_id'].endswith('_v1'))
            self.assertEqual(claim['excludes'], [])
            self.assertEqual(len(claim['requires']), 1)
            predicate = claim['requires'][0]
            self.assertIn((predicate['port'], predicate['field']),
                          {('stp', 'topology_changes'), ('loss', 'packet_loss_pct')})
            self.assertIs(type(predicate['value']), int)

        for case, severity in (('normal', 'HEALTHY'), ('fault', 'FAULT')):
            with self.subTest(case=case):
                sources = {}
                result = run_scenario(self.scenario(case), batch='C', inspect=sources.update)
                self.assertEqual(result['source_errors'], {})
                facts = {
                    alias: sources[alias].state.fact(spec['function_id'])
                    for alias, spec in workflow['sources'].items()
                }
                self.assertEqual(len({fact['id'] for fact in facts.values()}), 3)
                supported = {
                    claim_id: claim for claim_id, claim in result['claims'].items()
                    if claim['value'] == 'TRUE'
                }
                expected = {
                    claim['claim_id']: (severity, [facts[claim['requires'][0]['port']]['id']])
                    for claim in document['claims'] if claim['severity'] == severity
                }
                self.assertEqual({
                    claim_id: (claim['severity'], claim['evidence'])
                    for claim_id, claim in supported.items()
                }, expected)

    def test_signal_thresholds_and_disagreement(self):
        for changes, loss, verdict in (
            (0, 0, 'HEALTHY'),
            (0, 1, 'HEALTHY'),
            (0, 1.001, 'UNKNOWN'),
            (0, 10, 'UNKNOWN'),
            (1, 0, 'UNKNOWN'),
            (2, 10, 'UNKNOWN'),
            (3, 1, 'UNKNOWN'),
            (3, 9.999, 'UNKNOWN'),
            (3, 10, 'FAULT'),
            (3, 100, 'FAULT'),
            (3, 100.001, 'UNKNOWN'),
            (0, -0.001, 'UNKNOWN'),
            (-1, 0, 'UNKNOWN'),
        ):
            with self.subTest(changes=changes, loss=loss):
                row = self.scenario()
                row['sources']['stp']['values']['topology_changes'] = changes
                row['sources']['loss']['values']['packet_loss_pct'] = loss
                self.assertEqual(run_scenario(row, batch='C')['verdict'], verdict)

    def test_bridge_stp_and_latency_preconditions(self):
        for alias, field, value, verdict in (
            ('bridge', 'member_ports', -1, 'UNKNOWN'),
            ('bridge', 'member_ports', 0, 'UNKNOWN'),
            ('bridge', 'member_ports', 1, 'UNKNOWN'),
            ('bridge', 'member_ports', 2, 'FAULT'),
            ('bridge', 'bridge_up', False, 'UNKNOWN'),
            ('stp', 'stp_enabled', False, 'UNKNOWN'),
            ('loss', 'latency_ms', -0.001, 'UNKNOWN'),
            ('loss', 'latency_ms', 0, 'FAULT'),
        ):
            with self.subTest(field=field, value=value):
                row = self.scenario()
                row['sources'][alias]['values'][field] = value
                self.assertEqual(run_scenario(row, batch='C')['verdict'], verdict)

    def test_wrong_types_and_nonfinite_values(self):
        for alias, field, values in (
            ('bridge', 'bridge_up', ('true', 1, None)),
            ('bridge', 'member_ports', ('2', True, 2.5, None)),
            ('stp', 'stp_enabled', ('true', 1, None)),
            ('stp', 'topology_changes', ('3', True, 3.5, None)),
            ('loss', 'latency_ms', ('20', True, None, float('nan'), float('inf'))),
            ('loss', 'packet_loss_pct', ('10', True, None, [], {}, float('nan'),
                                        float('inf'), float('-inf'))),
        ):
            for value in values:
                with self.subTest(field=field, value=value):
                    row = self.scenario()
                    row['sources'][alias]['values'][field] = value
                    self.assert_no_claim_evidence(run_scenario(row, batch='C'))

    def test_null_malformed_absent_and_unaligned_sources(self):
        for alias in self.scenario()['sources']:
            for values in (None, {}):
                with self.subTest(alias=alias, values=values):
                    row = self.scenario()
                    row['sources'][alias]['values'] = values
                    self.assert_no_claim_evidence(run_scenario(row, batch='C'))
        self.assert_no_claim_evidence(assess('C06', {}, batch='C'))

        row = self.scenario()
        row['sources']['loss']['simulated_at'] = '2026-11-19T08:00:01Z'
        result = run_scenario(row, batch='C')
        self.assertEqual(result['reason'], 'different_sample_times')
        self.assert_no_claim_evidence(result)

    def test_scope_target_permission_timeout_and_freshness(self):
        for defect in ('scope', 'target', 'permission', 'timeout', 'stale'):
            with self.subTest(defect=defect):
                def invalidate(sources):
                    state = sources['bridge'].state
                    fact = state.fact('expansion.bridge_health')
                    if defect == 'permission':
                        state.permissions.clear()
                    elif defect == 'timeout':
                        fact['status'] = 'TIMEOUT'
                    elif defect == 'stale':
                        fact['age_s'] = fact['ttl_s']
                    else:
                        fact[defect] = 'foreign'

                self.assert_no_claim_evidence(run_scenario(self.scenario(), batch='C', inspect=invalidate))

    def test_gold_is_unread_during_execution_and_rejected_in_inputs(self):
        original = Path.read_text

        def guard(path, *args, **kwargs):
            self.assertNotEqual(path.name, 'gold.json')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'read_text', guard):
            row = next(row for row in load_scenarios('C') if row['id'] == 'C06-normal')
            self.assertEqual(run_scenario(row, batch='C')['verdict'], 'HEALTHY')

        sim_dir, diagnostics = batch_paths('C')
        for target, loader in ((sim_dir / 'scenarios.json', load_scenarios), (diagnostics, contracts)):
            with self.subTest(target=target.name):
                def inject_gold(path, *args, **kwargs):
                    content = original(path, *args, **kwargs)
                    if path != target:
                        return content
                    document = json.loads(content)
                    container = (document['workflows']['C06'] if path == diagnostics
                                 else document['scenarios'][0]['sources']['stp']['values'])
                    container['expected_verdict'] = 'HEALTHY'
                    return json.dumps(document)

                with patch.object(Path, 'read_text', inject_gold):
                    with self.assertRaisesRegex(SimulationError, 'gold-like'):
                        loader('C')
