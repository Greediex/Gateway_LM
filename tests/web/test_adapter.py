"""Isolated contract tests for the web adapter (not claims about Gateway_LM tests)."""
import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

ADAPTER = Path(__file__).resolve().parents[2] / 'web_gateway' / 'server.py'


class WebAdapterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        repo = Path(self.tmp.name)
        (repo / 'data').mkdir()
        fixture = {'id':'GLM-21-1', 'template':'internet_unverified', 'split':'test',
                   'workflow':'WF-INTERNET', 'request':'Laptop An có Wi-Fi, không có mạng',
                   'world':{'wan.status':{'link_up': False}},
                   'target':{'scope':'client','selector':'laptop-an'},'capabilities':['wan.status']}
        (repo/'data'/'cases.json').write_text(json.dumps([fixture]),encoding='utf8')
        self.repo = repo
        self.env = patch.dict(os.environ, {'GATEWAY_LM_REPO':str(repo)})
        self.env.start()
        spec = importlib.util.spec_from_file_location('web_gateway_server_test', ADAPTER)
        self.srv = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.srv)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_config_reads_actual_fixture(self):
        c=self.srv.fixture_summaries()
        self.assertEqual(len(c),1)
        self.assertEqual(c[0]['template'],'internet_unverified')
        self.assertEqual(c[0]['id'],'GLM-21-1')

    def test_chat_validation(self):
        for bad in [{}, {'message':' '}, {'message':'a','fixture_id':'unknown'},
                    {'message':'a','method':'unsafe'}, {'message':'x'*2001}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.srv.analyze(bad)

    def test_chat_calls_real_import_contract(self):
        fake_workflow=types.ModuleType('gateway_pilot.workflow')
        fake_rag=types.ModuleType('gateway_pilot.rag')
        class Registry:
            functions={'wan.status':types.SimpleNamespace(scope='gateway')}
        seen={}
        def diagnose(message,replay,**kwargs):
            seen.update(message=message,replay=replay,kwargs=kwargs)
            return {
                'terminal':{'response':'WAN mất liên kết.','action':'FINISH',
                            'diagnosis':'wan_link_down','evidence_ids':['e1']},
                'case_status':'RESOLVED','workflow':'WF-018',
                'target':{'scope':'gateway','id':'gateway_01'},
                'decision_source':'core_rules',
                'graph':{'calls':1,'repairs':0,
                         'executed':[{'function_id':'wan.status','arguments':{}}],
                         'evidence':[{'id':'e1','function_id':'wan.status','port':'wan.status',
                                      'value':{'link_up':False},'status':'OK'}],
                         'events':[{'node':'wan.status','state':'SUCCEEDED','reason':'verified'}],
                         'stages':[{'goal':'wan.status','evidence_id':'e1'}],
                         'plans':[], 'retrievals':[]}
            }
        fake_workflow.diagnose=diagnose
        fake_workflow.workflow_registry=lambda:Registry()
        fake_workflow.replay_from_fixture=lambda fixture,registry:{'capabilities':fixture['capabilities'],'world':fixture['world']}
        fake_rag.DEFAULT_CATALOG=Path('none')
        fake_rag.REPLAY_PRODUCT='test'
        fake_rag.REPLAY_FIRMWARE='simulated'
        class RunbookIndex:
            def __init__(self,p): pass
            def retrieve(self,*args,**kwargs): return {'documents':[]}
        fake_rag.RunbookIndex=RunbookIndex
        packages={'gateway_pilot':types.ModuleType('gateway_pilot'),
                  'gateway_pilot.workflow':fake_workflow,'gateway_pilot.rag':fake_rag}
        with patch.dict(sys.modules,packages):
            response=self.srv.analyze({'message':'Tại sao WAN mất mạng?',
                                       'fixture_id':'GLM-21-1', 'method':'bm25'})
        self.assertEqual(response['diagnosis'],'wan_link_down')
        self.assertEqual(response['calls'],1)
        self.assertEqual(response['timeline'][0]['value'],{'link_up':False})
        self.assertTrue(response['notice'].startswith('Kết quả dựa trên synthetic'))
        self.assertEqual(seen['message'],'Tại sao WAN mất mạng?')
        self.assertIsNone(seen['kwargs']['advisor'])
        self.assertEqual(seen['replay']['capabilities'],['wan.status'])
        self.assertNotIn('gold',seen['replay'])


if __name__=='__main__': unittest.main()
