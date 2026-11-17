"""HTTP durability accepts opaque handles only; fixtures make no device calls."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from gateway_pilot.application.session_storage import SessionStorage
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.skill_expansion.deployment import composition
from gateway_pilot.observability.snapshot import VerifiedSnapshot
from tests.test_skill_launcher import FakeLaptopBackend
from web_gateway import server


class SessionStorageHTTPTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.entries = []
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.storage = SessionStorage(Path(self.tmp.name) / 'state', clock=lambda: self.now)
        self.launcher = self.make_launcher()
        launcher_patch = patch('gateway_pilot.application.skill_launcher.LAUNCHER', self.launcher)
        launcher_patch.start()
        self.addCleanup(launcher_patch.stop)
        self.httpd = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def make_launcher(self):
        def factory(mode):
            entry = composition(mode, backend=FakeLaptopBackend() if mode == 'live' else None,
                                clock=lambda: self.now)
            self.entries.append(entry)
            return entry
        return SkillLauncher(factory=factory, storage=self.storage, clock=lambda: self.now)

    def stop_server(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)

    def request(self, path, payload=None, *, method='POST'):
        connection = http.client.HTTPConnection('127.0.0.1', self.httpd.server_port, timeout=5)
        try:
            connection.request(method, path, json.dumps(payload) if method == 'POST' else None,
                               headers={'Content-Type': 'application/json'})
            response = connection.getresponse()
            self.assertEqual(response.getheader('Cache-Control'), 'no-store')
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def saved_session(self):
        status, created = self.request('/api/skills/session', {'mode': 'live'})
        self.assertEqual(status, 200)
        sid = created['session_id']
        status, result = self.request('/api/skills/run', {'session_id': sid, 'skill_id': 'A08'})
        self.assertEqual(status, 200)
        self.assertGreater(result['calls_total'], 0)
        return sid, result

    def restart_launcher(self):
        fresh = self.make_launcher()
        replacement = patch('gateway_pilot.application.skill_launcher.LAUNCHER', fresh)
        replacement.start()
        self.addCleanup(replacement.stop)
        return fresh

    def test_resume_accepts_only_opaque_operator_id(self):
        for payload in (None, [], {}, {'session_id': '../private/checkpoint.json'},
                        {'session_id': ['a' * 32]}, {'session_id': 123},
                        {'session_id': 'A' * 32}, {'session_id': 'a' * 31}):
            status, result = self.request('/api/skills/resume', payload)
            self.assertIn(status, (400, 410))
            self.assertNotIn('snapshot', result)
        self.assertEqual(self.entries, [])

    def test_configuration_and_evidence_injection_rejected_before_factory(self):
        for field in ('path', 'directory', 'checkpoint', 'secret', 'key', 'request',
                      'goals', 'target', 'backend', 'permissions', 'case_id',
                      'calls', 'max_calls', 'created_at', 'expires_at', 'evidence'):
            with self.subTest(field=field):
                status, result = self.request('/api/skills/resume', {'session_id': 'a' * 32, field: 'injected'})
                self.assertEqual(status, 400)
                self.assertNotIn('snapshot', result)
        self.assertEqual(self.entries, [])

    def test_reconstructed_launcher_restores_without_new_calls_or_ttl_reset(self):
        sid, original = self.saved_session()
        expiry = self.launcher._get(sid)['session'].expires_at
        self.now += 1
        fresh = self.restart_launcher()
        status, restored = self.request('/api/skills/resume', {'session_id': sid})
        self.assertEqual(status, 200)
        self.assertFalse(restored['reused_session'])
        self.assertGreater(restored['restored_facts'], 0)
        session = fresh._get(sid)['session']
        self.assertEqual(session.expires_at, expiry)
        self.assertEqual(session.runner.calls, original['calls_total'])
        self.assertEqual(self.entries[-1]['backend'].calls, 0)
        status, reused = self.request('/api/skills/run', {'session_id': sid, 'skill_id': 'A08'})
        self.assertEqual(status, 200)
        self.assertEqual(reused['calls_total'], original['calls_total'] + reused['calls_this_run'])

    def test_closed_and_expired_sessions_cannot_resume(self):
        sid, _ = self.saved_session()
        self.assertEqual(self.request('/api/skills/close', {'session_id': sid})[0], 200)
        status, result = self.request('/api/skills/resume', {'session_id': sid})
        self.assertIn(status, (400, 410))
        self.assertNotIn('snapshot', result)
        sid, _ = self.saved_session()
        self.now += 301
        self.restart_launcher()
        status, result = self.request('/api/skills/resume', {'session_id': sid})
        self.assertIn(status, (400, 410))
        self.assertNotIn('snapshot', result)

    def test_persistent_run_and_concurrent_close_finish_without_lock_inversion(self):
        status, created = self.request('/api/skills/session', {'mode': 'live'})
        self.assertEqual(status, 200)
        sid = created['session_id']
        entered, release, close_started = threading.Event(), threading.Event(), threading.Event()
        results, errors = {}, []
        original = VerifiedSnapshot.export
        def delayed_export(snapshot):
            entered.set()
            if not release.wait(timeout=3):
                raise AssertionError('test release timeout')
            return original(snapshot)
        def run():
            try:
                results['run'] = self.launcher.run(sid, 'A08')
            except Exception as exc:
                errors.append(exc)
        def close():
            close_started.set()
            try:
                results['close'] = self.launcher.close(sid)
            except Exception as exc:
                errors.append(exc)
        with patch.object(VerifiedSnapshot, 'export', delayed_export):
            running = threading.Thread(target=run, daemon=True)
            closing = threading.Thread(target=close, daemon=True)
            running.start()
            try:
                self.assertTrue(entered.wait(timeout=3))
                closing.start()
                self.assertTrue(close_started.wait(timeout=3))
            finally:
                release.set()
            running.join(timeout=3)
            closing.join(timeout=3)
        self.assertFalse(running.is_alive(), 'run blocked by launcher global/session lock inversion')
        self.assertFalse(closing.is_alive(), 'close did not complete after active run')
        self.assertEqual(errors, [])
        self.assertTrue(results['close']['closed'])
        self.assertGreater(results['run']['calls_total'], 0)

    def test_history_invalid_query_or_tamper_returns_bounded_json_error(self):
        self.saved_session()
        status, result = self.request('/api/skills/history?path=/outside', method='GET')
        self.assertEqual(status, 400)
        self.assertNotIn('sessions', result)
        path = next(self.storage.directory.glob('*.checkpoint.json'))
        data = json.loads(path.read_text())
        data['body']['budget']['calls'] = 0
        path.write_text(json.dumps(data))
        status, result = self.request('/api/skills/history', method='GET')
        self.assertEqual(status, 503)
        self.assertNotIn('sessions', result)
        self.assertNotIn('192.0.2.10', json.dumps(result))

    def test_history_exposes_summary_without_raw_network_values_or_prompts(self):
        sid, _ = self.saved_session()
        entry = self.launcher._get(sid)
        entry['session'].execute(('client.ipv4',), request='private prompt sentinel')
        self.launcher.checkpoint(sid)
        status, result = self.request('/api/skills/history', method='GET')
        self.assertEqual(status, 200)
        self.assertFalse(result['raw_conversations_stored'])
        self.assertEqual(len(result['sessions']), 1)
        serialized = json.dumps(result)
        for private in ('private prompt sentinel', '192.0.2.10', '192.0.2.1',
                        'Synthetic test AP', '02:00:00:00:00:01', 'wifi0'):
            self.assertNotIn(private, serialized)
        self.assertLessEqual(len(result['sessions']), 20)
        self.assertNotIn('evidence', result['sessions'][0])


if __name__ == '__main__':
    unittest.main()
