"""COV-C direct Skills: synthetic thresholds and insufficient evidence."""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_c_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_c.diagnostics.json'
SKILLS = ('C01', 'C02', 'C03', 'C04', 'C05', 'C07', 'C08')

# (skill, values, expected verdict)
BOUNDARIES = [
    ('C01', {'port_count': 4, 'active_count': -1}, 'UNKNOWN'),
    ('C01', {'port_count': 4, 'active_count': 0}, 'FAULT'),
    ('C01', {'port_count': 4, 'active_count': 1}, 'HEALTHY'),
    ('C01', {'port_count': 4, 'active_count': 4}, 'HEALTHY'),
    ('C01', {'port_count': 4, 'active_count': 5}, 'UNKNOWN'),
    ('C01', {'port_count': 0, 'active_count': 0}, 'UNKNOWN'),
    ('C01', {'port_count': -1, 'active_count': 1}, 'UNKNOWN'),
    ('C01', {'port_count': 3, 'active_count': 0}, 'UNKNOWN'),  # outside the four-port model
    ('C01', {'port_count': 5, 'active_count': 1}, 'UNKNOWN'),
    ('C02', {'rx_errors': 0, 'tx_errors': 0, 'link_mbps': -1}, 'UNKNOWN'),
    ('C02', {'rx_errors': 0, 'tx_errors': 0, 'link_mbps': 0}, 'FAULT'),
    ('C02', {'rx_errors': 0, 'tx_errors': 0, 'link_mbps': 1}, 'HEALTHY'),
    ('C02', {'rx_errors': 1, 'tx_errors': 0, 'link_mbps': 1000}, 'UNKNOWN'),
    ('C02', {'rx_errors': 0, 'tx_errors': 1, 'link_mbps': 1000}, 'UNKNOWN'),  # no error delta
    ('C02', {'rx_errors': -1, 'tx_errors': 0, 'link_mbps': 0}, 'UNKNOWN'),
    ('C02', {'rx_errors': 0, 'tx_errors': -1, 'link_mbps': 0}, 'UNKNOWN'),
    ('C02', {'rx_errors': -1, 'tx_errors': 0, 'link_mbps': 1000}, 'UNKNOWN'),
    ('C02', {'rx_errors': 0, 'tx_errors': -1, 'link_mbps': 1000}, 'UNKNOWN'),
    ('C03', {'mac_entries': -1}, 'UNKNOWN'),
    ('C03', {'mac_entries': 0}, 'UNKNOWN'),  # an idle network can have an empty FDB
    ('C03', {'mac_entries': 1}, 'HEALTHY'),
    ('C03', {'mac_entries': 1023}, 'HEALTHY'),
    ('C03', {'mac_entries': 1024}, 'FAULT'),
    ('C03', {'mac_entries': 1025}, 'UNKNOWN'),
    ('C04', {'bridge_up': True, 'member_ports': -1}, 'UNKNOWN'),
    ('C04', {'bridge_up': True, 'member_ports': 0}, 'UNKNOWN'),
    ('C04', {'bridge_up': True, 'member_ports': 1}, 'HEALTHY'),
    ('C04', {'bridge_up': False, 'member_ports': -1}, 'UNKNOWN'),
    ('C04', {'bridge_up': False, 'member_ports': 0}, 'UNKNOWN'),
    ('C04', {'bridge_up': False, 'member_ports': 1}, 'FAULT'),
    ('C05', {'vlan_count': -1, 'invalid_memberships': 0}, 'UNKNOWN'),
    ('C05', {'vlan_count': -1, 'invalid_memberships': 1}, 'UNKNOWN'),
    ('C05', {'vlan_count': 0, 'invalid_memberships': 0}, 'UNKNOWN'),
    ('C05', {'vlan_count': 0, 'invalid_memberships': 1}, 'UNKNOWN'),
    ('C05', {'vlan_count': 1, 'invalid_memberships': -1}, 'UNKNOWN'),
    ('C05', {'vlan_count': 1, 'invalid_memberships': 0}, 'HEALTHY'),
    ('C05', {'vlan_count': 1, 'invalid_memberships': 1}, 'FAULT'),
    ('C07', {'stp_enabled': True, 'topology_changes': -1}, 'UNKNOWN'),
    ('C07', {'stp_enabled': True, 'topology_changes': 0}, 'HEALTHY'),
    ('C07', {'stp_enabled': True, 'topology_changes': 1}, 'UNKNOWN'),  # no observation window
    ('C07', {'stp_enabled': False, 'topology_changes': -1}, 'UNKNOWN'),
    ('C07', {'stp_enabled': False, 'topology_changes': 0}, 'FAULT'),
    ('C08', {'mtu_bytes': -1, 'mismatch_detected': False}, 'UNKNOWN'),
    ('C08', {'mtu_bytes': -1, 'mismatch_detected': True}, 'UNKNOWN'),
    ('C08', {'mtu_bytes': 0, 'mismatch_detected': False}, 'UNKNOWN'),
    ('C08', {'mtu_bytes': 0, 'mismatch_detected': True}, 'UNKNOWN'),
    ('C08', {'mtu_bytes': 67, 'mismatch_detected': False}, 'UNKNOWN'),
    ('C08', {'mtu_bytes': 67, 'mismatch_detected': True}, 'UNKNOWN'),
    ('C08', {'mtu_bytes': 68, 'mismatch_detected': False}, 'HEALTHY'),
    ('C08', {'mtu_bytes': 68, 'mismatch_detected': True}, 'FAULT'),
    ('C08', {'mtu_bytes': 9216, 'mismatch_detected': False}, 'HEALTHY'),
    ('C08', {'mtu_bytes': 9216, 'mismatch_detected': True}, 'FAULT'),
    ('C08', {'mtu_bytes': 9217, 'mismatch_detected': False}, 'UNKNOWN'),
    ('C08', {'mtu_bytes': 9217, 'mismatch_detected': True}, 'UNKNOWN'),
]

BAD = [
    ('C01', {'port_count': 4, 'active_count': '1'}),
    ('C02', {'rx_errors': 0, 'tx_errors': None, 'link_mbps': 1000}),
    ('C03', {'mac_entries': 1.5}),
    ('C04', {'bridge_up': 'up', 'member_ports': 1}),
    ('C05', {'vlan_count': '1', 'invalid_memberships': 0}),
    ('C07', {'stp_enabled': True, 'topology_changes': '0'}),
    ('C08', {'mtu_bytes': 1500, 'mismatch_detected': 0}),
]


class BatchCTests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
