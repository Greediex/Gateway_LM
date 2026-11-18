"""COV-E (WAN & Internet) direct Skills E02-E08: boundaries and negative paths.

Thresholds are declared synthetic heuristics in replay_e.diagnostics.json, not
calibrated values. SK04 (legacy) is not covered. Samples that cannot support a
verdict (link only just up, several default routes, short window, unknown
protocol) must be UNKNOWN, never HEALTHY/FAULT.
"""
import unittest

import tests.batch_sim_support as support

SIM = support.ROOT / 'data/skill_expansion_v1/simulation_e_v1'
DIAG = support.ROOT / 'config/skill_launcher/replay_e.diagnostics.json'
SKILLS = ('E02', 'E03', 'E04', 'E05', 'E06', 'E07', 'E08')

# (skill, values, expected verdict). Edges follow the declared Claim thresholds.
BOUNDARIES = [
    ('E02', {'link_up': True, 'uptime_seconds': 60}, 'HEALTHY'),
    ('E02', {'link_up': True, 'uptime_seconds': 59}, 'UNKNOWN'),      # too fresh to judge stability
    ('E02', {'link_up': False, 'uptime_seconds': 0}, 'FAULT'),
    ('E02', {'link_up': True, 'uptime_seconds': -1}, 'UNKNOWN'),
    ('E02', {'link_up': False, 'uptime_seconds': -1}, 'UNKNOWN'),
    ('E03', {'default_route': True, 'default_route_count': 1}, 'HEALTHY'),
    ('E03', {'default_route': False, 'default_route_count': 0}, 'FAULT'),
    ('E03', {'default_route': True, 'default_route_count': 2}, 'UNKNOWN'),   # may be multi-WAN
    ('E03', {'default_route': True, 'default_route_count': 0}, 'UNKNOWN'),   # inconsistent sample
    ('E03', {'default_route': False, 'default_route_count': 2}, 'UNKNOWN'),
    ('E04', {'protocol': 'pppoe', 'session_connected': True}, 'HEALTHY'),
    ('E04', {'protocol': 'dhcp', 'session_connected': True}, 'HEALTHY'),
    ('E04', {'protocol': 'static', 'session_connected': False}, 'FAULT'),
    ('E04', {'protocol': 'l2tp', 'session_connected': True}, 'UNKNOWN'),     # protocol not modeled
    ('E04', {'protocol': '', 'session_connected': False}, 'UNKNOWN'),
    ('E05', {'nat_enabled': True, 'cgnat_suspected': False}, 'HEALTHY'),
    ('E05', {'nat_enabled': True, 'cgnat_suspected': True}, 'FAULT'),
    ('E05', {'nat_enabled': False, 'cgnat_suspected': False}, 'FAULT'),
    ('E05', {'nat_enabled': False, 'cgnat_suspected': True}, 'FAULT'),
    ('E06', {'uplinks': 2, 'healthy_uplinks': 2}, 'HEALTHY'),
    ('E06', {'uplinks': 2, 'healthy_uplinks': 1}, 'HEALTHY'),    # partial loss not detectable
    ('E06', {'uplinks': 2, 'healthy_uplinks': 0}, 'FAULT'),
    ('E06', {'uplinks': 0, 'healthy_uplinks': 0}, 'UNKNOWN'),    # no uplink configured
    ('E06', {'uplinks': -1, 'healthy_uplinks': 0}, 'UNKNOWN'),
    ('E07', {'disconnect_events': 3, 'observation_window_s': 3600}, 'HEALTHY'),
    ('E07', {'disconnect_events': 4, 'observation_window_s': 3600}, 'FAULT'),
    ('E07', {'disconnect_events': 4, 'observation_window_s': 10}, 'FAULT'),  # burst in short window
    ('E07', {'disconnect_events': 0, 'observation_window_s': 3599}, 'UNKNOWN'),
    ('E07', {'disconnect_events': 0, 'observation_window_s': 0}, 'UNKNOWN'),
    ('E07', {'disconnect_events': -1, 'observation_window_s': 3600}, 'UNKNOWN'),
    ('E07', {'disconnect_events': 4, 'observation_window_s': -1}, 'UNKNOWN'),
    ('E08', {'reachable': True, 'loss_pct': 0.0}, 'HEALTHY'),
    ('E08', {'reachable': True, 'loss_pct': 5.0}, 'HEALTHY'),
    ('E08', {'reachable': True, 'loss_pct': 5.1}, 'FAULT'),
    ('E08', {'reachable': True, 'loss_pct': 100.0}, 'FAULT'),
    ('E08', {'reachable': True, 'loss_pct': 100.1}, 'UNKNOWN'),
    ('E08', {'reachable': True, 'loss_pct': -1.0}, 'UNKNOWN'),
    ('E08', {'reachable': False, 'loss_pct': 0.0}, 'FAULT'),     # unreachable wins over loss figure
]

BAD = [('E02', {'link_up': 'up', 'uptime_seconds': 1}),
       ('E03', {'default_route': True, 'default_route_count': None}),
       ('E04', {'protocol': 5, 'session_connected': True}),
       ('E05', {'nat_enabled': True}),
       ('E06', {'uplinks': 2.5, 'healthy_uplinks': 1}),
       ('E07', {'disconnect_events': 1, 'observation_window_s': '3600'}),
       ('E08', {'reachable': True, 'loss_pct': 0.0, 'extra': 1})]


class BatchETests(support.BatchSimulationCase):
    SIM, DIAG, SKILLS, BOUNDARIES, BAD = SIM, DIAG, SKILLS, BOUNDARIES, BAD


if __name__ == '__main__':
    unittest.main()
