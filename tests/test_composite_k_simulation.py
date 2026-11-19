"""History verdicts over ordered gateway samples verified by Core replay."""
import copy
import json
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios, timestamp
from gateway_pilot.skill_expansion.replay_backend import StrictSkillReplayBackend
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeKSimulationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflows = contracts('K')['workflows']
        cls.scenarios = {row['id']: row for row in load_scenarios('K')}

    def run_k(self, row, **kwargs):
        return run_scenario(row, batch='K', **kwargs)

    def assert_unknown(self, result):
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertNotIn('history', result)
        self.assertTrue(result['claims'])
        for claim in result['claims'].values():
            self.assertEqual(claim['value'], 'UNKNOWN')
            self.assertFalse(claim['evidence'])

    def test_scored_scenarios_and_single_predicate_claims(self):
        report = evaluate('K')
        self.assertEqual((report['passed'], report['total']), (18, 18))
        skills = ('K01', 'K02', 'K03', 'K05', 'K06', 'K07')
        cases = {'normal': 'HEALTHY', 'fault': 'FAULT', 'missing': 'UNKNOWN'}
        self.assertEqual({r['id']: r['verdict'] for r in report['rows']},
                         {f'{sid}-{state}': verdict for sid in skills for state, verdict in cases.items()})
        for row in report['rows']:
            with self.subTest(scenario=row['id']):
                self.assertTrue(row['limitation'])
                if row['id'].endswith('-missing'):
                    self.assertGreater(row['core_calls'], 0)
                    self.assert_unknown(row)
                    continue
                wf = self.workflows[row['skill_id']]
                self.assertEqual(row['core_calls'], len(wf['sources']))
                samples = row['history']
                times = [timestamp(sample['simulated_at']) for sample in samples]
                self.assertGreaterEqual(len(times), 2)
                self.assertEqual(times, sorted(set(times)))
                ids = [sample['evidence_id'] for sample in samples]
                self.assertEqual(len(ids), len(set(ids)))
                for sample in samples:
                    source = self.scenarios[row['id']]['sources'][sample['source']]
                    self.assertEqual(sample['value'], source['values'])
                    self.assertTrue(sample['evidence_id'].startswith(
                        wf['sources'][sample['source']]['function_id'] + ':'))
                proof, = [c for c in row['claims'].values() if c['value'] == 'TRUE']
                self.assertEqual(proof['evidence'], ids)
                self.assertEqual(proof['severity'], row['verdict'])
        for claim in contracts('K')['claims']:
            self.assertTrue(claim['claim_id'].endswith('_v1'))
            self.assertFalse(claim['excludes'])
            predicate, = claim['requires']
            self.assertTrue(predicate['field'])
            self.assertIn(type(predicate['value']), (int, float, bool))

    def test_boundaries_and_insufficient_samples(self):
        for skill, alias, field, value, verdict in (
            ('K01', 'current', 'samples', 0, 'FAULT'),
            ('K01', 'current', 'samples', 1, 'FAULT'),
            ('K01', 'current', 'samples', 2, 'HEALTHY'),
            ('K01', 'current', 'window_seconds', 0, 'UNKNOWN'),
            ('K01', 'current', 'window_seconds', 29, 'UNKNOWN'),
            ('K02', 'baseline', 'packet_loss_pct', 2, 'HEALTHY'),
            ('K02', 'baseline', 'packet_loss_pct', 2.01, 'UNKNOWN'),
            ('K02', 'current', 'packet_loss_pct', 0, 'HEALTHY'),
            ('K02', 'current', 'packet_loss_pct', 2.01, 'FAULT'),
            ('K02', 'current', 'packet_loss_pct', 100, 'FAULT'),
            ('K03', 'first', 'packet_loss_pct', 4.99, 'UNKNOWN'),
            ('K03', 'middle', 'packet_loss_pct', 4.99, 'UNKNOWN'),
            ('K03', 'current', 'packet_loss_pct', 4.99, 'HEALTHY'),
            ('K03', 'current', 'packet_loss_pct', 5, 'FAULT'),
            ('K05', 'baseline', 'open_incidents', 1, 'UNKNOWN'),
            ('K05', 'current', 'open_incidents', 1, 'FAULT'),
            ('K06', 'current', 'loss_pct', 5, 'HEALTHY'),
            ('K06', 'current', 'loss_pct', 5.01, 'UNKNOWN'),
            ('K06', 'current', 'loss_pct', 100, 'UNKNOWN'),
            ('K07', 'before', 'loss_pct', 99.99, 'UNKNOWN'),
            ('K07', 'current', 'loss_pct', 5, 'HEALTHY'),
            ('K07', 'current', 'loss_pct', 5.01, 'UNKNOWN'),
        ):
            with self.subTest(skill=skill, alias=alias, field=field, value=value):
                row = copy.deepcopy(self.scenarios[f'{skill}-normal'])
                row['sources'][alias]['values'][field] = value
                self.assertEqual(self.run_k(row)['verdict'], verdict)

        reachable = self.scenarios['K06-normal']['sources']['previous']['values']
        failed = self.scenarios['K06-fault']['sources']['current']['values']
        row = copy.deepcopy(self.scenarios['K06-normal'])
        row['sources']['current']['values'] = failed
        self.assert_unknown(self.run_k(row))  # Mixed observations cannot show an outage interval.
        row = copy.deepcopy(self.scenarios['K07-normal'])
        row['sources']['before']['values'] = reachable
        self.assert_unknown(self.run_k(row))  # No preceding failure.

    def test_invalid_types_and_numeric_domains(self):
        for skill, alias, field, invalid in (
            ('K01', 'current', 'samples', (-1, '2', True, 1.5, None)),
            ('K01', 'previous', 'window_seconds', (-1, '30')),
            ('K02', 'current', 'latency_ms', (-0.01, '22', float('inf'))),
            ('K02', 'current', 'packet_loss_pct', (-0.01, 100.01, True, '2', float('nan'))),
            ('K03', 'middle', 'packet_loss_pct', (100.01, '5', [])),
            ('K05', 'current', 'incident_events', (-1, '2')),
            ('K05', 'current', 'open_incidents', (-1, False, 0.5)),
            ('K06', 'current', 'reachable', (0, 'true', None)),
            ('K07', 'current', 'loss_pct', (-1, 101, '1', False)),
        ):
            for value in invalid:
                with self.subTest(skill=skill, alias=alias, field=field, value=value):
                    row = copy.deepcopy(self.scenarios[f'{skill}-normal'])
                    row['sources'][alias]['values'][field] = value
                    self.assert_unknown(self.run_k(row))

    def test_every_source_is_mandatory(self):
        for skill in self.workflows:
            fault = self.scenarios[f'{skill}-fault']
            for alias in fault['sources']:
                with self.subTest(skill=skill, alias=alias):
                    row = copy.deepcopy(fault)
                    row['sources'][alias]['values'] = None
                    self.assert_unknown(self.run_k(row))
                    del row['sources'][alias]
                    self.assert_unknown(self.run_k(row))

    def test_history_order_span_ttl_and_proof_identity(self):
        normal = self.scenarios['K03-fault']
        for alias, time, verdict in (
            ('middle', '2026-11-19T08:00:00Z', 'UNKNOWN'),
            ('middle', '2026-11-19T08:00:21Z', 'UNKNOWN'),
            ('current', '2026-11-19T08:00:30Z', 'FAULT'),
            ('current', '2026-11-19T08:00:30.001Z', 'UNKNOWN'),
            ('current', '2026-11-19T08:00:20', 'UNKNOWN'),
        ):
            with self.subTest(alias=alias, time=time):
                row = copy.deepcopy(normal)
                row['sources'][alias]['simulated_at'] = time
                self.assertEqual(self.run_k(row)['verdict'], verdict)

        for defect in ('ttl', 'permission', 'duplicate', 'foreign_environment', 'producer'):
            with self.subTest(defect=defect):
                def corrupt(sources):
                    current = sources['current']
                    fact = current.state.fact('expansion.latency_loss')
                    if defect == 'ttl':
                        fact['age_s'] = fact['ttl_s'] + 1
                    elif defect == 'permission':
                        current.state.permissions.clear()
                    elif defect == 'duplicate':
                        sources['current'] = replace(current, state=sources['first'].state)
                    elif defect == 'foreign_environment':
                        current.state.set_environment(boot_id='another-boot')
                    else:
                        fact['function_id'] = 'expansion.upstream_probe'
                self.assert_unknown(self.run_k(normal, inspect=corrupt))

    def test_bad_backend_responses_go_through_core(self):
        original = StrictSkillReplayBackend.sample
        for defect in ('target', 'scope', 'malformed', 'timeout', 'expired'):
            with self.subTest(defect=defect):
                def broken(backend, function, arguments, context):
                    if defect == 'timeout':
                        raise TimeoutError('synthetic timeout')
                    result = original(backend, function, arguments, context)
                    observation, = copy.deepcopy(result.observations)
                    if defect == 'target':
                        observation['target'] = 'foreign'
                    elif defect == 'scope':
                        observation['scope'] = 'client'
                    elif defect == 'malformed':
                        observation['value'] = {'malformed': True}
                    else:
                        observation['age_s'] = observation['ttl_s'] + 1
                    return ToolResult(observations=(observation,))

                with patch.object(StrictSkillReplayBackend, 'sample', broken):
                    self.assert_unknown(self.run_k(self.scenarios['K07-normal']))

    def test_gold_is_scorer_only_and_embedded_labels_are_rejected(self):
        sim_dir, diagnostics = batch_paths('K')
        scenarios = sim_dir / 'scenarios.json'
        original = Path.read_text

        def forbid_gold(path, *args, **kwargs):
            self.assertNotIn('gold', path.name)
            return original(path, *args, **kwargs)

        with patch.object(Path, 'read_text', forbid_gold):
            for row in load_scenarios('K'):
                self.run_k(row)

        for path in (scenarios, diagnostics):
            with self.subTest(path=path.name):
                def inject_gold(candidate, *args, **kwargs):
                    data = original(candidate, *args, **kwargs)
                    if candidate != path:
                        return data
                    doc = json.loads(data)
                    if path == scenarios:
                        doc['scenarios'][0]['sources']['previous']['values']['expected_verdict'] = 'FAULT'
                    else:
                        doc['workflows']['K01']['expected_verdict'] = 'FAULT'
                    return json.dumps(doc)

                with patch.object(Path, 'read_text', inject_gold):
                    with self.assertRaisesRegex(SimulationError, 'gold-like key'):
                        load_scenarios('K')
