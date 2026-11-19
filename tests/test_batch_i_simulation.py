"""COV-I direct Skills scored against synthetic security policy predicates."""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_i_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_i.diagnostics.json'
SKILLS = ('I01', 'I02', 'I03', 'I04', 'I05', 'I06', 'I08')

BOUNDARIES = [
    ('I01', {'rules_count': 1, 'invalid_rules': 0}, 'HEALTHY'),
    ('I01', {'rules_count': 1, 'invalid_rules': 1}, 'FAULT'),
    ('I01', {'rules_count': 0, 'invalid_rules': 0}, 'UNKNOWN'),
    ('I01', {'rules_count': 0, 'invalid_rules': 1}, 'UNKNOWN'),
    ('I01', {'rules_count': -1, 'invalid_rules': 1}, 'UNKNOWN'),
    ('I01', {'rules_count': 1, 'invalid_rules': -1}, 'UNKNOWN'),
    ('I02', {'listening_services': 0, 'exposed_services': 0}, 'HEALTHY'),
    ('I02', {'listening_services': 1, 'exposed_services': 0}, 'HEALTHY'),
    ('I02', {'listening_services': 1, 'exposed_services': 1}, 'FAULT'),
    ('I02', {'listening_services': 0, 'exposed_services': 1}, 'UNKNOWN'),
    ('I02', {'listening_services': -1, 'exposed_services': 0}, 'UNKNOWN'),
    ('I02', {'listening_services': -1, 'exposed_services': 1}, 'UNKNOWN'),
    ('I02', {'listening_services': 1, 'exposed_services': -1}, 'UNKNOWN'),
    ('I03', {'enabled': True}, 'HEALTHY'),
    ('I03', {'enabled': False}, 'FAULT'),
    ('I04', {'auth_mode': 'wpa2', 'encryption_enabled': True}, 'HEALTHY'),
    ('I04', {'auth_mode': 'wpa3', 'encryption_enabled': True}, 'HEALTHY'),
    ('I04', {'auth_mode': 'open', 'encryption_enabled': False}, 'FAULT'),
    ('I04', {'auth_mode': 'open', 'encryption_enabled': True}, 'UNKNOWN'),
    ('I04', {'auth_mode': 'wpa2', 'encryption_enabled': False}, 'UNKNOWN'),
    ('I04', {'auth_mode': '', 'encryption_enabled': True}, 'UNKNOWN'),
    ('I04', {'auth_mode': 'demo', 'encryption_enabled': False}, 'UNKNOWN'),
    ('I05', {'remote_admin_enabled': False, 'mfa_configured': False}, 'HEALTHY'),
    ('I05', {'remote_admin_enabled': False, 'mfa_configured': True}, 'HEALTHY'),
    ('I05', {'remote_admin_enabled': True, 'mfa_configured': True}, 'UNKNOWN'),
    ('I05', {'remote_admin_enabled': True, 'mfa_configured': False}, 'FAULT'),
    ('I06', {'segments': 2, 'policy_violations': 0}, 'HEALTHY'),
    ('I06', {'segments': 2, 'policy_violations': 1}, 'FAULT'),
    ('I06', {'segments': 1, 'policy_violations': 0}, 'UNKNOWN'),
    ('I06', {'segments': 1, 'policy_violations': 1}, 'UNKNOWN'),
    ('I06', {'segments': 0, 'policy_violations': 0}, 'UNKNOWN'),
    ('I06', {'segments': -1, 'policy_violations': 1}, 'UNKNOWN'),
    ('I06', {'segments': 2, 'policy_violations': -1}, 'UNKNOWN'),
    ('I08', {'checks_passed': 1, 'checks_failed': 0}, 'HEALTHY'),
    ('I08', {'checks_passed': 0, 'checks_failed': 1}, 'FAULT'),
    ('I08', {'checks_passed': 1, 'checks_failed': 1}, 'FAULT'),
    ('I08', {'checks_passed': 0, 'checks_failed': 0}, 'UNKNOWN'),
    ('I08', {'checks_passed': -1, 'checks_failed': 1}, 'UNKNOWN'),
    ('I08', {'checks_passed': 1, 'checks_failed': -1}, 'UNKNOWN'),
]

BAD = [
    ('I01', {'rules_count': '1', 'invalid_rules': 0}),
    ('I01', {'rules_count': 1, 'invalid_rules': True}),
    ('I02', {'listening_services': 1, 'exposed_services': 0.5}),
    ('I03', {'enabled': 1}),
    ('I04', {'auth_mode': 2, 'encryption_enabled': True}),
    ('I04', {'auth_mode': 'wpa3', 'encryption_enabled': 'true'}),
    ('I05', {'remote_admin_enabled': False, 'mfa_configured': None}),
    ('I06', {'segments': '2', 'policy_violations': 0}),
    ('I08', {'checks_passed': 0, 'checks_failed': '1'}),
]


class BatchITests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
