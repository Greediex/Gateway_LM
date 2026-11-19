"""COV-J VPN snapshot Claims: boundaries, insufficient evidence and malformed data."""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_j_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_j.diagnostics.json'
SKILLS = ('J01', 'J02', 'J04', 'J06', 'J07', 'J08')

BOUNDARIES = [
    ('J01', {'tunnel_up': True, 'peer_count': 1}, 'HEALTHY'),
    ('J01', {'tunnel_up': False, 'peer_count': 1}, 'FAULT'),
    ('J01', {'tunnel_up': True, 'peer_count': 0}, 'UNKNOWN'),
    ('J01', {'tunnel_up': False, 'peer_count': 0}, 'UNKNOWN'),
    ('J01', {'tunnel_up': True, 'peer_count': -1}, 'UNKNOWN'),
    ('J01', {'tunnel_up': False, 'peer_count': -1}, 'UNKNOWN'),
    ('J02', {'expected_routes': 1, 'missing_routes': 0}, 'HEALTHY'),
    ('J02', {'expected_routes': 1, 'missing_routes': 1}, 'FAULT'),
    ('J02', {'expected_routes': 0, 'missing_routes': 0}, 'UNKNOWN'),
    ('J02', {'expected_routes': 0, 'missing_routes': 1}, 'UNKNOWN'),
    ('J02', {'expected_routes': 1, 'missing_routes': 2}, 'UNKNOWN'),
    ('J02', {'expected_routes': 3, 'missing_routes': 2}, 'UNKNOWN'),
    ('J02', {'expected_routes': -1, 'missing_routes': 1}, 'UNKNOWN'),
    ('J02', {'expected_routes': 1, 'missing_routes': -1}, 'UNKNOWN'),
    ('J04', {'peers_reachable': 1, 'peers_unreachable': 0}, 'HEALTHY'),
    ('J04', {'peers_reachable': 0, 'peers_unreachable': 1}, 'FAULT'),
    ('J04', {'peers_reachable': 0, 'peers_unreachable': 0}, 'UNKNOWN'),
    ('J04', {'peers_reachable': -1, 'peers_unreachable': 1}, 'UNKNOWN'),
    ('J04', {'peers_reachable': 1, 'peers_unreachable': -1}, 'UNKNOWN'),
    ('J06', {'ipv6_enabled': True, 'route_present': True}, 'HEALTHY'),
    ('J06', {'ipv6_enabled': True, 'route_present': False}, 'FAULT'),
    ('J06', {'ipv6_enabled': False, 'route_present': True}, 'UNKNOWN'),
    ('J06', {'ipv6_enabled': False, 'route_present': False}, 'UNKNOWN'),
    ('J07', {'routing_rules': 1, 'unresolved_rules': 0}, 'HEALTHY'),
    ('J07', {'routing_rules': 1, 'unresolved_rules': 1}, 'FAULT'),
    ('J07', {'routing_rules': 0, 'unresolved_rules': 0}, 'UNKNOWN'),
    ('J07', {'routing_rules': 0, 'unresolved_rules': 1}, 'UNKNOWN'),
    ('J07', {'routing_rules': 1, 'unresolved_rules': 2}, 'UNKNOWN'),
    ('J07', {'routing_rules': 3, 'unresolved_rules': 2}, 'UNKNOWN'),
    ('J07', {'routing_rules': -1, 'unresolved_rules': 1}, 'UNKNOWN'),
    ('J07', {'routing_rules': 1, 'unresolved_rules': -1}, 'UNKNOWN'),
    ('J08', {'service_enabled': True, 'connections': 1}, 'HEALTHY'),
    ('J08', {'service_enabled': False, 'connections': 0}, 'FAULT'),
    ('J08', {'service_enabled': True, 'connections': 0}, 'UNKNOWN'),
    ('J08', {'service_enabled': False, 'connections': 1}, 'UNKNOWN'),
    ('J08', {'service_enabled': True, 'connections': -1}, 'UNKNOWN'),
    ('J08', {'service_enabled': False, 'connections': -1}, 'UNKNOWN'),
]

BAD = [
    ('J01', {'tunnel_up': 'up', 'peer_count': 1}),
    ('J01', {'tunnel_up': True, 'peer_count': True}),
    ('J02', {'expected_routes': 1, 'missing_routes': 0.5}),
    ('J04', {'peers_reachable': '1', 'peers_unreachable': 0}),
    ('J06', {'ipv6_enabled': 1, 'route_present': True}),
    ('J06', {'ipv6_enabled': True, 'route_present': None}),
    ('J07', {'routing_rules': 1, 'unresolved_rules': False}),
    ('J08', {'service_enabled': True, 'connections': '1'}),
]


class BatchJTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
