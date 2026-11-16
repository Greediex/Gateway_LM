"""Laptop-first launcher contracts; all providers in this suite are synthetic."""
import copy
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from unittest.mock import patch

from gateway_pilot.adapters.laptop_skills import LaptopSkillBackend
from gateway_pilot.application.skill_launcher import SkillLauncher, SkillSessionError
from gateway_pilot.command_catalog.loader import digest
from gateway_pilot.core import PlanError
from gateway_pilot.observability.snapshot import VerifiedSnapshot
from gateway_pilot.skill_expansion import deployment as deployment_module
from gateway_pilot.skill_expansion.deployment import composition, deployment
from gateway_pilot.skill_expansion.profiles import load_bundle


class FakeLaptopBackend(LaptopSkillBackend):
    """Exercise the real laptop adapter without OS calls or hardware claims."""
    def __init__(self):
        self.client_id, self.interface = 'local-laptop', 'wifi0'
        self._tools = {'ping': None, 'resolvectl': None}
        self.calls = 0
        self.associated, self.bssid = True, '02:00:00:00:00:01'

    @property
    def environment_id(self):
        return digest({'associated': self.associated, 'bssid': self.bssid})

    def wifi(self):
        return dict(interface=self.interface, radio_enabled=True, associated=self.associated,
                    ssid='Synthetic test AP' if self.associated else '', bssid=self.bssid,
                    signal_pct=70 if self.associated else -1, channel=36, frequency_mhz=5180,
                    ap_rate_mbps=1201)

    def route(self):
        return dict(has_route=True, interface=self.interface, source_ipv4='192.0.2.10',
                    gateway='192.0.2.1', resolver_fingerprint='')

    def _ipv4(self):
        return dict(configured=True, address='192.0.2.10')

    def sample(self, function, arguments, context):
        self.calls += 1
        return super().sample(function, arguments, context)


class SkillLauncherTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.entries = []

    def launcher(self, *, backend=None, max_sessions=8, calls=24):
        def factory(mode):
            entry = composition(mode, backend=backend, clock=lambda: self.now)
            entry['session'].runner.max_calls = calls
            self.entries.append(entry)
            return entry
        return SkillLauncher(factory=factory, max_sessions=max_sessions, clock=lambda: self.now)

    def test_replay_b02_b03_b05_verified_then_reused_and_refreshed(self):
        launcher = self.launcher()
        sid = launcher.create_session('replay')['session_id']
        for index, skill in enumerate(('B02', 'B03', 'B05'), 1):
            result = launcher.run(sid, skill)
            self.assertEqual(result['status'], 'MEASURED')
            self.assertTrue(result['synthetic_only'])
            self.assertEqual((result['calls_this_run'], result['calls_total']), (1, index))
            self.assertEqual(result['missing_ports'], [])
            self.assertTrue(result['evidence_ids'])
            self.assertTrue(all(row['contract_digest'] and row['source'].startswith('synthetic_replay/')
                                for row in result['snapshot']['facts'].values()))
            repeated = launcher.run(sid, skill)
            self.assertEqual(repeated['calls_this_run'], 0)
            self.assertEqual(repeated['evidence_ids'], result['evidence_ids'])
            self.assertTrue(repeated['reused_ports'])
        self.now += 31
        refreshed = launcher.run(sid, 'B02')
        self.assertEqual(refreshed['calls_this_run'], 1)
        self.assertEqual(refreshed['calls_total'], 4)

    def test_unsupported_designs_make_no_calls_and_keep_catalog_honest(self):
        for mode in ('live', 'replay'):
            backend = FakeLaptopBackend() if mode == 'live' else None
            launcher = self.launcher(backend=backend)
            created = launcher.create_session(mode)
            catalog = created['catalog']
            self.assertEqual(catalog['design_total'], 120)
            self.assertEqual(catalog['native_total'], 6 if mode == 'live' else 0)
            self.assertEqual(len(catalog['rows']), 126 if mode == 'live' else 120)
            for skill in ('SK13', 'B04', 'B07', 'A04'):
                result = launcher.run(created['session_id'], skill)
                self.assertEqual(result['status'], 'UNAVAILABLE')
                self.assertEqual(result['calls_this_run'], 0)
                self.assertEqual(result['calls_total'], 0)
                self.assertEqual(result['snapshot']['facts'], {})
            if mode == 'live':
                rows = {r['skill_id']: r for r in catalog['rows']}
                self.assertEqual(rows['B02']['availability'], 'UNAVAILABLE')
                self.assertEqual(rows['B04']['reason'], 'REQUIRES_RSSI_AND_SNR')
                self.assertEqual(rows['B07']['reason'], 'REQUIRES_ROAMING_HISTORY')

    def test_live_fake_provider_exercises_identity_association_and_optional_degradation(self):
        backend = FakeLaptopBackend()
        launcher = self.launcher(backend=backend)
        created = launcher.create_session('live')
        rows = {r['skill_id']: r for r in created['catalog']['rows']}
        self.assertEqual(rows['laptop.network.inspect']['availability'], 'DEGRADED')
        self.assertEqual(rows['A08']['availability'], 'READY')
        identity = launcher.run(created['session_id'], 'SK01')
        self.assertEqual(identity['calls_this_run'], 1)
        result = launcher.run(created['session_id'], 'A08')
        self.assertEqual(result['status'], 'MEASURED')
        self.assertFalse(result['synthetic_only'])  # Operator-selected live path, fake only in this test.
        association = result['snapshot']['facts']['expansion.client_association']
        self.assertEqual(association['value'], {'associated': True, 'access_point_id': backend.bssid})
        self.assertEqual((association['scope'], association['target']), ('client', 'local-laptop'))
        repeated = launcher.run(created['session_id'], 'A08')
        self.assertEqual(repeated['calls_this_run'], 0)
        self.assertEqual(repeated['evidence_ids'], result['evidence_ids'])

    def test_expired_closed_invalid_handles_and_capacity(self):
        launcher = self.launcher(max_sessions=1)
        sid = launcher.create_session('replay')['session_id']
        with self.assertRaisesRegex(SkillSessionError, 'session_capacity_limit'):
            launcher.create_session('replay')
        for invalid in (None, '', 'x' * 32, 'a' * 32):
            with self.assertRaisesRegex(SkillSessionError, 'session_expired'):
                launcher.run(invalid, 'B02')
        self.now += 300
        with self.assertRaisesRegex(SkillSessionError, 'session_expired'):
            launcher.run(sid, 'B02')
        self.assertTrue(self.entries[0]['session'].closed)
        sid = launcher.create_session('replay')['session_id']
        self.assertTrue(launcher.close(sid)['closed'])
        with self.assertRaisesRegex(SkillSessionError, 'session_expired'):
            launcher.run(sid, 'B02')

    def test_fixture_or_laptop_context_drift_closes_without_more_samples(self):
        for mode in ('live', 'replay'):
            backend = FakeLaptopBackend() if mode == 'live' else None
            launcher = self.launcher(backend=backend)
            sid = launcher.create_session(mode)['session_id']
            skill = 'A08' if mode == 'live' else 'B02'
            launcher.run(sid, skill)
            entry = self.entries[-1]
            calls = entry['session'].runner.calls
            if mode == 'live':
                backend.bssid = '02:00:00:00:00:02'
            else:
                entry['backend']._fixture.clear()
            with self.assertRaisesRegex(SkillSessionError, 'session_expired'):
                launcher.run(sid, skill)
            self.assertTrue(entry['session'].closed)
            self.assertEqual(entry['session'].runner.calls, calls)
            self.assertTrue(all(e.get('_invalidated') for e in entry['session'].state.evidence))

    def test_global_budget_does_not_reset_and_sessions_are_isolated(self):
        launcher = self.launcher(calls=1)
        first = launcher.create_session('replay')['session_id']
        result = launcher.run(first, 'B02')
        denied = launcher.run(first, 'B03')
        self.assertEqual((denied['status'], denied['calls_this_run'], denied['calls_total']), ('UNAVAILABLE', 0, 1))
        self.assertEqual(denied['snapshot']['facts'], {})
        self.assertEqual(launcher.run(first, 'B02')['calls_this_run'], 0)
        second = launcher.create_session('replay')['session_id']
        independent = launcher.run(second, 'B02')
        self.assertEqual(independent['calls_this_run'], 1)
        self.assertNotEqual(independent['evidence_ids'], result['evidence_ids'])

    def test_close_waits_for_in_progress_snapshot_export(self):
        launcher = self.launcher()
        sid = launcher.create_session('replay')['session_id']
        entered, release, closing = threading.Event(), threading.Event(), threading.Event()
        original_export = VerifiedSnapshot.export
        def paused_export(snapshot):
            entered.set()
            if not release.wait(timeout=5):
                raise AssertionError('snapshot export was never released')
            return original_export(snapshot)
        def close():
            closing.set()
            return launcher.close(sid)
        with patch.object(VerifiedSnapshot, 'export', paused_export), ThreadPoolExecutor(max_workers=2) as pool:
            running = pool.submit(launcher.run, sid, 'B02')
            try:
                self.assertTrue(entered.wait(timeout=5))
                stopped = pool.submit(close)
                self.assertTrue(closing.wait(timeout=5))
                with self.assertRaises(FutureTimeout):
                    stopped.result(timeout=0.05)
            finally:
                release.set()
            measured = running.result(timeout=5)
            self.assertTrue(measured['snapshot']['facts'])
            self.assertTrue(stopped.result(timeout=5)['closed'])
        self.assertTrue(self.entries[0]['session'].closed)
        with self.assertRaisesRegex(SkillSessionError, 'session_expired'):
            launcher.run(sid, 'B02')


class SkillDeploymentTests(unittest.TestCase):
    def setUp(self):
        deployment.cache_clear()
        self.addCleanup(deployment.cache_clear)

    def test_pinned_live_replay_separation_and_unchanged_proposed_source(self):
        before = digest(load_bundle()['catalog'])
        live, _, live_pins, live_actions = deployment('live')
        replay, _, replay_pins, replay_actions = deployment('replay')
        self.assertNotEqual(live['content_digest'], replay['content_digest'])
        self.assertTrue(live_pins['source'].startswith('linux_client/'))
        self.assertTrue(replay_pins['source'].startswith('synthetic_replay/'))
        self.assertEqual(set(replay_actions), {'B02', 'B03', 'B05'})
        self.assertEqual(set(live_actions) & set(replay_actions), set())
        self.assertTrue(all(f['scope'] == 'client' and f['risk'] == 'READ_ONLY' for f in live['functions']))
        self.assertTrue(all(f['scope'] == 'gateway' and f['risk'] == 'READ_ONLY' for f in replay['functions']))
        bundle = load_bundle()
        self.assertEqual(len(bundle['catalog']['functions']), 72)
        self.assertTrue(all(f['lifecycle'] == 'PROPOSED' for f in bundle['catalog']['functions']))
        self.assertEqual(digest(bundle['catalog']), before)

    def test_action_and_registry_approval_tamper_rejected(self):
        real_read = deployment_module.read_json
        for filename, mutate in (
            ('live.actions.json', lambda d: d['actions'][0].update(name='unreviewed action')),
            ('approvals.json', lambda d: d['live'].update(registry_digest='0' * 64)),
        ):
            deployment.cache_clear()
            def altered(path, **kwargs):
                document = real_read(path, **kwargs)
                if path.name == filename:
                    document = copy.deepcopy(document)
                    mutate(document)
                return document
            with patch.object(deployment_module, 'read_json', side_effect=altered):
                with self.assertRaises(PlanError):
                    deployment('live')

    def test_replay_backend_cannot_be_live_provider_or_get_real_target_support(self):
        replay = composition('replay')
        with self.assertRaisesRegex(PlanError, 'skill_provider_pin'):
            composition('live', backend=replay['backend'])
        with self.assertRaisesRegex(PlanError, 'skill_provider_pin'):
            composition('replay', backend=FakeLaptopBackend())
        from gateway_pilot.adapters.bindings import TargetContext
        context = TargetContext('gateway', 'real-router', replay['runtime'].context.environment_id)
        for fid in replay['runtime'].registry.functions:
            self.assertFalse(replay['backend'].supports(fid, context))


if __name__ == '__main__':
    unittest.main()
