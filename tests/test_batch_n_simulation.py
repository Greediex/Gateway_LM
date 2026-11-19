"""COV-N direct READ simulations for snapshot, drift and rollback readback."""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_n_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_n.diagnostics.json'
SKILLS = ('N03', 'N04', 'N07')

BOUNDARIES = [
    ('N03', {'snapshot_available': True, 'configuration_revision': 'r'}, 'HEALTHY'),
    ('N03', {'snapshot_available': False, 'configuration_revision': ''}, 'FAULT'),
    ('N03', {'snapshot_available': True, 'configuration_revision': ''}, 'UNKNOWN'),
    ('N03', {'snapshot_available': False, 'configuration_revision': 'r'}, 'UNKNOWN'),
    ('N04', {'drift_count': -1}, 'UNKNOWN'),
    ('N04', {'drift_count': 0}, 'HEALTHY'),
    ('N04', {'drift_count': 1}, 'FAULT'),
    ('N07', {'expected_match': True}, 'HEALTHY'),
    ('N07', {'expected_match': False}, 'FAULT'),
]

BAD = [
    ('N03', {'snapshot_available': 1, 'configuration_revision': 'r'}),
    ('N03', {'snapshot_available': True, 'configuration_revision': 1}),
    ('N03', {'snapshot_available': True}),
    ('N04', {'drift_count': '0'}),
    ('N04', {'drift_count': True}),
    ('N04', {'drift_count': 0.5}),
    ('N07', {'expected_match': 0}),
    ('N07', {'expected_match': 'false'}),
    ('N07', {'expected_match': None}),
]


class BatchNTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
