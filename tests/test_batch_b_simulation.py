"""COV-B (Wi-Fi & RF) Claims: boundaries, out-of-range, malformed values, gold isolation.

Thresholds are declared synthetic heuristics in replay_b.diagnostics.json, not
calibrated values. The 21 shared scenarios cover normal/fault/missing; the
boundary table below covers the exact edges.
"""
import unittest
from dataclasses import replace
from unittest.mock import patch

from gateway_pilot.skill_expansion.replay_backend import ReplayFixtureError
from gateway_pilot.skill_expansion.simulation import load_scenarios
from scripts.simulate_skills import ROOT, evaluate, run_scenario

SIM = ROOT / 'data/skill_expansion_v1/simulation_b_v1'
DIAG = ROOT / 'config/skill_launcher/replay_b.diagnostics.json'
SKILLS = ('B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08')

# (skill, values, expected verdict). Edges follow the declared Claim thresholds.
BOUNDARIES = [
    ('B02', {'radio_up': True, 'channel': 36, 'band': '5GHz'}, 'HEALTHY'),
    ('B02', {'radio_up': False, 'channel': 0, 'band': ''}, 'FAULT'),
    ('B03', {'ssid_present': True, 'ssid': 'HomeNet'}, 'HEALTHY'),
    ('B03', {'ssid_present': False, 'ssid': ''}, 'FAULT'),
    ('B04', {'rssi_dbm': -75.0, 'snr_db': 20.0}, 'HEALTHY'),   # exactly on both limits
    ('B04', {'rssi_dbm': -75.1, 'snr_db': 20.0}, 'FAULT'),
    ('B04', {'rssi_dbm': -60.0, 'snr_db': 19.9}, 'FAULT'),     # strong RSSI, poor SNR
    ('B05', {'channel_utilization_pct': 0.0}, 'HEALTHY'),
    ('B05', {'channel_utilization_pct': 70.0}, 'HEALTHY'),
    ('B05', {'channel_utilization_pct': 70.1}, 'FAULT'),
    ('B05', {'channel_utilization_pct': 100.0}, 'FAULT'),
    ('B05', {'channel_utilization_pct': 100.1}, 'UNKNOWN'),    # impossible percentage
    ('B05', {'channel_utilization_pct': -1.0}, 'UNKNOWN'),
    ('B06', {'channel': 36, 'neighbor_bss_count': 0}, 'HEALTHY'),
    ('B06', {'channel': 36, 'neighbor_bss_count': 5}, 'HEALTHY'),
    ('B06', {'channel': 36, 'neighbor_bss_count': 6}, 'FAULT'),
    ('B06', {'channel': 36, 'neighbor_bss_count': -1}, 'UNKNOWN'),
    ('B07', {'roam_count': 0, 'last_ap_id': 'a'}, 'HEALTHY'),
    ('B07', {'roam_count': 10, 'last_ap_id': 'a'}, 'HEALTHY'),
    ('B07', {'roam_count': 11, 'last_ap_id': 'a'}, 'FAULT'),
    ('B07', {'roam_count': -1, 'last_ap_id': 'a'}, 'UNKNOWN'),
    ('B08', {'backhaul_up': True, 'link_quality_pct': 50.0}, 'HEALTHY'),
    ('B08', {'backhaul_up': True, 'link_quality_pct': 49.9}, 'FAULT'),
    ('B08', {'backhaul_up': True, 'link_quality_pct': 100.0}, 'HEALTHY'),
    ('B08', {'backhaul_up': True, 'link_quality_pct': 100.1}, 'UNKNOWN'),
    ('B08', {'backhaul_up': True, 'link_quality_pct': -1.0}, 'UNKNOWN'),
    ('B08', {'backhaul_up': False, 'link_quality_pct': 90.0}, 'FAULT'),  # down wins over quality
]


class BatchBTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.scenarios = {s.id: s for s in load_scenarios(SIM)}

    def run_values(self, skill, values):
        return run_scenario(replace(self.scenarios[f'{skill}-normal'], values=values), DIAG)

    def test_all_seven_skills_have_three_states_and_pass_through_core(self):
        report = evaluate(SIM, DIAG)
        self.assertEqual((report['passed'], report['total']), (21, 21))
        for skill in SKILLS:
            self.assertEqual({s.state for s in self.scenarios.values() if s.skill_id == skill},
                             {'normal', 'fault', 'missing'}, skill)
        for row in report['rows']:
            if row['id'].endswith('-missing'):
                self.assertEqual((row['outcome'], row['verdict']), ('NOT_READY', 'UNKNOWN'))
            else:
                self.assertEqual(row['outcome'], 'VERIFIED')
                self.assertTrue(row['core_calls'] > 0 and row['evidence_id'])

    def test_threshold_boundaries_and_out_of_range_values(self):
        for skill, values, expected in BOUNDARIES:
            with self.subTest(skill=skill, values=values):
                result = self.run_values(skill, values)
                self.assertEqual(result['verdict'], expected)
                if expected == 'UNKNOWN':
                    # Out-of-range proof is admitted as evidence but supports no Claim.
                    self.assertFalse([c for c in result['claims'].values() if c['value'] == 'TRUE'])

    def test_malformed_values_are_rejected_before_any_claim(self):
        bad = [('B02', {'radio_up': 'yes', 'channel': 36, 'band': '5GHz'}),
               ('B04', {'rssi_dbm': '-60', 'snr_db': 30.0}),
               ('B05', {'channel_utilization_pct': None}),
               ('B07', {'roam_count': 2.5, 'last_ap_id': 'a'}),
               ('B08', {'backhaul_up': True}),
               ('B06', {'channel': 36, 'neighbor_bss_count': 1, 'extra': 1})]
        for skill, values in bad:
            with self.subTest(skill=skill), self.assertRaises(ReplayFixtureError):
                self.run_values(skill, values)

    def test_gold_is_never_read_during_execution(self):
        with patch('scripts.simulate_skills.load_claim_gold', side_effect=AssertionError('gold read')), \
                patch('scripts.simulate_skills.load_gold', side_effect=AssertionError('gold read')):
            self.assertEqual(run_scenario(self.scenarios['B04-fault'], DIAG)['verdict'], 'FAULT')

    def test_missing_source_is_unknown_and_never_healthy(self):
        for skill in SKILLS:
            row = run_scenario(self.scenarios[f'{skill}-missing'], DIAG)
            self.assertEqual((row['outcome'], row['verdict'], row['claims']), ('NOT_READY', 'UNKNOWN', {}), skill)


if __name__ == '__main__':
    unittest.main()
