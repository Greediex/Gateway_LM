"""Catalog-driven chat: real Core/Verifier/RCA with a deterministic local model double."""
import copy
import unittest
from unittest.mock import patch

from gateway_pilot.application.skill_chat import SkillChat, validate_choice
from gateway_pilot.application.skill_launcher import SkillLauncher, SkillSessionError
from gateway_pilot.core import PlanError
from gateway_pilot.graph_v3.rca_agent import RCAAgent
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_launcher import FakeLaptopBackend


def choice(decision='measure', skills=(), findings=(), unavailable=()):
    return dict(decision=decision, skill_ids=list(skills), finding_ids=list(findings), unavailable_ids=list(unavailable))


class Model:
    local_only=True
    model='deterministic-local-double'
    def __init__(self, outputs):self.outputs=list(outputs);self.inputs=[]
    def choose_skills(self, request, catalog, context):
        self.inputs.append(copy.deepcopy((request,catalog,context)))
        result=self.outputs.pop(0)
        return result(context) if callable(result) else result


class SkillChatTests(unittest.TestCase):
    def setUp(self):
        self.now=100.0;self.entries=[]
        def factory(mode):
            e=composition(mode,backend=FakeLaptopBackend() if mode=='live' else None,clock=lambda:self.now)
            self.entries.append(e);return e
        self.launcher=SkillLauncher(factory=factory,clock=lambda:self.now)

    def chat(self, outputs, **options):
        model=Model(outputs)
        return SkillChat(self.launcher,model_factory=lambda:model,**options),model

    def test_multi_skill_then_rca_feedback_then_answer_and_followup_reuses_session(self):
        chat,model=self.chat([choice(skills=['laptop.wifi.inspect','laptop.route.inspect']),
                              choice('answer',findings=['laptop.wifi','laptop.route'])])
        r=chat.chat('Wi-Fi và gateway laptop thế nào?')
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertEqual([x['skill_id'] for x in r['skill_runs']],['laptop.wifi.inspect','laptop.route.inspect'])
        self.assertEqual(r['calls'],3)
        self.assertEqual(len(model.inputs[0][1]),126)
        self.assertTrue(any(row[0]=='SK13' and row[2]=='UNAVAILABLE' for row in model.inputs[0][1]))
        self.assertTrue(model.inputs[1][2]['rca'])
        self.assertFalse(model.inputs[1][2]['missing_goals'])
        self.assertTrue(r['evidence_ids']);self.assertIsNone(r['diagnosis'])
        model.outputs=[choice('answer',findings=['laptop.route'])]
        follow=chat.chat('Gateway là gì?',session_id=r['session_id'])
        self.assertEqual(follow['calls'],0)
        self.assertIn('Gateway:',follow['answer']);self.assertNotIn('signal',follow['answer'])
        self.assertEqual(model.inputs[-1][2]['previous_question'],'Wi-Fi và gateway laptop thế nào?')

    def test_adaptive_second_selection_receives_first_verified_evidence(self):
        chat,model=self.chat([choice(skills=['laptop.route.inspect']),
                              choice(skills=['laptop.wifi.inspect']),choice('answer',findings=['laptop.wifi'])])
        result=chat.chat('Tại sao Wi-Fi laptop có vấn đề?')
        self.assertEqual(len(result['skill_runs']),2)
        self.assertTrue(model.inputs[1][2]['findings'])
        self.assertEqual(model.inputs[1][2]['attempted'],['laptop.route.inspect'])
        self.assertEqual(result['calls'],3)
        self.assertNotIn('Gateway:',result['answer'])

    def test_unavailable_catalog_skill_explains_without_measurement_or_replay(self):
        chat,_=self.chat([choice('clarify',unavailable=['B04'])])
        r=chat.chat('Đọc SNR Wi-Fi')
        self.assertEqual((r['calls'],r['case_status']),(0,'UNAVAILABLE'))
        self.assertIn('REQUIRES_RSSI_AND_SNR',r['answer'])
        self.assertEqual(r['evidence_ids'],[])
        self.assertEqual(r['mode'],'linux_live')

    def test_write_and_custom_targets_are_zero_calls_without_model(self):
        chat,model=self.chat([])
        for text in ('reboot router','Ping 203.0.113.8','Đổi mật khẩu wifi'):
            result=chat.chat(text)
            self.assertEqual(result['calls'],0)
            self.assertEqual(result['skill_runs'],[])
        self.assertEqual(model.inputs,[])

    def test_invalid_or_unavailable_or_arbitrary_model_ids_never_execute(self):
        for output in ({'command':'reboot'},choice(skills=['B04']),choice(skills=['os.system']),
                       choice('answer',findings=['invented']),choice(skills=['laptop.route.inspect'] , unavailable=['SK01']),
                       choice(skills=['laptop.route.inspect','laptop.route.inspect'])):
            chat,_=self.chat([output]);r=chat.chat('Kiểm tra laptop')
            self.assertEqual(r['calls'],0)
            self.assertEqual(r['stop_reason'],'invalid_model_proposal')

    def test_model_cannot_present_signal_percent_as_completed_snr_request(self):
        chat,_=self.chat([choice(skills=['laptop.wifi.inspect']),choice('answer',findings=['laptop.wifi'])])
        r=chat.chat('Đọc SNR Wi-Fi laptop')
        self.assertEqual(r['case_status'],'PARTIAL')
        self.assertIn('B04',r['unavailable_skills'])
        self.assertIn('REQUIRES_RSSI_AND_SNR',r['answer'])

    def test_model_outage_does_not_silently_use_rules(self):
        def unavailable():raise OSError('offline')
        r=SkillChat(self.launcher,model_factory=unavailable).chat('Kiểm tra Wi-Fi')
        self.assertEqual(r['calls'],0);self.assertFalse(r['llm_advisor_ready'])
        self.assertEqual(r['stop_reason'],'model_unavailable')

    def test_repeated_proposal_and_round_budget_stop(self):
        chat,_=self.chat([choice(skills=['laptop.route.inspect']),choice(skills=['laptop.route.inspect'])])
        r=chat.chat('Kiểm tra route');self.assertEqual(r['calls'],2)
        self.assertEqual(r['stop_reason'],'invalid_model_proposal')
        chat,_=self.chat([choice(skills=['laptop.route.inspect'])],max_rounds=1)
        r=chat.chat('Kiểm tra route');self.assertEqual(r['calls'],0)
        self.assertEqual(r['stop_reason'],'round_budget_exhausted')

    def test_evidence_expiring_during_inference_requires_verified_refresh(self):
        def late(context):
            self.now+=31
            return choice('answer',findings=['laptop.route'])
        chat,_=self.chat([choice(skills=['laptop.route.inspect']),late])
        r=chat.chat('Gateway là gì?')
        self.assertEqual(r['recovery_attempts'],1)
        self.assertTrue(r['evidence_ids'])
        self.assertIn('Gateway:',r['answer'])
        self.assertGreater(r['snapshot']['facts']['laptop.route']['expires_in_s'],0)

    def test_context_acl_and_session_changes_fail_closed_after_inference(self):
        for mutation in ('context','permissions','claim','closed'):
            def mutate(context):
                e=self.entries[-1]
                if mutation=='context':e['backend'].bssid='changed'
                elif mutation=='permissions':e['runtime'].permissions=frozenset()
                elif mutation=='claim':e['runtime'].registry.workflows.clear()
                else:e['session'].close()
                return choice('answer',findings=['laptop.route'])
            chat,_=self.chat([choice(skills=['laptop.route.inspect']),mutate])
            with self.assertRaisesRegex(SkillSessionError,'session_expired'):
                chat.chat('Gateway là gì?')

    def test_capability_loss_revokes_cached_facts_and_session_source_is_fixed(self):
        def revoke(context):
            self.entries[-1]['backend'].supports=lambda *a:False
            return choice('answer',findings=['laptop.route'])
        chat,_=self.chat([choice(skills=['laptop.route.inspect']),revoke])
        result=chat.chat('Gateway là gì?')
        self.assertEqual(result['evidence_ids'],[])
        sid=self.launcher.create_session('replay')['session_id']
        with self.assertRaisesRegex(ValueError,'live_session'):chat.chat('test',session_id=sid)

    def test_rca_reuses_same_runner_and_rejects_another_registry(self):
        e=composition('live',backend=FakeLaptopBackend(),clock=lambda:self.now)
        runner=e['session'].runner
        agent=RCAAgent(e['runtime'].registry,method='bm25')
        before=agent.assess_session(e['session'],workflows=['LAPTOP-CONNECTIVITY'])
        self.assertEqual(before[0]['decision'],'INCONCLUSIVE')
        e['session'].execute(['laptop.route'])
        after=agent.assess_session(e['session'],workflows=['LAPTOP-ROUTE'])
        self.assertEqual(after[0]['decision'],'HEALTHY_OBSERVED')
        self.assertIs(runner,e['session'].runner);self.assertEqual(runner.calls,2)
        e['backend'].supports=lambda *args:False
        revoked=agent.assess_session(e['session'],workflows=['LAPTOP-ROUTE'])
        self.assertEqual(revoked[0]['decision'],'INCONCLUSIVE')
        other=composition('live',backend=FakeLaptopBackend(),clock=lambda:self.now)
        with self.assertRaises(PlanError):agent.assess_session(other['session'],workflows=['LAPTOP-ROUTE'])

class SkillModelAdapterTests(unittest.TestCase):
    def test_local_model_sends_entire_catalog_and_finite_runnable_schema(self):
        from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
        show={'model_info':{'general.parameter_count':1_700_000_000}}
        output=choice(skills=['laptop.route.inspect'])
        with patch('gateway_pilot.graph_v3.ollama_goal_model.http_json',side_effect=[show,{'message':{'content':__import__('json').dumps({'decision':'measure','ids':['laptop.route.inspect']})}}]) as http:
            model=OllamaGoalModel('qwen3:1.7b')
            docs=[['A'+str(i),'Design Skill '+str(i),'UNAVAILABLE','gateway'] for i in range(120)]
            docs.append(['laptop.route.inspect','Route','READY','client'])
            self.assertEqual(model.choose_skills('Gateway?',docs,{'findings':[]}),output)
            payload=http.call_args.args[2]
            self.assertIn('A119:Design Skill 119',payload['messages'][0]['content'])
            self.assertIn('laptop.route.inspect:Route [READY, scope=client]',payload['messages'][0]['content'])
            self.assertEqual(payload['format']['oneOf'][0]['properties']['ids']['items']['enum'],['laptop.route.inspect'])
            self.assertFalse(any(b['properties']['decision']['const']=='answer' for b in payload['format']['oneOf']))
            self.assertFalse(payload['think'])

    def test_completed_selected_skill_does_not_lock_remaining_intent_or_cached_facts(self):
        from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
        import json
        show={'model_info':{'general.parameter_count':1_700_000_000}}
        output={'decision':'measure','ids':['laptop.wifi.inspect']}
        with patch('gateway_pilot.graph_v3.ollama_goal_model.http_json',side_effect=[show,{'message':{'content':json.dumps(output)}}]) as http:
            model=OllamaGoalModel('qwen3:1.7b')
            docs=[['laptop.dns.inspect','DNS','READY','client'],['laptop.wifi.inspect','Wi-Fi','READY','client'],['B04','RSSI/SNR','UNAVAILABLE','client']]
            context={'attempted':['laptop.dns.inspect'],'selected_measurements_complete':True,
                     'findings':[{'id':'laptop.dns'},{'id':'laptop.wifi'}]}
            self.assertEqual(model.choose_skills('DNS và Wi-Fi',docs,context)['skill_ids'],['laptop.wifi.inspect'])
            branches=http.call_args.args[2]['format']['oneOf']
            self.assertEqual({b['properties']['decision']['const'] for b in branches},{'measure','answer','clarify'})
            answer=next(b for b in branches if b['properties']['decision']['const']=='answer')
            self.assertIn('laptop.wifi',answer['properties']['ids']['items']['enum'])

    def test_diagnostic_contract_pin_tampering_is_rejected(self):
        from gateway_pilot.skill_expansion import deployment as module
        original=module.read_json
        def tamper(path,**kwargs):
            value=original(path,**kwargs)
            if path.name=='live.diagnostics.json':value['claims'][0]['requires'][0]['value']='tampered'
            return value
        with patch.object(module,'read_json',side_effect=tamper),self.assertRaisesRegex(PlanError,'diagnostics_pin'):
            composition('live',backend=FakeLaptopBackend())
