"""Check semantic field binding, privacy, freshness and full answer coverage."""
import json
import unittest
from unittest.mock import patch

from gateway_pilot.application.grounded_answer import ledger, produce_grounded_answer
from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel


class GroundedAnswerTests(unittest.TestCase):
    def setUp(self):
        self.facts={'laptop.wifi':{'evidence_id':'wifi-new','expires_in_s':30,
                    'value':{'ssid':'Synthetic AP','channel':36,'signal_pct':70,'api_token':'SECRET'}}}
        self.renderers={'laptop.wifi':{'text':'Full Wi-Fi renderer'}}

    def run_answer(self, text):
        replies=iter([json.dumps({'fact_ids':['F1']}),
                      json.dumps({'segments':[{'kind':'statement','text':text}]})])
        return produce_grounded_answer('SSID?', ['laptop.wifi'],self.facts,self.renderers,
                                       lambda p:next(replies))

    def test_actual_model_sentence_keeps_exact_field_and_proof(self):
        r=self.run_answer('SSID hiện tại là {{F1}}.')
        self.assertTrue(r.used_llm)
        self.assertEqual(r.answer,'SSID hiện tại là Synthetic AP.')
        self.assertEqual(r.evidence_ids,('wifi-new',))
        self.assertEqual(r.calls,2)

    def test_relabel_negation_invented_number_and_health_claim_rejected(self):
        for text in ['BSSID hiện tại là {{F1}}.','SSID không phải {{F1}}.',
                     'SSID {{F1}} có 99% tín hiệu.','SSID {{F1}} hoạt động tốt.']:
            with self.subTest(text=text):
                r=self.run_answer(text)
                self.assertFalse(r.used_llm)
                self.assertEqual(r.answer,'SSID: Synthetic AP.')

    def test_expired_or_missing_ttl_is_not_admitted(self):
        for ttl in [-1,0,None,float('nan')]:
            self.facts['laptop.wifi']['expires_in_s']=ttl
            self.assertEqual(ledger('SSID?',list(self.facts),self.facts),[])
            r=self.run_answer('SSID hiện tại là {{F1}}.')
            self.assertFalse(r.used_llm)
            self.assertNotIn('Synthetic AP',r.answer)
            self.assertEqual(r.evidence_ids,())

    def test_unknown_channel_is_disclosed_and_not_rendered_as_channel_zero(self):
        self.facts['laptop.wifi']['value']['channel']=0
        r=produce_grounded_answer('SSID và kênh Wi-Fi?',list(self.facts),self.facts,self.renderers,
                                 lambda p: self.fail('Missing field must not be hidden by a model answer'))
        self.assertIn('Kênh: chưa đọc được',r.answer)
        self.assertEqual(r.calls,0)

    def test_projection_excludes_unrequested_fields_and_secrets(self):
        rows=ledger('SSID?',list(self.facts),self.facts)
        self.assertEqual([r['key'] for r in rows],['ssid'])
        rows=ledger('Wi-Fi thế nào?',list(self.facts),self.facts)
        self.assertNotIn('api_token',[r['key'] for r in rows])

    def test_multi_field_selection_must_not_silently_omit_channel(self):
        r=produce_grounded_answer('SSID và kênh Wi-Fi?',list(self.facts),self.facts,self.renderers,
                                 lambda p:json.dumps({'fact_ids':['F1']}))
        self.assertFalse(r.used_llm)
        self.assertIn('SSID: Synthetic AP.',r.answer)
        self.assertIn('Kênh: 36.',r.answer)
        self.assertEqual(r.calls,1)

    def test_broad_wifi_answer_cannot_dump_all_available_fields(self):
        self.facts['laptop.wifi']['value'].update(associated=True,interface='wifi0')
        r=produce_grounded_answer('Wi-Fi có vấn đề gì?',list(self.facts),self.facts,self.renderers,
                                 lambda p:json.dumps({'fact_ids':['F1','F2','F3','F4']}))
        self.assertFalse(r.used_llm)
        self.assertEqual(r.calls,1)

    def test_transport_uses_existing_verified_model_and_remaining_timeout(self):
        with patch('gateway_pilot.graph_v3.ollama_goal_model.http_json',side_effect=[
            {'model_info':{'general.parameter_count':2_000_000_000}},
            {'message':{'content':'{"fact_ids":["F1"]}'}}]) as http:
            m=OllamaGoalModel('qwen3:1.7b',timeout=60)
            m.complete_answer({'messages':[{},{}],'format':{'type':'object'}},timeout=.25)
        self.assertEqual(http.call_args.kwargs,{'timeout':.25,'max_bytes':65536})
        self.assertFalse(http.call_args.args[2]['think'])
        self.assertNotIn('tools',http.call_args.args[2])
