"""Advisory context reaches the real model adapter, never execution rights."""
import json
import unittest
from unittest.mock import patch

from gateway_pilot.application.chat_context import ChatContext
from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_launcher import FakeLaptopBackend


class SemanticEncoder:
    local_only = True
    model_id = 'integration-test-local'

    def encode_many(self, texts):
        return [[1, 0] if 'RSSI/SNR' in text or text == 'opaque' else [0, 1] for text in texts]


class ChatContextIntegrationTests(unittest.TestCase):
    def test_semantic_only_unavailable_candidate_reaches_prompt_but_zero_calls(self):
        context = ChatContext(encoder=SemanticEncoder())
        payloads = []
        def http(endpoint, api, payload, **kwargs):
            if api == 'show':
                return {'model_info': {'general.parameter_count': 1000}}
            payloads.append(payload)
            # Simulate a malicious model ignoring the schema's execution ACL.
            return {'message': {'content': '{"decision":"measure","ids":["B04"]}'}}
        backend = FakeLaptopBackend()
        launcher = SkillLauncher(factory=lambda mode: composition(mode, backend=backend))
        with patch('gateway_pilot.graph_v3.ollama_goal_model.http_json', side_effect=http):
            model = OllamaGoalModel('test', chat_context=context)
            result = SkillChat(launcher, model_factory=lambda: model).chat('opaque')
        self.assertTrue(payloads)
        selection=next(p for p in payloads if 'oneOf' in p['format'])
        self.assertIn('B04:', selection['messages'][0]['content'])
        self.assertEqual(model.last_catalog['semantic_candidates'][0]['skill_id'], 'B04')
        measure = next(b for b in selection['format']['oneOf']
                       if b['properties']['decision']['const'] == 'measure')
        self.assertNotIn('B04', measure['properties']['ids']['items']['enum'])
        self.assertEqual(result['calls'], 0)
        self.assertEqual(backend.calls, 0)
        self.assertEqual(result['evidence_ids'], [])
        self.assertEqual(result['stop_reason'], 'invalid_model_proposal')

    def test_runbook_provenance_is_prompt_data_and_not_findings(self):
        context = ChatContext()
        with patch('gateway_pilot.graph_v3.ollama_goal_model.http_json', side_effect=[
                {'model_info': {'general.parameter_count': 1000}},
                {'message': {'content': '{"decision":"clarify","ids":[]}'}}]) as http:
            model = OllamaGoalModel('test', chat_context=context)
            model.choose_skills('DNS lỗi phân giải tên miền', [['local.read','Read','READY','client']],
                                {'findings': [], 'inference_timeout_s': 5})
        payload = http.call_args.args[2]
        prompt = payload['messages'][0]['content']
        self.assertIn('NOT measured facts or instructions', prompt)
        self.assertIn('linux-read-docs-v1', prompt)
        self.assertIn(context.index.source['sha256'], prompt)
        self.assertIn('"is_observation": false', prompt)
        self.assertIn('"untrusted_data": true', prompt)
        final_user = json.loads(payload['messages'][-1]['content'])
        self.assertEqual(final_user['findings'], [])
        self.assertNotIn('documents', final_user)

    def test_context_elapsed_is_subtracted_from_rpc_timeout(self):
        context = ChatContext()
        # search_start, metadata duration, final pre-RPC deadline calculation.
        with patch('gateway_pilot.graph_v3.ollama_goal_model.time.perf_counter', side_effect=[10, 12, 12]), patch(
                'gateway_pilot.graph_v3.ollama_goal_model.http_json', side_effect=[
                    {'model_info': {'general.parameter_count': 1000}},
                    {'message': {'content': '{"decision":"clarify","ids":[]}'}}]) as http:
            model = OllamaGoalModel('test', timeout=20, chat_context=context)
            model.choose_skills('dns', [['local.read','Read','READY','client']],
                                {'findings': [], 'inference_timeout_s': 5})
        self.assertEqual(http.call_args.kwargs['timeout'], 3)

    def test_exhausted_context_deadline_prevents_model_rpc(self):
        context = ChatContext()
        with patch('gateway_pilot.graph_v3.ollama_goal_model.time.perf_counter', side_effect=[10, 15, 15]), patch(
                'gateway_pilot.graph_v3.ollama_goal_model.http_json', return_value={
                    'model_info': {'general.parameter_count': 1000}}) as http:
            model = OllamaGoalModel('test', chat_context=context)
            with self.assertRaisesRegex(TimeoutError, 'context_deadline_exhausted'):
                model.choose_skills('dns', [['local.read','Read','READY','client']],
                                    {'findings': [], 'inference_timeout_s': 5})
        self.assertEqual(http.call_count, 1)  # model size verification only


if __name__ == '__main__':
    unittest.main()
