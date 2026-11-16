"""Actual laptop association semantics, using an entirely fake local provider."""
import unittest

from gateway_pilot.adapters.bindings import TargetContext
from gateway_pilot.core import PlanError
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_launcher import FakeLaptopBackend


class LaptopSkillBackendTests(unittest.TestCase):
    def test_association_uses_bssid_and_never_signal_or_router_inference(self):
        backend = FakeLaptopBackend()
        entry = composition('live', backend=backend)
        runner, _ = entry['session'].execute(['expansion.client_association'])
        evidence = runner.state.fact('expansion.client_association')
        self.assertIsNotNone(evidence)
        self.assertEqual(evidence['value'], {'associated': True, 'access_point_id': backend.bssid})
        self.assertEqual(evidence['function_version'], '2.0.0')
        self.assertEqual(evidence['source'], 'linux_client/skill_laptop_v1')
        self.assertNotIn('rssi_dbm', evidence['value'])
        self.assertNotIn('snr_db', evidence['value'])

    def test_disconnected_is_valid_measurement_with_no_access_point(self):
        backend = FakeLaptopBackend()
        backend.associated, backend.bssid = False, ''
        entry = composition('live', backend=backend)
        runner, _ = entry['session'].execute(['expansion.client_association'])
        self.assertEqual(runner.state.fact('expansion.client_association')['value'],
                         {'associated': False, 'access_point_id': ''})

    def test_associated_without_bssid_is_unavailable_no_sample(self):
        backend = FakeLaptopBackend()
        backend.bssid = ''
        entry = composition('live', backend=backend)
        snapshot = entry['runtime'].probe()
        row = next(r for r in snapshot.functions if r.function_id == 'expansion.client_association')
        self.assertEqual(row.status, 'UNSUPPORTED')
        with self.assertRaises(PlanError):
            entry['session'].execute(['expansion.client_association'])
        self.assertEqual(backend.calls, 0)

    def test_wrong_target_and_changed_environment_never_support_association(self):
        backend = FakeLaptopBackend()
        old_environment = backend.environment_id
        self.assertFalse(backend.supports('expansion.client_association',
                         TargetContext('client', 'remote-laptop', old_environment)))
        backend.bssid = '02:00:00:00:00:02'
        self.assertFalse(backend.supports('expansion.client_association',
                         TargetContext('client', backend.client_id, old_environment)))
        self.assertEqual(backend.calls, 0)


if __name__ == '__main__':
    unittest.main()
