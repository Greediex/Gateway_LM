"""COV-L direct READ simulations for topology, associations, gateways and subnets."""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_l_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_l.diagnostics.json'
SKILLS = ('L01', 'L02', 'L03', 'L05')

BOUNDARIES = [
    ('L01', {'node_count': 2, 'edge_count': 1}, 'HEALTHY'),
    ('L01', {'node_count': 2, 'edge_count': 0}, 'FAULT'),
    ('L01', {'node_count': 1, 'edge_count': 0}, 'UNKNOWN'),
    ('L01', {'node_count': 1, 'edge_count': 1}, 'UNKNOWN'),
    ('L01', {'node_count': 0, 'edge_count': 0}, 'UNKNOWN'),
    ('L01', {'node_count': 0, 'edge_count': 1}, 'UNKNOWN'),
    ('L01', {'node_count': -1, 'edge_count': 1}, 'UNKNOWN'),
    ('L01', {'node_count': 2, 'edge_count': -1}, 'UNKNOWN'),
    ('L02', {'known_associations': 1, 'unresolved_clients': 0}, 'HEALTHY'),
    ('L02', {'known_associations': 1, 'unresolved_clients': 1}, 'FAULT'),
    ('L02', {'known_associations': 0, 'unresolved_clients': 1}, 'FAULT'),
    ('L02', {'known_associations': 0, 'unresolved_clients': 0}, 'UNKNOWN'),
    ('L02', {'known_associations': -1, 'unresolved_clients': 1}, 'UNKNOWN'),
    ('L02', {'known_associations': 1, 'unresolved_clients': -1}, 'UNKNOWN'),
    ('L03', {'known_gateways': 1, 'reachable_gateways': 1}, 'HEALTHY'),
    ('L03', {'known_gateways': 1, 'reachable_gateways': 0}, 'FAULT'),
    ('L03', {'known_gateways': 2, 'reachable_gateways': 0}, 'FAULT'),
    ('L03', {'known_gateways': 2, 'reachable_gateways': 1}, 'UNKNOWN'),
    ('L03', {'known_gateways': 2, 'reachable_gateways': 2}, 'UNKNOWN'),
    ('L03', {'known_gateways': 2, 'reachable_gateways': 3}, 'UNKNOWN'),
    ('L03', {'known_gateways': 1, 'reachable_gateways': 2}, 'UNKNOWN'),
    ('L03', {'known_gateways': 0, 'reachable_gateways': 0}, 'UNKNOWN'),
    ('L03', {'known_gateways': 0, 'reachable_gateways': 1}, 'UNKNOWN'),
    ('L03', {'known_gateways': -1, 'reachable_gateways': 0}, 'UNKNOWN'),
    ('L03', {'known_gateways': 1, 'reachable_gateways': -1}, 'UNKNOWN'),
    ('L05', {'subnet_count': 1, 'vlan_count': 1}, 'HEALTHY'),
    ('L05', {'subnet_count': 0, 'vlan_count': 1}, 'FAULT'),
    ('L05', {'subnet_count': 1, 'vlan_count': 0}, 'UNKNOWN'),
    ('L05', {'subnet_count': 0, 'vlan_count': 0}, 'UNKNOWN'),
    ('L05', {'subnet_count': -1, 'vlan_count': 1}, 'UNKNOWN'),
    ('L05', {'subnet_count': 1, 'vlan_count': -1}, 'UNKNOWN'),
]

BAD = [
    ('L01', {'node_count': '2', 'edge_count': 1}),
    ('L01', {'node_count': 2, 'edge_count': 1.5}),
    ('L02', {'known_associations': True, 'unresolved_clients': 0}),
    ('L02', {'known_associations': 1, 'unresolved_clients': None}),
    ('L03', {'known_gateways': [1], 'reachable_gateways': 1}),
    ('L03', {'known_gateways': 1, 'reachable_gateways': False}),
    ('L05', {'subnet_count': {}, 'vlan_count': 1}),
    ('L05', {'subnet_count': 1, 'vlan_count': '1'}),
]


class BatchLTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
