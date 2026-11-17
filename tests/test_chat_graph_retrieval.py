"""Graph relevance reaches the live model prompt, never the execution ACL."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gateway_pilot.application.skill_chat import validate_choice
from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
from gateway_pilot.skill_expansion.retrieval import SkillRetriever


class ChatGraphRetrievalTests(unittest.TestCase):
    def test_graph_only_candidate_is_visible_but_cannot_measure(self):
        def skill(sid, name):
            return SimpleNamespace(id=sid, name_vi=name, domain_name='', kind='',
                                   catalog_status='PROPOSED', priority='P1', runtime_status='NOT_BOUND')
        catalog = SimpleNamespace(skills={'seed':skill('seed', 'wifi'),
                                          'neighbor':skill('neighbor', 'memory')},
                                  relations=[SimpleNamespace(source='seed', target='neighbor',
                                      type='composes_with', weight=1., status='PROPOSED')])
        retriever = SkillRetriever(catalog)
        self.assertEqual([h.skill_id for h in retriever.search('wifi', include_proposed=True, graph_weight=0)], ['seed'])
        docs = [['seed','wifi','UNAVAILABLE','gateway'],
                ['neighbor','memory','UNAVAILABLE','gateway'],
                ['local.read','local read','READY','client']]
        rows = {r[0]:{'availability':r[2]} for r in docs}
        for selected in ['local.read', 'neighbor']:
            with self.subTest(selected=selected), patch('gateway_pilot.graph_v3.ollama_goal_model._skill_retriever', return_value=retriever), patch('gateway_pilot.graph_v3.ollama_goal_model.http_json', side_effect=[
                    {'model_info':{'general.parameter_count':4_022_468_096}},
                    {'message':{'content':json.dumps({'decision':'measure','ids':[selected]})}}]) as http:
                model = OllamaGoalModel('qwen3:4b', max_parameters=4_500_000_000)
                proposal = model.choose_skills('wifi', docs, {'findings':[]})
                payload = http.call_args.args[2]
                self.assertIn('neighbor:memory [UNAVAILABLE', payload['messages'][0]['content'])
                self.assertEqual(payload['format']['oneOf'][0]['properties']['ids']['items']['enum'], ['local.read'])
                hit = next(h for h in model.last_catalog['hits'] if h['skill_id']=='neighbor')
                self.assertEqual(hit['lexical'], 0)
                self.assertGreater(hit['graph'], 0)
                self.assertEqual(model.last_catalog['method'], 'bm25_graph')
                if selected=='neighbor':
                    with self.assertRaisesRegex(ValueError, 'unsupported_or_repeated_skill'):
                        validate_choice(proposal, rows, {}, [])
                else:
                    self.assertEqual(validate_choice(proposal, rows, {}, [])['skill_ids'], ['local.read'])

    def test_no_seed_does_not_expand_entire_graph(self):
        from gateway_pilot.graph_v3.ollama_goal_model import _skill_retriever
        self.assertEqual(_skill_retriever().search('zzzxqqqxy', include_proposed=True, graph_weight=.30), [])
