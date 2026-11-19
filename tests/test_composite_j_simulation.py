"""J05 VPN peer reachability screening using three verified Core sources."""

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.simulate_composites import evaluate, run_scenario


class CompositeJSimulationTests(unittest.TestCase):
    def scenario(self, case='fault'):
        return next(row for row in load_scenarios('J') if row['id'] == f'J05-{case}')

    def assert_unknown(self, row, **kwargs):
        result = run_scenario(row, batch='J', **kwargs)
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertEqual(len(result['claims']), 2)
        for claim in result['claims'].values():
            self.assertEqual((claim['value'], claim['evidence']), ('UNKNOWN', []))

    def test_exact_scenarios_and_verified_provenance(self):
        report = evaluate('J')
        self.assertEqual((report['total'], report['passed']), (3, 3))
        self.assertEqual({row['id']: row['verdict'] for row in report['rows']}, {
            'J05-normal': 'HEALTHY', 'J05-fault': 'FAULT', 'J05-missing': 'UNKNOWN',
        })
        doc = contracts('J')
        workflow = doc['workflows']['J05']
        self.assertTrue(workflow['limitation'].strip())
        for case, verdict in (('normal', 'HEALTHY'), ('fault', 'FAULT')):
            with self.subTest(case=case):
                captured = {}
                result = run_scenario(self.scenario(case), batch='J', inspect=captured.update)
                self.assertEqual(result['core_calls'], 3)
                self.assertEqual(result['source_errors'], {})
                proof_ids = {
                    alias: captured[alias].state.fact(spec['function_id'])['id']
                    for alias, spec in workflow['sources'].items()
                }
                self.assertEqual(len(set(proof_ids.values())), 3)
                self.assertEqual(
                    [(claim['severity'], claim['evidence']) for claim in result['claims'].values()
                     if claim['value'] == 'TRUE'],
                    [(verdict, [proof_ids['peers']])],
                )
        for claim in doc['claims']:
            self.assertTrue(claim['claim_id'].endswith('_v1'))
            self.assertEqual(claim['excludes'], [])
            predicate, = claim['requires']
            self.assertEqual((predicate['port'], predicate['field']), ('peers', 'peers_unreachable'))
            self.assertIs(type(predicate['value']), int)

    def test_boundary_table(self):
        for alias, values, verdict in (
            ('peers', {'peers_reachable': 1, 'peers_unreachable': 0}, 'HEALTHY'),
            ('peers', {'peers_reachable': 0, 'peers_unreachable': 1}, 'FAULT'),
            ('peers', {'peers_unreachable': 0}, 'UNKNOWN'),  # No peer result.
            ('peers', {'peers_reachable': 1}, 'UNKNOWN'),    # Two peer results.
            ('peers', {'peers_reachable': -1}, 'UNKNOWN'),
            ('peers', {'peers_reachable': 2}, 'UNKNOWN'),
            ('peers', {'peers_unreachable': -1}, 'UNKNOWN'),
            ('peers', {'peers_unreachable': 2}, 'UNKNOWN'),
            ('tunnel', {'tunnel_up': False}, 'UNKNOWN'),
            ('tunnel', {'peer_count': -1}, 'UNKNOWN'),
            ('tunnel', {'peer_count': 0}, 'UNKNOWN'),
            ('tunnel', {'peer_count': 2}, 'UNKNOWN'),
            ('routes', {'expected_routes': -1}, 'UNKNOWN'),
            ('routes', {'expected_routes': 0}, 'UNKNOWN'),
            ('routes', {'expected_routes': 1}, 'FAULT'),
            ('routes', {'missing_routes': -1}, 'UNKNOWN'),
            ('routes', {'missing_routes': 1}, 'UNKNOWN'),
        ):
            with self.subTest(source=alias, values=values):
                row = self.scenario()
                row['sources'][alias]['values'].update(values)
                if verdict == 'UNKNOWN':
                    self.assert_unknown(row)
                else:
                    self.assertEqual(run_scenario(row, batch='J')['verdict'], verdict)

    def test_wrong_types(self):
        for alias, field in (
            ('tunnel', 'peer_count'), ('routes', 'expected_routes'), ('routes', 'missing_routes'),
            ('peers', 'peers_reachable'), ('peers', 'peers_unreachable'),
        ):
            for invalid in ('1', True, None, 0.5, [], {}, float('nan'), float('inf')):
                with self.subTest(source=alias, field=field, invalid=invalid):
                    row = self.scenario()
                    row['sources'][alias]['values'][field] = invalid
                    self.assert_unknown(row)
        for invalid in (1, 'true', None, []):
            with self.subTest(tunnel_up=invalid):
                row = self.scenario()
                row['sources']['tunnel']['values']['tunnel_up'] = invalid
                self.assert_unknown(row)

    def test_missing_malformed_and_unaligned_sources(self):
        for alias in ('tunnel', 'routes', 'peers'):
            for values in (None, {}):
                with self.subTest(source=alias, values=values):
                    row = self.scenario()
                    row['sources'][alias]['values'] = values
                    self.assert_unknown(row)
            with self.subTest(source=alias, defect='missing Core state'):
                self.assert_unknown(self.scenario(), inspect=lambda sources: sources.pop(alias))
        row = self.scenario()
        row['sources']['routes']['simulated_at'] = '2026-11-19T08:00:01Z'
        self.assert_unknown(row)

    def test_rejects_unusable_verified_source(self):
        for defect in ('target', 'scope', 'permission', 'timeout', 'stale'):
            with self.subTest(defect=defect):
                def corrupt(sources):
                    state = sources['routes'].state
                    fact = state.fact('expansion.vpn_routes')
                    if defect == 'permission':
                        state.permissions.clear()
                    elif defect == 'stale':
                        fact['age_s'] = fact['ttl_s']
                    elif defect == 'timeout':
                        fact['status'] = 'TIMEOUT'
                    else:
                        fact[defect] = 'foreign'

                self.assert_unknown(self.scenario(), inspect=corrupt)

    def test_gold_is_scorer_only_and_rejected_in_scenarios_and_config(self):
        original = Path.read_text

        def no_gold(path, *args, **kwargs):
            self.assertNotEqual(path.name, 'gold.json')
            return original(path, *args, **kwargs)

        with patch.object(Path, 'read_text', no_gold):
            self.assertEqual(run_scenario(self.scenario('normal'), batch='J')['verdict'], 'HEALTHY')

        sim_dir, diagnostics = batch_paths('J')
        for target, loader, location in (
            (sim_dir / 'scenarios.json', load_scenarios, 'values'),
            (diagnostics, contracts, 'workflow'),
            (diagnostics, contracts, 'source schema'),
        ):
            with self.subTest(target=target.name, location=location):
                def inject_gold(path, *args, **kwargs):
                    content = original(path, *args, **kwargs)
                    if path != target:
                        return content
                    doc = json.loads(content)
                    if location == 'values':
                        container = doc['scenarios'][0]['sources']['routes']['values']
                    else:
                        container = doc['workflows']['J05']
                        if location == 'source schema':
                            container = container['sources']['routes']['value_schema']['properties']
                    container['expected_verdict'] = 'HEALTHY'
                    return json.dumps(doc)

                with patch.object(Path, 'read_text', inject_gold):
                    with self.assertRaisesRegex(SimulationError, 'gold-like'):
                        loader('J')
