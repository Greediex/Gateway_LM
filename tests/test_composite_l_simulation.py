"""Synthetic site service counters and two-gateway reachability screening."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeLSimulationTests(unittest.TestCase):
    def scenario(self, skill, case='fault'):
        return next(row for row in load_scenarios('L') if row['id'] == f'{skill}-{case}')

    def assert_unknown(self, row, **kwargs):
        result = run_scenario(row, batch='L', **kwargs)
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertEqual(len(result['claims']), 2)
        for claim in result['claims'].values():
            self.assertEqual((claim['value'], claim['evidence']), ('UNKNOWN', []))

    def test_exact_scenarios_and_core_provenance(self):
        report = evaluate('L')
        self.assertEqual((report['total'], report['passed']), (6, 6))
        expected = {'normal': 'HEALTHY', 'fault': 'FAULT', 'missing': 'UNKNOWN'}
        self.assertEqual({row['id']: row['verdict'] for row in report['rows']}, {
            f'{skill}-{case}': verdict for skill in ('L06', 'L07')
            for case, verdict in expected.items()
        })
        doc = contracts('L')
        self.assertEqual(set(doc['workflows']), {'L06', 'L07'})
        for skill, claim_source in (('L06', 'services'), ('L07', 'links')):
            workflow = doc['workflows'][skill]
            self.assertTrue(workflow['limitation'].strip())
            for case in ('normal', 'fault'):
                with self.subTest(skill=skill, case=case):
                    captured = {}
                    result = run_scenario(self.scenario(skill, case), batch='L', inspect=captured.update)
                    self.assertEqual(result['verdict'], expected[case])
                    self.assertEqual(result['core_calls'], len(workflow['sources']))
                    self.assertEqual(result['source_errors'], {})
                    proof_ids = {
                        alias: captured[alias].state.fact(spec['function_id'])['id']
                        for alias, spec in workflow['sources'].items()
                    }
                    self.assertEqual(len(set(proof_ids.values())), len(workflow['sources']))
                    self.assertEqual(
                        [(claim['severity'], claim['evidence']) for claim in result['claims'].values()
                         if claim['value'] == 'TRUE'],
                        [(expected[case], [proof_ids[claim_source]])],
                    )
        for claim in doc['claims']:
            self.assertTrue(claim['claim_id'].endswith('_v1'))
            self.assertEqual(claim['excludes'], [])
            predicate, = claim['requires']
            observed = ('services', 'failed_services', 1) if claim['workflow'].startswith('REPLAY-L06') else (
                'links', 'reachable_gateways', 2)
            self.assertEqual((predicate['port'], predicate['field'], predicate['value']), observed)
            self.assertIs(type(predicate['value']), int)

    def test_boundary_table(self):
        for skill, alias, changes, verdict in (
            ('L06', 'services', {'running_services': 1, 'failed_services': 0}, 'HEALTHY'),
            ('L06', 'services', {'running_services': 0, 'failed_services': 1}, 'FAULT'),
            ('L06', 'services', {'running_services': 0, 'failed_services': 0}, 'UNKNOWN'),
            ('L06', 'services', {'running_services': -1}, 'UNKNOWN'),
            ('L06', 'services', {'failed_services': -1}, 'UNKNOWN'),
            ('L06', 'topology', {'node_count': -1}, 'UNKNOWN'),
            ('L06', 'topology', {'node_count': 1}, 'UNKNOWN'),
            ('L06', 'topology', {'edge_count': -1}, 'UNKNOWN'),
            ('L06', 'topology', {'edge_count': 0}, 'UNKNOWN'),
            ('L06', 'topology', {'node_count': 2, 'edge_count': 1}, 'FAULT'),
            ('L06', 'wan', {'observation_window_s': -1}, 'UNKNOWN'),
            ('L06', 'wan', {'observation_window_s': 0}, 'UNKNOWN'),
            ('L06', 'wan', {'observation_window_s': 1}, 'FAULT'),
            ('L06', 'wan', {'disconnect_events': -1}, 'UNKNOWN'),
            ('L06', 'wan', {'disconnect_events': 1}, 'UNKNOWN'),
            ('L07', 'links', {'known_gateways': -1}, 'UNKNOWN'),
            ('L07', 'links', {'known_gateways': 1}, 'UNKNOWN'),
            ('L07', 'links', {'known_gateways': 3}, 'UNKNOWN'),
            ('L07', 'links', {'reachable_gateways': -1}, 'UNKNOWN'),
            ('L07', 'links', {'reachable_gateways': 0}, 'UNKNOWN'),
            ('L07', 'links', {'reachable_gateways': 1}, 'FAULT'),
            ('L07', 'links', {'reachable_gateways': 2}, 'HEALTHY'),
            ('L07', 'links', {'reachable_gateways': 3}, 'UNKNOWN'),
            ('L07', 'upstream', {'loss_pct': -0.01}, 'UNKNOWN'),
            ('L07', 'upstream', {'loss_pct': 0}, 'FAULT'),
            ('L07', 'upstream', {'loss_pct': 99.99}, 'FAULT'),
            ('L07', 'upstream', {'loss_pct': 100}, 'UNKNOWN'),
            ('L07', 'upstream', {'loss_pct': 100.01}, 'UNKNOWN'),
            ('L07', 'upstream', {'reachable': False}, 'UNKNOWN'),
        ):
            with self.subTest(skill=skill, source=alias, changes=changes):
                row = self.scenario(skill)
                row['sources'][alias]['values'].update(changes)
                if verdict == 'UNKNOWN':
                    self.assert_unknown(row)
                else:
                    self.assertEqual(run_scenario(row, batch='L')['verdict'], verdict)

    def test_invalid_types_and_nonfinite_values(self):
        for skill, workflow in contracts('L')['workflows'].items():
            for alias, source in workflow['sources'].items():
                for field, schema in source['value_schema']['properties'].items():
                    invalid_values = {
                        'boolean': (1, 'true', None, []),
                        'integer': ('1', True, None, 0.5, [], {}),
                        'number': ('1', True, None, {}, float('nan'), float('inf'), float('-inf')),
                    }[schema['type']]
                    for invalid in invalid_values:
                        with self.subTest(skill=skill, source=alias, field=field, invalid=invalid):
                            row = self.scenario(skill)
                            row['sources'][alias]['values'][field] = invalid
                            self.assert_unknown(row)

    def test_missing_malformed_and_unaligned_sources(self):
        for skill, workflow in contracts('L')['workflows'].items():
            for alias in workflow['sources']:
                for values in (None, {}):
                    with self.subTest(skill=skill, source=alias, values=values):
                        row = self.scenario(skill)
                        row['sources'][alias]['values'] = values
                        self.assert_unknown(row)
                with self.subTest(skill=skill, source=alias, defect='missing Core state'):
                    self.assert_unknown(self.scenario(skill), inspect=lambda sources: sources.pop(alias))
                with self.subTest(skill=skill, source=alias, defect='different sample time'):
                    row = self.scenario(skill)
                    row['sources'][alias]['simulated_at'] = '2026-11-19T08:00:01Z'
                    self.assert_unknown(row)

    def test_unusable_verified_context_blocks_claim(self):
        for defect in ('target', 'scope', 'permission', 'timeout', 'stale'):
            with self.subTest(defect=defect):
                def corrupt(sources):
                    state = sources['wan'].state
                    fact = state.fact('expansion.wan_events')
                    if defect == 'permission':
                        state.permissions.clear()
                    elif defect == 'stale':
                        fact['age_s'] = fact['ttl_s']
                    elif defect == 'timeout':
                        fact['status'] = 'TIMEOUT'
                    else:
                        fact[defect] = 'foreign'

                self.assert_unknown(self.scenario('L06'), inspect=corrupt)

    def test_gold_is_scorer_only_and_rejected_in_inputs(self):
        original = Path.read_text

        def no_gold(path, *args, **kwargs):
            self.assertNotEqual(path.name, 'gold.json')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'read_text', no_gold):
            for skill in ('L06', 'L07'):
                self.assertEqual(run_scenario(self.scenario(skill, 'normal'), batch='L')['verdict'], 'HEALTHY')

        sim_dir, diagnostics = batch_paths('L')
        for target, loader, keys in (
            (sim_dir / 'scenarios.json', load_scenarios, ('scenarios', 0, 'sources', 'wan', 'values')),
            (diagnostics, contracts, ('workflows', 'L06')),
            (diagnostics, contracts, ('workflows', 'L06', 'sources', 'wan', 'value_schema', 'properties')),
        ):
            with self.subTest(target=target.name, keys=keys):
                def inject_gold(path, *args, **kwargs):
                    content = original(path, *args, **kwargs)
                    if path != target:
                        return content
                    doc = json.loads(content)
                    container = doc
                    for key in keys:
                        container = container[key]
                    container['expected_verdict'] = 'HEALTHY'
                    return json.dumps(doc)

                with patch.object(Path, 'read_text', inject_gold):
                    with self.assertRaisesRegex(SimulationError, 'gold-like'):
                        loader('L')
