"""COV-F (DNS & Core Services) direct Skills F02-F08: boundaries and negative paths.

Thresholds are declared synthetic heuristics in replay_f.diagnostics.json, not
calibrated values. SK05 (legacy) is not covered. Cases that cannot be judged
from one sample (idle cache, DNSSEC off) must be UNKNOWN, never HEALTHY/FAULT.
"""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_f_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_f.diagnostics.json'
SKILLS = ('F02', 'F03', 'F04', 'F05', 'F06', 'F07', 'F08')

# (skill, values, expected verdict). Edges follow the declared Claim thresholds.
BOUNDARIES = [
    ('F02', {'resolver_count': 3, 'healthy_count': 3}, 'HEALTHY'),
    ('F02', {'resolver_count': 3, 'healthy_count': 1}, 'HEALTHY'),   # partial loss not detectable
    ('F02', {'resolver_count': 3, 'healthy_count': 0}, 'FAULT'),
    ('F02', {'resolver_count': 0, 'healthy_count': 0}, 'FAULT'),     # no resolver configured
    ('F02', {'resolver_count': -1, 'healthy_count': 0}, 'UNKNOWN'),
    ('F02', {'resolver_count': 2, 'healthy_count': -1}, 'UNKNOWN'),
    ('F03', {'cache_hits': 1, 'cache_misses': 5000}, 'HEALTHY'),
    ('F03', {'cache_hits': 0, 'cache_misses': 101}, 'FAULT'),
    ('F03', {'cache_hits': 0, 'cache_misses': 100}, 'UNKNOWN'),      # too little traffic to judge
    ('F03', {'cache_hits': 0, 'cache_misses': 0}, 'UNKNOWN'),
    ('F03', {'cache_hits': -1, 'cache_misses': 5}, 'UNKNOWN'),
    ('F04', {'zones': 0, 'conflicts': 0}, 'HEALTHY'),
    ('F04', {'zones': 2, 'conflicts': 1}, 'FAULT'),
    ('F04', {'zones': -1, 'conflicts': 0}, 'UNKNOWN'),
    ('F04', {'zones': 2, 'conflicts': -1}, 'UNKNOWN'),
    ('F05', {'resolver_option_present': True}, 'HEALTHY'),
    ('F05', {'resolver_option_present': False}, 'FAULT'),
    ('F06', {'dnssec_enabled': True, 'validation_failures': 0}, 'HEALTHY'),
    ('F06', {'dnssec_enabled': True, 'validation_failures': 1}, 'FAULT'),
    ('F06', {'dnssec_enabled': False, 'validation_failures': 0}, 'UNKNOWN'),  # off: nothing to judge
    ('F06', {'dnssec_enabled': False, 'validation_failures': 9}, 'UNKNOWN'),  # inconsistent sample
    ('F06', {'dnssec_enabled': True, 'validation_failures': -1}, 'UNKNOWN'),
    ('F07', {'dot_enabled': True, 'doh_enabled': False}, 'HEALTHY'),
    ('F07', {'dot_enabled': False, 'doh_enabled': True}, 'HEALTHY'),
    ('F07', {'dot_enabled': True, 'doh_enabled': True}, 'HEALTHY'),   # two HEALTHY Claims, one verdict
    ('F07', {'dot_enabled': False, 'doh_enabled': False}, 'FAULT'),
    ('F08', {'synchronized': True, 'offset_ms': 0.0}, 'HEALTHY'),
    ('F08', {'synchronized': True, 'offset_ms': 500.0}, 'HEALTHY'),
    ('F08', {'synchronized': True, 'offset_ms': -500.0}, 'HEALTHY'),
    ('F08', {'synchronized': True, 'offset_ms': 500.1}, 'FAULT'),
    ('F08', {'synchronized': True, 'offset_ms': -500.1}, 'FAULT'),
    ('F08', {'synchronized': False, 'offset_ms': 0.0}, 'FAULT'),
    ('F08', {'synchronized': False, 'offset_ms': 10.0}, 'FAULT'),     # unsynced wins over small offset
]

BAD = [('F02', {'resolver_count': '3', 'healthy_count': 3}),
       ('F03', {'cache_hits': None, 'cache_misses': 1}),
       ('F04', {'zones': 2.5, 'conflicts': 0}),
       ('F05', {'resolver_option_present': 'yes'}),
       ('F06', {'dnssec_enabled': True}),
       ('F07', {'dot_enabled': True, 'doh_enabled': False, 'extra': 1}),
       ('F08', {'synchronized': True, 'offset_ms': 'late'})]


class BatchFTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
