"""G08 synthetic queue screening over verified Core sources."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeGSimulationTests(unittest.TestCase):
    def scenario(self, case='normal'):
        return next(row for row in load_scenarios('G') if row['id'] == f'G08-{case}')

    def assert_unknown(self, row, **kwargs):
        result = run_scenario(row, batch='G', **kwargs)
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertTrue(result['claims'])
        for claim in result['claims'].values():
            self.assertEqual((claim['value'], claim['evidence']), ('UNKNOWN', []))

    def test_exact_scenarios_and_core_provenance(self):
        report = evaluate('G')
        self.assertEqual((report['total'], report['passed']), (3, 3))
        self.assertEqual({row['id']: row['verdict'] for row in report['rows']}, {
            'G08-normal': 'HEALTHY', 'G08-fault': 'FAULT', 'G08-missing': 'UNKNOWN',
        })
        for case, severity in (('normal', 'HEALTHY'), ('fault', 'FAULT')):
            with self.subTest(case=case):
                captured = {}
                result = run_scenario(self.scenario(case), batch='G', inspect=captured.update)
                self.assertEqual(result['core_calls'], 2)
                self.assertEqual(result['source_errors'], {})
                traffic = captured['traffic'].state.fact('expansion.bandwidth_usage')
                queue = captured['queue'].state.fact('expansion.queue_delay')
                self.assertNotEqual(traffic['id'], queue['id'])
                supported = [claim for claim in result['claims'].values() if claim['value'] == 'TRUE']
                self.assertEqual([(claim['severity'], claim['evidence']) for claim in supported],
                                 [(severity, [queue['id']])])

        document = contracts('G')
        self.assertTrue(document['workflows']['G08']['limitation'].strip())
        for claim in document['claims']:
            self.assertTrue(claim['claim_id'].endswith('_v1'))
            self.assertEqual(claim['excludes'], [])
            self.assertEqual(len(claim['requires']), 1)
            predicate = claim['requires'][0]
            self.assertEqual((predicate['port'], predicate['field']), ('queue', 'queue_delay_ms'))
            self.assertIs(type(predicate['value']), int)

    def test_threshold_and_traffic_boundaries(self):
        for delay, rx, tx, verdict in (
            (0, 120, 20, 'HEALTHY'),
            (49.999, 120, 20, 'HEALTHY'),
            (50, 120, 0, 'HEALTHY'),
            (50, 0, 20, 'HEALTHY'),
            (50.001, 120, 20, 'FAULT'),
            (8, 0, 0, 'UNKNOWN'),
            (180, 0, 0, 'UNKNOWN'),
            (-0.001, 120, 20, 'UNKNOWN'),
            (180, -0.001, 20, 'UNKNOWN'),
            (180, 120, -0.001, 'UNKNOWN'),
        ):
            with self.subTest(delay=delay, rx=rx, tx=tx):
                row = self.scenario()
                row['sources']['queue']['values']['queue_delay_ms'] = delay
                row['sources']['traffic']['values'].update(rx_mbps=rx, tx_mbps=tx)
                if verdict == 'UNKNOWN':
                    self.assert_unknown(row)
                else:
                    self.assertEqual(run_scenario(row, batch='G')['verdict'], verdict)

    def test_wrong_types_and_nonfinite_values(self):
        for alias, field in (('queue', 'queue_delay_ms'),
                             ('traffic', 'rx_mbps'), ('traffic', 'tx_mbps')):
            for value in ('50', True, None, {}, [], float('nan'), float('inf'), float('-inf')):
                with self.subTest(alias=alias, field=field, value=value):
                    row = self.scenario('fault')
                    row['sources'][alias]['values'][field] = value
                    self.assert_unknown(row)

    def test_missing_malformed_and_unaligned_sources(self):
        for alias in ('queue', 'traffic'):
            for values in (None, {}):
                with self.subTest(alias=alias, values=values):
                    row = self.scenario('fault')
                    row['sources'][alias]['values'] = values
                    self.assert_unknown(row)
        row = self.scenario('fault')
        del row['sources']['traffic']['values']['tx_mbps']
        self.assert_unknown(row)
        row = self.scenario('fault')
        row['sources']['traffic']['simulated_at'] = '2026-11-19T08:00:01Z'
        self.assert_unknown(row)

    def test_rechecks_target_scope_permission_timeout_and_freshness(self):
        for defect in ('target', 'scope', 'permission', 'timeout', 'stale'):
            with self.subTest(defect=defect):
                def corrupt(sources):
                    state = sources['traffic'].state
                    fact = state.fact('expansion.bandwidth_usage')
                    if defect == 'permission':
                        state.permissions.clear()
                    elif defect == 'stale':
                        fact['age_s'] = fact['ttl_s']
                    elif defect == 'timeout':
                        fact['status'] = 'TIMEOUT'
                    else:
                        fact[defect] = 'foreign'

                self.assert_unknown(self.scenario('fault'), inspect=corrupt)

    def test_gold_is_scorer_only_and_rejected_in_scenarios_and_config(self):
        original = Path.read_text

        def guard(path, *args, **kwargs):
            self.assertNotEqual(path.name, 'gold.json')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'read_text', guard):
            result = run_scenario(self.scenario(), batch='G')
            self.assertEqual(result['verdict'], 'HEALTHY')

        sim_dir, diagnostics = batch_paths('G')
        for target, loader in ((sim_dir / 'scenarios.json', load_scenarios), (diagnostics, contracts)):
            with self.subTest(target=target.name):
                def inject_gold(path, *args, **kwargs):
                    content = original(path, *args, **kwargs)
                    if path != target:
                        return content
                    document = json.loads(content)
                    container = (document['workflows']['G08'] if path == diagnostics
                                 else document['scenarios'][0]['sources']['queue']['values'])
                    container['expected_verdict'] = 'HEALTHY'
                    return json.dumps(document)

                with patch.object(Path, 'read_text', inject_gold):
                    with self.assertRaisesRegex(SimulationError, 'gold-like'):
                        loader('G')
