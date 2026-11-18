"""COV-B (Wi-Fi & RF) Claims: boundaries, out-of-range, malformed values, gold isolation.

Thresholds are declared synthetic heuristics in replay_b.diagnostics.json, not
calibrated values. The 21 shared scenarios cover normal/fault/missing; the
boundary table below covers the exact edges.
"""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_b_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_b.diagnostics.json'
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


BAD = [('B02', {'radio_up': 'yes', 'channel': 36, 'band': '5GHz'}),
       ('B04', {'rssi_dbm': '-60', 'snr_db': 30.0}),
       ('B05', {'channel_utilization_pct': None}),
       ('B07', {'roam_count': 2.5, 'last_ap_id': 'a'}),
       ('B08', {'backhaul_up': True}),
       ('B06', {'channel': 36, 'neighbor_bss_count': 1, 'extra': 1})]


class BatchBTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
