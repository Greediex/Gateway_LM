"""Local HTTP Skill API accepts bounded IDs, with isolated expiring sessions."""
import http.client
import json
import threading
import unittest
from unittest.mock import patch

from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_launcher import FakeLaptopBackend
from web_gateway import server


class SkillLauncherHTTPTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.entries = []
        def factory(mode):
            entry = composition(mode, backend=FakeLaptopBackend() if mode == 'live' else None,
                                clock=lambda: self.now)
            self.entries.append(entry)
            return entry
        self.launcher = SkillLauncher(factory=factory, max_sessions=2, clock=lambda: self.now)
        launcher_patch = patch('gateway_pilot.application.skill_launcher.LAUNCHER', self.launcher)
        launcher_patch.start()
        self.addCleanup(launcher_patch.stop)
        self.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def request(self, path, payload=None, *, method='POST', headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        try:
            connection.request(method, path, json.dumps(payload) if method == 'POST' else None,
                               headers={'Content-Type': 'application/json', **(headers or {})})
            response = connection.getresponse()
            self.assertEqual(response.getheader('Cache-Control'), 'no-store')
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def create(self, mode='replay'):
        status, created = self.request('/api/skills/session', {'mode': mode})
        self.assertEqual(status, 200)
        return created['session_id']

    def test_catalog_defaults_laptop_and_rejects_unsupported_query_parameters(self):
        status, catalog = self.request('/api/skills', method='GET')
        self.assertEqual((status, catalog['mode'], catalog['design_total'], catalog['native_total']), (200, 'live', 120, 6))
        self.assertTrue(catalog['requires_session'])
        self.assertEqual(self.entries, [])
        for query in ('mode=live&target=router', 'mode=live&mode=replay', 'mode=cloud', 'mode='):
            self.assertEqual(self.request('/api/skills?' + query, method='GET')[0], 400)

    def test_sessions_execute_reuse_and_isolate_evidence(self):
        first, second = self.create(), self.create()
        status, result = self.request('/api/skills/run', {'session_id': first, 'skill_id': 'B02'})
        self.assertEqual((status, result['calls_this_run'], result['synthetic_only']), (200, 1, True))
        _, repeated = self.request('/api/skills/run', {'session_id': first, 'skill_id': 'B02'})
        self.assertEqual(repeated['calls_this_run'], 0)
        _, independent = self.request('/api/skills/run', {'session_id': second, 'skill_id': 'B02'})
        self.assertEqual(independent['calls_this_run'], 1)
        self.assertNotEqual(independent['evidence_ids'], result['evidence_ids'])
        _, unavailable = self.request('/api/skills/run', {'session_id': first, 'skill_id': 'B04'})
        self.assertEqual((unavailable['status'], unavailable['calls_this_run']), ('UNAVAILABLE', 0))

    def test_strict_payload_rejects_configuration_injection_before_factory_or_calls(self):
        for field in ('target', 'backend', 'permissions', 'command', 'function_ids', 'approved_digest', 'path', 'snapshot'):
            self.assertEqual(self.request('/api/skills/session', {'mode': 'replay', field: 'injected'})[0], 400)
        for payload in ({}, [], None, {'mode': 'bad'}, {'mode': ['live']}):
            self.assertEqual(self.request('/api/skills/session', payload)[0], 400)
        self.assertEqual(self.entries, [])
        sid = self.create()
        for payload in ({'session_id': sid}, {'session_id': sid, 'skill_id': []},
                        {'session_id': sid, 'skill_id': 'B02', 'target': 'router'},
                        {'session_id': sid, 'skill_id': 'unknown'},
                        {'session_id': sid, 'skill_id': 'x' * 101}):
            self.assertEqual(self.request('/api/skills/run', payload)[0], 400)
        self.assertEqual(self.entries[0]['session'].runner.calls, 0)

    def test_expiry_closed_and_forged_handles_return_410_capacity_429(self):
        first, second = self.create(), self.create()
        self.assertEqual(self.request('/api/skills/session', {'mode': 'replay'})[0], 429)
        self.assertEqual(self.request('/api/skills/close', {'session_id': first})[0], 200)
        for sid in (first, 'a' * 32, 'forged'):
            status, body = self.request('/api/skills/run', {'session_id': sid, 'skill_id': 'B02'})
            self.assertEqual((status, body['reason']), (410, 'session_expired'))
        self.now += 300
        self.assertEqual(self.request('/api/skills/run', {'session_id': second, 'skill_id': 'B02'})[0], 410)

    def test_context_drift_returns_410_without_stale_facts(self):
        sid = self.create('live')
        self.assertEqual(self.request('/api/skills/run', {'session_id': sid, 'skill_id': 'A08'})[0], 200)
        entry = self.entries[0]
        before = entry['backend'].calls
        entry['backend'].bssid = '02:00:00:00:00:02'
        status, body = self.request('/api/skills/run', {'session_id': sid, 'skill_id': 'A08'})
        self.assertEqual((status, body['reason']), (410, 'session_expired'))
        self.assertNotIn('snapshot', body)
        self.assertEqual(entry['backend'].calls, before)

    def test_acl_drift_returns_410_without_old_success(self):
        sid = self.create()
        self.assertEqual(self.request('/api/skills/run', {'session_id': sid, 'skill_id': 'B02'})[0], 200)
        entry = self.entries[0]
        entry['runtime'].permissions = frozenset()
        status, body = self.request('/api/skills/run', {'session_id': sid, 'skill_id': 'B02'})
        self.assertEqual((status, body['reason']), (410, 'session_expired'))
        self.assertNotIn('snapshot', body)
        self.assertEqual(entry['session'].runner.calls, 1)
        self.assertIsNone(entry['session'].state.fact('expansion.radio_health'))

    def test_origin_host_and_content_type_guards_precede_session_creation(self):
        for headers, expected in (({'Host': 'attacker.invalid'}, 403),
                                  ({'Origin': 'https://attacker.invalid'}, 403),
                                  ({'Content-Type': 'text/plain'}, 415)):
            self.assertEqual(self.request('/api/skills/session', {'mode': 'live'}, headers=headers)[0], expected)
        self.assertEqual(self.entries, [])


if __name__ == '__main__':
    unittest.main()
