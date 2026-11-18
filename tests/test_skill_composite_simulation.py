"""WP-A4: no synthetic composite READs, full-source proof or UNKNOWN."""
import copy
import unittest
from dataclasses import replace
from unittest.mock import patch

from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.skill_expansion.composite import assess, contracts, load_scenarios
from gateway_pilot.skill_expansion.replay_backend import StrictSkillReplayBackend
from scripts.simulate_composites import evaluate, run_scenario


class CompositeSimulationTests(unittest.TestCase):
    def normal(self, sid):
        return next(copy.deepcopy(r) for r in load_scenarios() if r['id'] == sid + '-normal')

    def test_nine_scenarios_and_original_proof_ids(self):
        report = evaluate()
        self.assertEqual((report['total'], report['passed']), (9, 9))
        for sid in ('A03', 'A05', 'A07'):
            with self.subTest(skill=sid):
                captured = {}
                result = run_scenario(self.normal(sid), inspect=lambda sources: captured.update(sources))
                specs = contracts()['workflows'][sid]['sources']
                ids = {source.state.fact(specs[alias]['function_id'])['id']
                       for alias, source in captured.items()}
                self.assertEqual(len(ids), 2)
                for claim in result['claims'].values():
                    if claim['value'] == 'TRUE':
                        self.assertEqual(set(claim['evidence']), ids)
                self.assertEqual(result['core_calls'], 2 if sid == 'A07' else 3)
                # Only the already-existing measurements and identity dependency.
                executed = {e['function_id'] for source in captured.values() for e in source.state.executed}
                self.assertLessEqual(executed, {s['function_id'] for s in specs.values()} |
                                     {'expansion.synthetic_client_identity'})

    def test_each_source_missing_even_when_other_reports_fault(self):
        for row in load_scenarios():
            if row['id'].endswith('missing'):
                continue
            for alias in row['sources']:
                with self.subTest(row=row['id'], missing=alias):
                    changed = copy.deepcopy(row)
                    changed['sources'][alias]['values'] = None
                    result = run_scenario(changed)
                    self.assertEqual(result['verdict'], 'UNKNOWN')
                    self.assertTrue(all(c['value'] == 'UNKNOWN' and not c['evidence']
                                        for c in result['claims'].values()))

    def test_each_source_revalidated_after_execution(self):
        for sid in ('A03', 'A05', 'A07'):
            specs = contracts()['workflows'][sid]['sources']
            for alias, spec in specs.items():
                for defect in ('target', 'scope', 'permission', 'schema', 'timeout', 'expired', 'environment'):
                    with self.subTest(skill=sid, source=alias, defect=defect):
                        def corrupt(sources):
                            state = sources[alias].state
                            fact = state.fact(spec['function_id'])
                            if defect == 'target': fact['target'] = 'foreign'
                            elif defect == 'scope': fact['scope'] = 'wrong'
                            elif defect == 'permission': state.permissions.clear()
                            elif defect == 'schema': fact['value'] = {}
                            elif defect == 'timeout': fact['status'] = 'TIMEOUT'
                            elif defect == 'expired': fact['age_s'] = fact['ttl_s'] + 1
                            else: state.set_environment(boot_id='foreign')
                        result = run_scenario(self.normal(sid), inspect=corrupt)
                        self.assertEqual(result['verdict'], 'UNKNOWN')
                        self.assertTrue(all(not c['evidence'] for c in result['claims'].values()))

    def test_backend_negative_responses_pass_through_core(self):
        original = StrictSkillReplayBackend.sample
        for sid in ('A03', 'A05', 'A07'):
            for defect in ('timeout', 'target', 'scope', 'schema', 'stale'):
                with self.subTest(skill=sid, defect=defect):
                    def broken(backend, function, arguments, context):
                        if defect == 'timeout':
                            raise TimeoutError('synthetic timeout')
                        result = original(backend, function, arguments, context)
                        rows = [copy.deepcopy(r) for r in result.observations]
                        for r in rows:
                            if defect == 'target': r['target'] = 'foreign'
                            elif defect == 'scope': r['scope'] = 'wrong'
                            elif defect == 'schema': r['value'] = {'malformed': True}
                            else: r['age_s'] = r['ttl_s'] + 1
                        return ToolResult(observations=tuple(rows))
                    with patch.object(StrictSkillReplayBackend, 'sample', broken):
                        result = run_scenario(self.normal(sid))
                    self.assertEqual(result['verdict'], 'UNKNOWN')

    def test_history_requires_distinct_ordered_matching_samples(self):
        for defect in ('equal_time', 'reverse_time', 'different_segment', 'duplicate', 'negative_count'):
            with self.subTest(defect=defect):
                row = self.normal('A07')
                if defect == 'equal_time': row['sources']['previous']['simulated_at'] = row['sources']['inventory']['simulated_at']
                elif defect == 'reverse_time': row['sources']['previous']['simulated_at'] = '2026-11-18T09:00:00Z'
                elif defect == 'different_segment': row['sources']['previous']['values']['segment'] = 'other'
                elif defect == 'negative_count': row['sources']['previous']['values']['devices_count'] = -1
                def inspect(sources):
                    if defect == 'duplicate':
                        sources['previous'] = replace(sources['inventory'], simulated_at='2026-11-18T08:00:00Z')
                self.assertEqual(run_scenario(row, inspect=inspect)['verdict'], 'UNKNOWN')

    def test_history_count_increase_and_zero_boundary(self):
        for previous, current, expected in [(0, 0, 'HEALTHY'), (0, 1, 'FAULT'), (1, 0, 'FAULT'), (3, 3, 'HEALTHY')]:
            with self.subTest(previous=previous, current=current):
                row = self.normal('A07')
                row['sources']['previous']['values']['devices_count'] = previous
                row['sources']['inventory']['values']['devices_count'] = current
                self.assertEqual(run_scenario(row)['verdict'], expected)

    def test_empty_known_vendor_is_unknown_no_device_type_inference(self):
        row = self.normal('A05')
        row['sources']['vendor']['values']['oui_vendor'] = ''
        self.assertEqual(run_scenario(row)['verdict'], 'UNKNOWN')
        row['sources']['vendor']['values']['oui_vendor'] = 'Another vendor'
        result = run_scenario(row)
        self.assertEqual(result['verdict'], 'HEALTHY')
        self.assertIn('does not prove device type', result['limitation'])

    def test_gold_never_read_by_execution(self):
        from pathlib import Path
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            self.assertNotIn('gold', path.name)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            self.assertEqual(run_scenario(self.normal('A07'))['verdict'], 'HEALTHY')

    def test_foreign_source_rejected(self):
        def inspect(sources):
            sources['foreign'] = sources['inventory']
        self.assertEqual(run_scenario(self.normal('A03'), inspect=inspect)['verdict'], 'UNKNOWN')
