"""WP-A1: declared Claims over real synthetic Core state, including proof rejection."""
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.skill_expansion.simulation import SimulationError, load_scenarios
from scripts.core_replay_smoke_v2 import smoke
from scripts.simulate_skills import assess_claims, evaluate, load_claim_gold, run_scenario


class ClaimSimulationTests(unittest.TestCase):
    def test_twelve_scenarios_have_claim_proof_or_unknown(self):
        report = evaluate()
        self.assertEqual((report['total'], report['passed']), (12, 12))
        for row in report['rows']:
            with self.subTest(row=row['id']):
                expected = {'normal': 'HEALTHY', 'fault': 'FAULT', 'missing': 'UNKNOWN'}[row['id'].split('-')[1]]
                self.assertEqual(row['verdict'], expected)
                true = [c for c in row['claims'].values() if c['value'] == 'TRUE']
                if expected == 'UNKNOWN':
                    self.assertFalse(true)
                    self.assertNotIn('evidence_id', row)
                else:
                    self.assertTrue(true)
                    self.assertTrue(all(c['evidence'] == [row['evidence_id']] for c in true))

    def test_inventory_boundary_zero_and_one(self):
        sc = load_scenarios()[0]
        for count, verdict in [(0, 'FAULT'), (1, 'HEALTHY')]:
            with self.subTest(count=count):
                result = run_scenario(replace(sc, values={**sc.values, 'devices_count': count}))
                self.assertEqual(result['verdict'], verdict)

    def test_identity_boolean_combinations(self):
        sc = next(s for s in load_scenarios() if s.id == 'A06-normal')
        for consistent in (False, True):
            for conflict in (False, True):
                with self.subTest(consistent=consistent, conflict=conflict):
                    result = run_scenario(replace(sc, values={'ip_mac_consistent': consistent,
                                                            'hostname_conflict': conflict}))
                    self.assertEqual(result['verdict'], 'HEALTHY' if consistent and not conflict else 'FAULT')

    def test_invalid_evidence_cannot_support_any_claim(self):
        # Exercise existing CaseState admission gates, for both target scopes.
        for sc in (s for s in load_scenarios() if s.state == 'normal'):
            for defect in ('target', 'scope', 'permission', 'schema', 'timeout', 'expired'):
                with self.subTest(skill=sc.skill_id, defect=defect):
                    def assess(state):
                        fact = state.fact(sc.function_id)
                        self.assertIsNotNone(fact)
                        if defect == 'target':
                            fact['target'] = 'foreign-target'
                        elif defect == 'scope':
                            fact['scope'] = 'client' if fact['scope'] == 'gateway' else 'gateway'
                        elif defect == 'permission':
                            state.permissions.clear()
                        elif defect == 'schema':
                            fact['value'] = {'malformed': True}
                        elif defect == 'timeout':
                            fact['status'] = 'TIMEOUT'
                        else:
                            fact['age_s'] = fact['ttl_s'] + 1
                        result = assess_claims(state, sc.skill_id)
                        self.assertEqual(result['verdict'], 'UNKNOWN')
                        self.assertTrue(all(c['value'] == 'UNKNOWN' and not c['evidence']
                                            for c in result['claims'].values()))
                        return result
                    smoke(sc.function_id, values=sc.values, assess=assess)

    def test_ttl_boundary_on_core_clock(self):
        sc = load_scenarios()[0]
        def assess(state):
            fact = state.fact(sc.function_id)
            expires = fact['_received_at'] + fact['ttl_s'] - fact.get('age_s', 0)
            state.clock = lambda: expires
            self.assertEqual(assess_claims(state, sc.skill_id)['verdict'], 'HEALTHY')
            state.clock = lambda: expires + 0.001
            self.assertEqual(assess_claims(state, sc.skill_id)['verdict'], 'UNKNOWN')
            return {}
        smoke(sc.function_id, values=sc.values, assess=assess)

    def test_gold_is_not_read_during_execution(self):
        with patch('scripts.simulate_skills.load_claim_gold', side_effect=AssertionError('gold read')):
            self.assertEqual(run_scenario(load_scenarios()[0])['verdict'], 'HEALTHY')

    def test_invalid_gold_rejected(self):
        scenarios = load_scenarios()
        base = {'format': 'gateway-lm.skill-simulation-claims-gold/v1', 'version': '1.0.0',
                'scenarios_version': '1.0.0', 'expected': load_claim_gold(scenarios)}
        for change in ({'version': '2.0.0'}, {'scenarios_version': '2.0.0'},
                       {'expected': {}}, {'expected': {s.id: 'RESOLVED' for s in scenarios}}):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp)
                (path / 'gold_claims_v1.json').write_text(json.dumps({**base, **change}))
                with self.assertRaises(SimulationError):
                    load_claim_gold(scenarios, path)
