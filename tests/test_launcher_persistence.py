"""Production launcher wiring for signed session restart; synthetic provider only."""
import tempfile
from pathlib import Path
import unittest

from gateway_pilot.application.skill_launcher import SkillLauncher, SkillSessionError
from gateway_pilot.application.session_storage import SessionStorage
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_launcher import FakeLaptopBackend


class LauncherPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.now=100.
        self.entries=[]
        def factory(mode):
            entry=composition(mode,backend=FakeLaptopBackend(),clock=lambda:self.now)
            self.entries.append(entry)
            return entry
        self.factory=factory

    def launcher(self):
        return SkillLauncher(factory=self.factory,clock=lambda:self.now,
                             storage=SessionStorage(Path(self.directory.name)))

    def test_new_launcher_restores_facts_calls_and_deadline_without_new_sample(self):
        original=self.launcher();sid=original.create_session()['session_id']
        original.run(sid,'laptop.route.inspect')
        entry=original._get(sid);calls=entry['session'].runner.calls
        deadline=entry['session'].expires_at
        self.now+=1
        reopened=self.launcher();result=reopened.resume(sid)
        current=reopened._get(sid)['session']
        self.assertGreater(result['restored_facts'],0)
        self.assertEqual(current.runner.calls,calls)
        self.assertEqual(current.expires_at,deadline)
        reused=reopened.run(sid,'laptop.route.inspect')
        self.assertEqual(reused['calls_this_run'],0)
        self.assertEqual(reopened.history()[0]['calls'],calls)
        self.assertFalse(any('value' in r or 'request' in r for r in reopened.history()))

    def test_close_and_expiry_cannot_get_a_new_budget_by_resume(self):
        launcher=self.launcher();sid=launcher.create_session()['session_id']
        launcher.run(sid,'laptop.route.inspect');launcher.close(sid)
        with self.assertRaises(SkillSessionError):self.launcher().resume(sid)
        sid=launcher.create_session()['session_id'];launcher.run(sid,'laptop.route.inspect')
        self.now+=301
        with self.assertRaises(SkillSessionError):self.launcher().resume(sid)
