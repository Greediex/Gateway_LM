"""FINALIZE-02: replay Skill chat uses the same Core/Verifier/RCA/answer path.

Approval for replay diagnostics is injected only inside this test; the real
config/skill_launcher/approvals.json must be changed by a human operator.
"""
import unittest
from unittest.mock import patch

from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.command_catalog.loader import digest, read_json
from gateway_pilot.core import ROOT
from gateway_pilot.skill_expansion import deployment as dep
from tests.test_skill_chat import Model, choice

DIAG = ROOT / 'config/skill_launcher/replay.diagnostics.json'


def _approved_read(path, *args, **kwargs):
    doc = read_json(path, *args, **kwargs)
    if str(path).endswith('approvals.json'):
        doc['replay']['diagnostics_digest'] = digest(read_json(DIAG))
    return doc


class ReplayChatTests(unittest.TestCase):
    def setUp(self):
        dep.deployment.cache_clear()
        self.addCleanup(dep.deployment.cache_clear)
        self.now = 100.0
        self.launcher = SkillLauncher(factory=lambda mode: dep.composition(mode, clock=lambda: self.now),
                                      clock=lambda: self.now)

    def chat(self, outputs):
        model = Model(outputs)
        return SkillChat(self.launcher, model_factory=lambda: model), model

    def test_replay_chat_disabled_until_operator_pins_diagnostics(self):
        chat, model = self.chat([])
        with self.assertRaisesRegex(ValueError, 'chat_diagnostics_not_approved'):
            chat.chat('Radio wifi gateway thế nào?', mode='replay')
        self.assertEqual(model.inputs, [])

    def test_replay_chat_measures_through_core_and_reports_synthetic(self):
        with patch.object(dep, 'read_json', side_effect=_approved_read):
            chat, model = self.chat([choice(skills=['B02']),
                                     choice('answer', findings=['expansion.radio_health'])])
            r = chat.chat('Radio wifi của gateway thế nào?', mode='replay')
        self.assertEqual(r['mode'], 'synthetic_replay')
        self.assertTrue(r['synthetic_only'])
        self.assertEqual([x['skill_id'] for x in r['skill_runs']], ['B02'])
        self.assertTrue(r['evidence_ids'])
        self.assertIn('mô phỏng', r['answer'])
        self.assertEqual(model.inputs[0][2]['scope'],
                         'Only the synthetic replay gateway; fixture data, never a real device')
        self.assertTrue(any(a['workflow'] == 'REPLAY-RADIO' for a in r['rca_assessments']))

    def test_replay_write_and_custom_target_need_no_model_or_calls(self):
        with patch.object(dep, 'read_json', side_effect=_approved_read):
            chat, model = self.chat([])
            for text in ('Xóa cấu hình DNS của router', 'reboot gateway', 'Ping 203.0.113.8'):
                r = chat.chat(text, mode='replay')
                self.assertEqual(r['calls'], 0)
                self.assertIn(r['case_status'], {'BLOCKED', 'NEEDS_INPUT'})
                self.assertEqual(r['evidence_ids'], [])
        self.assertEqual(model.inputs, [])

    def test_mode_mismatch_and_invalid_mode_rejected(self):
        with patch.object(dep, 'read_json', side_effect=_approved_read):
            chat, _ = self.chat([])
            sid = self.launcher.create_session('replay')['session_id']
            with self.assertRaisesRegex(ValueError, 'live_session'):
                chat.chat('wifi', session_id=sid, mode='live')
            with self.assertRaisesRegex(ValueError, 'invalid_chat_mode'):
                chat.chat('wifi', mode='router')

    def test_tampered_diagnostics_fail_closed(self):
        def tampered(path, *a, **k):
            doc = _approved_read(path, *a, **k)
            if str(path).endswith('replay.diagnostics.json'):
                doc['claims'][0]['severity'] = 'HEALTHY'
            return doc
        with patch.object(dep, 'read_json', side_effect=tampered):
            with self.assertRaises(Exception):
                dep.composition('replay', clock=lambda: self.now)


if __name__ == '__main__':
    unittest.main()
