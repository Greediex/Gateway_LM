"""COV-D (IP, DHCP & IPv6) direct Skills D02/D03/D05/D06/D07: boundaries and negative paths.

Thresholds are declared synthetic heuristics in replay_d.diagnostics.json, not
calibrated values. D04/D08 (composite) and SK03 (legacy) are not covered here.
"""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_d_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_d.diagnostics.json'
SKILLS = ('D02', 'D03', 'D05', 'D06', 'D07')

# (skill, values, expected verdict). Edges follow the declared Claim thresholds.
BOUNDARIES = [
    ('D02', {'free_addresses': 0, 'used_addresses': 0}, 'FAULT'),        # exhausted
    ('D02', {'free_addresses': 1, 'used_addresses': 10}, 'FAULT'),       # low
    ('D02', {'free_addresses': 5, 'used_addresses': 10}, 'FAULT'),
    ('D02', {'free_addresses': 6, 'used_addresses': 10}, 'HEALTHY'),
    ('D02', {'free_addresses': -1, 'used_addresses': 10}, 'UNKNOWN'),
    ('D02', {'free_addresses': 50, 'used_addresses': -1}, 'UNKNOWN'),
    ('D03', {'active_leases': 10, 'expired_leases': 0}, 'HEALTHY'),
    ('D03', {'active_leases': 10, 'expired_leases': 20}, 'HEALTHY'),
    ('D03', {'active_leases': 10, 'expired_leases': 21}, 'FAULT'),
    ('D03', {'active_leases': 10, 'expired_leases': -1}, 'UNKNOWN'),
    ('D03', {'active_leases': -1, 'expired_leases': 3}, 'UNKNOWN'),
    ('D05', {'neighbor_count': 12, 'failed_entries': 0}, 'HEALTHY'),
    ('D05', {'neighbor_count': 12, 'failed_entries': 3}, 'HEALTHY'),
    ('D05', {'neighbor_count': 12, 'failed_entries': 4}, 'FAULT'),
    ('D05', {'neighbor_count': 12, 'failed_entries': -1}, 'UNKNOWN'),
    ('D05', {'neighbor_count': -1, 'failed_entries': 0}, 'UNKNOWN'),
    ('D06', {'router_advertisements': True, 'prefix_count': 1}, 'HEALTHY'),
    ('D06', {'router_advertisements': True, 'prefix_count': 0}, 'FAULT'),   # RA but no prefix
    ('D06', {'router_advertisements': False, 'prefix_count': 0}, 'FAULT'),
    ('D06', {'router_advertisements': False, 'prefix_count': 3}, 'FAULT'),  # no RA even with prefixes
    ('D06', {'router_advertisements': True, 'prefix_count': -1}, 'UNKNOWN'),
    ('D07', {'server_enabled': True, 'leases_count': 0}, 'HEALTHY'),
    ('D07', {'server_enabled': False, 'leases_count': 5}, 'FAULT'),
    ('D07', {'server_enabled': True, 'leases_count': -1}, 'UNKNOWN'),
]

BAD = [('D02', {'free_addresses': '5', 'used_addresses': 1}),
       ('D03', {'active_leases': None, 'expired_leases': 1}),
       ('D05', {'neighbor_count': 2.5, 'failed_entries': 0}),
       ('D06', {'router_advertisements': 'true', 'prefix_count': 1}),
       ('D07', {'server_enabled': True}),
       ('D02', {'free_addresses': 1, 'used_addresses': 1, 'extra': 1})]


class BatchDTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
