"""COV-G (Performance & QoS) direct Skills G01/G02/G04/G05/G06/G07: boundaries, negative paths.

Thresholds are declared synthetic heuristics in replay_g.diagnostics.json, not
calibrated values. G03/G08 (composite) are not covered. A one-direction-only
counter (G04) cannot be judged from one sample and must be UNKNOWN.
"""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_g_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_g.diagnostics.json'
SKILLS = ('G01', 'G02', 'G04', 'G05', 'G06', 'G07')

# (skill, values, expected verdict). Edges follow the declared Claim thresholds.
BOUNDARIES = [
    ('G01', {'latency_ms': 0.0, 'packet_loss_pct': 0.0}, 'HEALTHY'),
    ('G01', {'latency_ms': 100.0, 'packet_loss_pct': 2.0}, 'HEALTHY'),   # exactly on both limits
    ('G01', {'latency_ms': 100.1, 'packet_loss_pct': 0.0}, 'FAULT'),
    ('G01', {'latency_ms': 10.0, 'packet_loss_pct': 2.1}, 'FAULT'),
    ('G01', {'latency_ms': 10.0, 'packet_loss_pct': 100.0}, 'FAULT'),
    ('G01', {'latency_ms': 10.0, 'packet_loss_pct': 100.1}, 'UNKNOWN'),  # impossible percentage
    ('G01', {'latency_ms': -1.0, 'packet_loss_pct': 0.0}, 'UNKNOWN'),
    ('G01', {'latency_ms': 10.0, 'packet_loss_pct': -1.0}, 'UNKNOWN'),
    ('G02', {'jitter_ms': 0.0}, 'HEALTHY'),
    ('G02', {'jitter_ms': 30.0}, 'HEALTHY'),
    ('G02', {'jitter_ms': 30.1}, 'FAULT'),
    ('G02', {'jitter_ms': -0.1}, 'UNKNOWN'),
    ('G04', {'rx_bytes': 1, 'tx_bytes': 1}, 'HEALTHY'),
    ('G04', {'rx_bytes': 0, 'tx_bytes': 0}, 'FAULT'),
    ('G04', {'rx_bytes': 100, 'tx_bytes': 0}, 'UNKNOWN'),    # one direction only: cannot judge
    ('G04', {'rx_bytes': 0, 'tx_bytes': 100}, 'UNKNOWN'),
    ('G04', {'rx_bytes': -1, 'tx_bytes': 5}, 'UNKNOWN'),
    ('G05', {'rx_mbps': 0.0, 'tx_mbps': 0.0}, 'HEALTHY'),
    ('G05', {'rx_mbps': 800.0, 'tx_mbps': 800.0}, 'HEALTHY'),
    ('G05', {'rx_mbps': 800.1, 'tx_mbps': 10.0}, 'FAULT'),
    ('G05', {'rx_mbps': 10.0, 'tx_mbps': 800.1}, 'FAULT'),
    ('G05', {'rx_mbps': -1.0, 'tx_mbps': 10.0}, 'UNKNOWN'),
    ('G05', {'rx_mbps': 900.0, 'tx_mbps': -1.0}, 'UNKNOWN'),   # a bad field voids the other's verdict
    ('G06', {'queue_delay_ms': 0.0}, 'HEALTHY'),
    ('G06', {'queue_delay_ms': 50.0}, 'HEALTHY'),
    ('G06', {'queue_delay_ms': 50.1}, 'FAULT'),
    ('G06', {'queue_delay_ms': -1.0}, 'UNKNOWN'),
    ('G07', {'sqm_enabled': True, 'configured_rate_mbps': 300.0}, 'HEALTHY'),
    ('G07', {'sqm_enabled': True, 'configured_rate_mbps': 0.0}, 'FAULT'),   # enabled with no rate
    ('G07', {'sqm_enabled': False, 'configured_rate_mbps': 0.0}, 'FAULT'),
    ('G07', {'sqm_enabled': False, 'configured_rate_mbps': 300.0}, 'FAULT'),
    ('G07', {'sqm_enabled': True, 'configured_rate_mbps': -5.0}, 'UNKNOWN'),
]

BAD = [('G01', {'latency_ms': '18', 'packet_loss_pct': 0.0}),
       ('G02', {'jitter_ms': None}),
       ('G04', {'rx_bytes': 1.5, 'tx_bytes': 1}),
       ('G05', {'rx_mbps': 10.0}),
       ('G06', {'queue_delay_ms': True, 'extra': 1}),
       ('G07', {'sqm_enabled': 'on', 'configured_rate_mbps': 300.0})]


class BatchGTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
