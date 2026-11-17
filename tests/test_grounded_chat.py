"""Answer-layer regressions through the real Core; no OS calls."""
import json
import unittest

from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher, SkillSessionError
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_chat import Model, choice
from tests.test_skill_launcher import FakeLaptopBackend


class GroundedChatTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.
        self.backend = FakeLaptopBackend()
        self.backend.route = lambda: dict(has_route=True, interface='ethernet0',
            source_ipv4='192.0.2.10', gateway='192.0.2.1', resolver_fingerprint='')
        self.entries = []
        def factory(mode):
            e = composition(mode, backend=self.backend, clock=lambda:self.now)
            self.entries.append(e)
            return e
        self.launcher = SkillLauncher(factory=factory, clock=lambda:self.now)
        self.model = Model([choice(skills=['laptop.wifi.inspect']),
                            choice('answer', findings=['laptop.wifi'])])
        self.chat = SkillChat(self.launcher, model_factory=lambda:self.model, clock=lambda:self.now)

    def completion(self, advance=False, mislabel=False, close=False):
        selected = []
        def complete(payload, *, timeout):
            if close:
                self.launcher.close(next(iter(self.launcher._sessions)))
            body = json.loads(payload['messages'][-1]['content'])
            if 'verified_facts' in body:
                fid = next(f['id'] for f in body['verified_facts'] if f['key']=='ssid')
                selected.append(fid)
                if advance:self.now += 31
                return json.dumps({'fact_ids':[fid]})
            label = 'BSSID' if mislabel else 'SSID'
            return json.dumps({'segments':[{'kind':'statement',
                'text':label+' hiện tại là {{'+selected[0]+'}}.'}]})
        self.model.complete_answer = complete

    def test_ssid_followup_does_not_show_route_bssid_or_signal(self):
        first = self.chat.chat('Wi-Fi laptop')
        self.model.outputs = [choice('answer', findings=['laptop.wifi'])]
        r = self.chat.chat('kiểm tra ssid', session_id=first['session_id'])
        self.assertEqual(r['calls'], 0)
        self.assertIn('SSID', r['answer'])
        for unrelated in ['BSSID', 'signal', 'Đường đo', 'Gateway:', 'Internet']:
            self.assertNotIn(unrelated, r['answer'])

    def test_diagnostic_is_not_whole_network_health(self):
        r = self.chat.chat('Wi-Fi laptop có vấn đề gì?')
        self.assertIn('Chưa', r['answer'])
        self.assertIn('ethernet0', r['answer'])
        self.assertEqual(r['diagnostic_status'], 'INCONCLUSIVE')
        self.assertIsNone(r['diagnosis'])

    def test_expiry_during_synthesis_discards_draft_and_refreshes_once(self):
        self.completion(advance=True)
        r = self.chat.chat('kiểm tra ssid')
        self.assertEqual(r['recovery_attempts'], 1)
        self.assertFalse(r['answer_synthesis']['used_llm'])
        self.assertTrue(r['snapshot']['facts']['laptop.wifi']['expires_in_s'] > 0)
        self.assertEqual(r['model_calls'], 3)  # No second answer RPC using an expired ledger.
        self.assertTrue(all(e in {f['evidence_id'] for f in r['snapshot']['facts'].values()}
                            for e in r['evidence_ids']))

    def test_field_relabel_is_rejected(self):
        self.completion(mislabel=True)
        r = self.chat.chat('kiểm tra ssid')
        self.assertFalse(r['answer_synthesis']['used_llm'])
        self.assertNotIn('BSSID', r['answer'])

    def test_expiry_at_final_wording_refreshes_and_never_reuses_the_draft(self):
        self.completion()
        original=self.model.complete_answer
        def late_wording(payload, *, timeout):
            result=original(payload,timeout=timeout)
            if 'allowed_statements' in json.loads(payload['messages'][-1]['content']):
                self.now+=31
            return result
        self.model.complete_answer=late_wording
        r=self.chat.chat('kiểm tra ssid')
        self.assertEqual(r['recovery_attempts'],1)
        self.assertEqual(r['model_calls'],4)
        self.assertFalse(r['answer_synthesis']['used_llm'])
        self.assertEqual(r['answer_synthesis']['reason'],'evidence_changed_or_deadline')
        self.assertGreater(r['snapshot']['facts']['laptop.wifi']['expires_in_s'],0)

    def test_answer_deadline_does_not_start_a_second_rpc_or_reread(self):
        self.chat.max_elapsed_s=5
        self.completion()
        original=self.model.complete_answer
        def late(payload, *, timeout):
            self.assertLessEqual(timeout,5)
            result=original(payload,timeout=timeout)
            self.now+=6
            return result
        self.model.complete_answer=late
        r=self.chat.chat('kiểm tra ssid')
        self.assertEqual(r['stop_reason'],'turn_deadline_exhausted')
        self.assertEqual(r['model_calls'],3)
        self.assertEqual(r['recovery_attempts'],0)
        self.assertNotEqual(r['case_status'],'MEASURED')

    def test_bssid_lookup_is_bound_to_bssid_field(self):
        r=self.chat.chat('BSSID Wi-Fi là gì?')
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertIn('BSSID: 02:00:00:00:00:01.',r['answer'])
        self.assertNotIn('SSID: Synthetic',r['answer'])

    def test_near_expiry_uses_focused_renderer_without_extra_rpc_or_reread(self):
        def delayed_choice(context):
            self.now+=20
            return choice('answer',findings=['laptop.wifi'])
        self.model.outputs[-1]=delayed_choice
        self.model.complete_answer=lambda *a,**kw:self.fail('No synthesis with too little TTL')
        r=self.chat.chat('Laptop đang dùng Wi-Fi nào?')
        self.assertEqual(r['answer'],'SSID: Synthetic test AP.')
        self.assertEqual(r['model_calls'],2)
        self.assertEqual(r['recovery_attempts'],0)
        self.assertEqual(r['answer_synthesis']['reason'],'insufficient_freshness_window')

    def test_close_during_answer_is_still_expired(self):
        self.completion(close=True)
        with self.assertRaises(SkillSessionError):
            self.chat.chat('kiểm tra ssid')
