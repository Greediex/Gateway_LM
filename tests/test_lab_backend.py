"""LAB-01: OpenWrt lab ubus reads mapped to Skill ports, through the same Core (fake transport)."""
import unittest
from pathlib import Path
from types import SimpleNamespace

from gateway_pilot.adapters.ubus_http import UbusHttpError, UbusHttpReadTransport
from gateway_pilot.skill_expansion import lab_backend as lab
from gateway_pilot.skill_expansion.runtime_bridge import SkillNotReady
from scripts.lab_skills import run

WAN_UP = {'up': True, 'uptime': 120, 'device': 'eth1',
          'route': [{'target': '0.0.0.0', 'mask': 0, 'nexthop': '100.64.0.1'}]}
WAN_DOWN = {'up': False, 'pending': False}


class FakeUbus:
    def __init__(self, wan=WAN_UP, carrier=True, fail=(), deny=()):
        self.data = {('network.interface.wan', 'status'): wan,
                     ('network.device', 'status'): {'carrier': carrier},
                     ('system', 'board'): {'release': {'version': '25.12.6'}},
                     ('system', 'info'): {'root': {'avail': 75344}}}
        self.fail, self.deny = set(fail), set(deny)

    def probe(self, obj, method):
        return (obj, method) not in self.deny

    def read(self, obj, method, args):
        if (obj, method) in self.fail:
            raise UbusHttpError('ubus_call_failed')
        return self.data[(obj, method)]


class TransportTest(unittest.TestCase):
    def test_refuses_non_loopback_urls(self):
        for url in ('http://192.168.1.1/ubus', 'https://127.0.0.1/ubus', 'http://example.com/ubus',
                    'http://127.0.0.1:18080/other'):
            with self.assertRaises(ValueError):
                UbusHttpReadTransport(url, 'gwlm', Path('/nonexistent'))
        UbusHttpReadTransport('http://127.0.0.1:18080/ubus', 'gwlm', Path('/nonexistent'))


class ReaderTest(unittest.TestCase):
    def test_wan_link(self):
        self.assertEqual(lab.wan_link(FakeUbus()), {'link_up': True, 'uptime_seconds': 120})
        self.assertEqual(lab.wan_link(FakeUbus(wan=WAN_DOWN)), {'link_up': False, 'uptime_seconds': 0})
        self.assertEqual(lab.wan_link(FakeUbus(carrier=False)), {'link_up': False, 'uptime_seconds': 0})

    def test_wan_routes(self):
        self.assertEqual(lab.wan_routes(FakeUbus()), {'default_route': True, 'default_route_count': 1})
        self.assertEqual(lab.wan_routes(FakeUbus(wan=WAN_DOWN)), {'default_route': False, 'default_route_count': 0})

    def test_firmware(self):
        self.assertEqual(lab.firmware_info(FakeUbus()), {'version': '25.12.6', 'free_storage_mb': 73.6})

    def test_malformed_replies_raise(self):
        with self.assertRaises(lab.LabReadError):
            lab.wan_link(FakeUbus(wan={'uptime': 3}))
        with self.assertRaises(lab.LabReadError):
            lab.wan_link(FakeUbus(carrier='yes'))
        with self.assertRaises(lab.LabReadError):
            lab.wan_routes(FakeUbus(wan={'up': True, 'route': 'x'}))
        bad = FakeUbus()
        bad.data[('system', 'info')] = {}
        with self.assertRaises(lab.LabReadError):
            lab.firmware_info(bad)

    def test_backend_refuses_other_targets(self):
        backend = lab.OpenWrtLabBackend([{'function_id': 'expansion.wan_link', 'scope': 'gateway',
                                          'capability_probe': 'p'}], [], FakeUbus())
        synthetic = SimpleNamespace(scope='gateway', target_id='synthetic-test-target',
                                    environment_id=lab.ENVIRONMENT_ID)
        self.assertFalse(backend.supports('expansion.wan_link', synthetic))
        self.assertFalse(backend.supports('expansion.unknown', synthetic))


class CoreTest(unittest.TestCase):
    """Lab values go through the shared Core and versioned Claims, not around them."""

    def verdicts(self, transport, skills=('E02', 'E03', 'H08')):
        return {r['skill']: r['verdict'] for r in run(transport, skills)}

    def test_healthy_lab(self):
        rows = run(FakeUbus())
        self.assertEqual({r['skill']: r['verdict'] for r in rows}, {'E02': 'HEALTHY', 'E03': 'HEALTHY', 'H08': 'HEALTHY'})
        self.assertTrue(all(r['source'] == 'openwrt_lab/ubus-ro' and r['core_calls'] == 1 for r in rows))

    def test_wan_pulled(self):
        self.assertEqual(self.verdicts(FakeUbus(wan=WAN_DOWN)), {'E02': 'FAULT', 'E03': 'FAULT', 'H08': 'HEALTHY'})

    def test_failed_read_is_unknown_not_healthy(self):
        rows = run(FakeUbus(fail={('network.device', 'status')}), ('E02',))
        self.assertEqual((rows[0]['verdict'], rows[0]['value']), ('UNKNOWN', None))

    def test_acl_denied_method_is_not_ready(self):
        with self.assertRaises(SkillNotReady):
            run(FakeUbus(deny={('system', 'info')}), ('H08',))


if __name__ == '__main__':
    unittest.main()
