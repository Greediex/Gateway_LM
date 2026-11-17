"""P0 regression cases exercise the existing Core with synthetic laptop telemetry."""
import threading
import unittest
from unittest.mock import patch

from gateway_pilot.adapters.read_backends import observations
from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher, SkillSessionError
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_chat import Model, choice
from tests.test_skill_launcher import FakeLaptopBackend


class FullLaptopBackend(FakeLaptopBackend):
    def __init__(self):
        super().__init__()
        self._tools.update(ping='synthetic',resolvectl='synthetic')
        self.fail=set()

    def route(self):
        return {**super().route(),'resolver_fingerprint':'a'*64}

    def sample(self, function, arguments, context):
        fid=function['function_id']
        if fid in self.fail:
            self.calls+=1
            raise TimeoutError('synthetic timeout')
        if fid=='laptop.dns':
            value={'query':'example.com','resolved':True,'interface':self.interface}
        elif fid in {'laptop.gateway_probe','laptop.internet_probe'}:
            value={'destination':'192.0.2.1' if fid=='laptop.gateway_probe' else '1.1.1.1',
                   'interface':self.interface,'sent':4,'received':4,'loss_pct':0,'latency_ms':2}
        else:
            return super().sample(function,arguments,context)
        self.calls+=1
        return observations(function,{next(iter(function['outputs'])):value},self.source,context)


class P0ChatTests(unittest.TestCase):
    def setUp(self):
        self.now=100.0;self.entries=[]
        def factory(mode):
            e=composition(mode,backend=FullLaptopBackend(),clock=lambda:self.now)
            self.entries.append(e);return e
        self.launcher=SkillLauncher(factory=factory,clock=lambda:self.now)

    def chat(self, outputs, **kwargs):
        model=Model(outputs)
        return SkillChat(self.launcher,model_factory=lambda:model,**kwargs),model

    def test_multi_intent_cannot_finish_after_dns_only(self):
        chat,_=self.chat([choice(skills=['laptop.dns.inspect']),
                          choice('answer',findings=['laptop.dns']),
                          choice('answer',findings=['laptop.dns'])])
        r=chat.chat('Kiểm tra DNS và Wi-Fi laptop')
        self.assertEqual(r['case_status'],'PARTIAL')
        self.assertIn('laptop.wifi',r['coverage']['missing_ports'])
        self.assertIn('Wi-Fi',r['answer'])

    def test_unknown_second_obligation_is_not_hidden_by_known_dns_result(self):
        for request in ('Kiểm tra DNS và mức pin laptop',
                        'Kiểm tra DNS và nhiệt độ CPU laptop'):
            with self.subTest(request=request):
                chat,_=self.chat([choice(skills=['laptop.dns.inspect']),
                                  choice('answer',findings=['laptop.dns'])])
                r=chat.chat(request)
                self.assertEqual(r['case_status'],'PARTIAL')
                self.assertFalse(r['coverage']['complete'])
                self.assertTrue(r['coverage']['unconfirmed_parts'])
                self.assertIn('Chưa xác minh đầy đủ',r['answer'])
                self.launcher.close(r['session_id'])

    def test_english_remote_ap_scope_never_uses_laptop_dns(self):
        chat,_=self.chat([choice(skills=['laptop.dns.inspect'])])
        r=chat.chat('Check DNS on AP')
        self.assertEqual(r['calls'],0)
        self.assertFalse(r['coverage']['scope_confirmed'])
        self.assertEqual(r['stop_reason'],'custom_target_not_supported')

    def test_default_model_startup_receives_remaining_turn_budget(self):
        model=Model([choice(skills=['laptop.dns.inspect']),
                     choice('answer',findings=['laptop.dns'])])
        with patch('gateway_pilot.application.skill_chat.OllamaGoalModel',return_value=model) as ctor:
            chat=SkillChat(self.launcher,max_elapsed_s=5,clock=lambda:self.now)
            chat.chat('DNS laptop')
        self.assertGreater(ctor.call_args.kwargs['timeout'],0)
        self.assertLessEqual(ctor.call_args.kwargs['timeout'],5)

    def test_wifi_fields_requested_are_rendered_from_verified_values(self):
        chat,_=self.chat([choice(skills=['laptop.wifi.inspect']),
                          choice('answer',findings=['laptop.wifi'])])
        r=chat.chat('SSID laptop và kênh Wi-Fi hiện tại là gì?')
        value=r['snapshot']['facts']['laptop.wifi']['value']
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertIn(value['ssid'],r['answer'])
        self.assertIn('Kênh: '+str(value['channel']),r['answer'])

    def test_model_dependency_finding_does_not_expand_dns_answer_scope(self):
        chat,_=self.chat([choice(skills=['laptop.dns.inspect']),
                          choice('answer',findings=['laptop.dns','laptop.route'])])
        r=chat.chat('Kiểm tra DNS trên laptop')
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertIn('laptop.route',r['snapshot']['facts'])
        self.assertEqual(r['evidence_ids'],[r['snapshot']['facts']['laptop.dns']['evidence_id']])
        self.assertNotIn('Gateway:',r['answer'])

    def test_degraded_action_does_not_advertise_unavailable_optional_outputs(self):
        launcher=SkillLauncher(factory=lambda mode:composition(mode,backend=FakeLaptopBackend(),
                                                              clock=lambda:self.now),clock=lambda:self.now)
        model=Model([choice(skills=['laptop.wifi.inspect']),choice('answer',findings=['laptop.wifi'])])
        r=SkillChat(launcher,model_factory=lambda:model).chat('Wi-Fi laptop')
        outputs=model.inputs[0][2]['runnable_outputs']['laptop.network.inspect']
        self.assertIn('laptop.wifi',outputs)
        self.assertNotIn('laptop.dns',outputs)
        self.assertNotIn('laptop.gateway_probe',outputs)
        self.assertNotIn('laptop.internet_probe',outputs)
        launcher.close(r['session_id'])

    def test_multi_intent_feedback_allows_second_skill_and_completes_answer_from_facts(self):
        chat,model=self.chat([choice(skills=['laptop.dns.inspect']),choice('answer',findings=['laptop.dns']),
                              choice(skills=['laptop.wifi.inspect']),choice('answer',findings=['laptop.dns'])])
        r=chat.chat('Kiểm tra DNS và Wi-Fi laptop')
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertTrue(r['coverage']['complete'])
        self.assertIn('Wi-Fi',r['answer']);self.assertIn('DNS',r['answer'])
        self.assertEqual(r['calls'],4)
        self.assertIn('laptop.wifi',model.inputs[2][2]['missing_goals'])
        self.assertIn('laptop.dns',model.inputs[0][2]['runnable_outputs']['laptop.dns.inspect'])
        self.assertNotIn('B04',model.inputs[0][2]['runnable_outputs'])
        self.assertEqual(model.inputs[2][2]['missing_goal_actions']['laptop.wifi'][0],'laptop.wifi.inspect')
        self.assertNotIn('selected_measurements_complete',model.inputs[2][2])

    def test_expired_answer_is_refreshed_once_through_same_session(self):
        def late(context):
            self.now+=31
            return choice('answer',findings=['laptop.dns'])
        chat,_=self.chat([choice(skills=['laptop.dns.inspect']),late])
        r=chat.chat('Kiểm tra DNS')
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertEqual(r['recovery_attempts'],1)
        self.assertTrue(r['evidence_ids']);self.assertTrue(r['snapshot']['facts']['laptop.dns']['expires_in_s']>0)
        self.assertEqual(len(self.entries),1)

    def test_invalid_proposal_can_be_corrected_without_tool_bypass(self):
        chat,_=self.chat([{'command':'arbitrary'},choice(skills=['laptop.wifi.inspect']),
                          choice('answer',findings=['laptop.wifi'])])
        r=chat.chat('Wi-Fi laptop thế nào?')
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertEqual(r['proposal_rejections'],1)
        self.assertEqual(r['calls'],3)

    def test_no_progress_stops_with_missing_information(self):
        chat,_=self.chat([choice('answer'),choice('answer')])
        r=chat.chat('Kiểm tra DNS')
        self.assertEqual(r['calls'],0)
        self.assertIn(r['stop_reason'],{'no_progress','incomplete_coverage','needs_clarification'})
        self.assertFalse(r['coverage']['complete'])

    def test_model_failure_after_measurement_preserves_usable_facts(self):
        def timeout(context):raise TimeoutError('synthetic model timeout')
        chat,_=self.chat([choice(skills=['laptop.wifi.inspect']),timeout])
        r=chat.chat('Wi-Fi và DNS laptop')
        self.assertEqual(r['case_status'],'PARTIAL')
        self.assertIn('Wi-Fi',r['answer']);self.assertIn('DNS',r['answer'])
        self.assertTrue(r['evidence_ids'])
        self.assertEqual(r['stop_reason'],'model_unavailable')

    def test_refresh_failure_never_exports_expired_proof_or_raises_budget(self):
        def late(context):
            self.now+=31
            self.entries[-1]['backend'].fail.add('laptop.dns')
            return choice('answer',findings=['laptop.dns'])
        chat,_=self.chat([choice(skills=['laptop.dns.inspect']),late])
        r=chat.chat('Kiểm tra DNS')
        self.assertNotEqual(r['case_status'],'MEASURED')
        self.assertEqual(r['recovery_attempts'],1)
        self.assertNotIn('laptop.dns',r['snapshot']['facts'])
        fresh_ids={r['id'] for r in r['evidence']}
        self.assertTrue(set(r['evidence_ids'])<=fresh_ids)
        for assessment in r['rca_assessments']:
            self.assertTrue(set(assessment['evidence_ids'])<=fresh_ids)

    def test_session_change_during_inference_never_rereads_another_context(self):
        def change(context):
            self.entries[-1]['backend'].bssid='changed'
            return choice('answer',findings=['laptop.wifi'])
        chat,_=self.chat([choice(skills=['laptop.wifi.inspect']),change])
        with self.assertRaisesRegex(SkillSessionError,'session_expired'):
            chat.chat('Wi-Fi laptop')
        self.assertEqual(self.entries[-1]['session'].runner.calls,3)

    def test_same_session_and_model_concurrency_are_rejected_without_queue(self):
        from concurrent.futures import ThreadPoolExecutor
        entered,release=threading.Event(),threading.Event()
        def wait(context):
            entered.set();self.assertTrue(release.wait(5))
            return choice('clarify')
        chat,_=self.chat([wait])
        sid=self.launcher.create_session('live')['session_id']
        with ThreadPoolExecutor(2) as pool:
            active=pool.submit(chat.chat,'Kiểm tra Wi-Fi',session_id=sid)
            try:
                self.assertTrue(entered.wait(5))
                with self.assertRaisesRegex(SkillSessionError,'session_busy'):
                    chat.chat('DNS',session_id=sid)
                with self.assertRaisesRegex(SkillSessionError,'model_busy'):
                    chat.chat('DNS')
            finally:release.set()
            active.result(5)
        self.assertEqual(len(self.launcher._sessions),1)

    def test_closed_session_cancels_pending_model_before_tools(self):
        from concurrent.futures import ThreadPoolExecutor
        entered,release=threading.Event(),threading.Event()
        def wait(context):
            entered.set();release.wait(5)
            return choice(skills=['laptop.wifi.inspect'])
        chat,_=self.chat([wait])
        sid=self.launcher.create_session('live')['session_id']
        with ThreadPoolExecutor(1) as pool:
            active=pool.submit(chat.chat,'Wi-Fi laptop',session_id=sid)
            try:
                self.assertTrue(entered.wait(5));self.launcher.close(sid)
            finally:release.set()
            with self.assertRaisesRegex(SkillSessionError,'session_expired'):active.result(5)
        self.assertEqual(self.entries[-1]['session'].runner.calls,0)

    def test_turn_deadline_stops_before_post_timeout_measurement(self):
        def late(context):
            self.now+=6
            return choice(skills=['laptop.wifi.inspect'])
        chat,_=self.chat([late],clock=lambda:self.now,max_elapsed_s=5)
        r=chat.chat('Wi-Fi laptop')
        self.assertEqual((r['stop_reason'],r['calls']),('turn_deadline_exhausted',0))
        self.assertGreaterEqual(r['timings_ms']['inference'],6000)

    def test_model_response_size_is_bounded_before_json_parse(self):
        from unittest.mock import patch,MagicMock
        from gateway_pilot.run import http_json
        response=MagicMock()
        response.__enter__.return_value=response
        response.read.return_value=b'x'*1025
        with patch('gateway_pilot.run.urllib.request.urlopen',return_value=response):
            with self.assertRaisesRegex(ValueError,'response_too_large'):
                http_json('http://127.0.0.1:11434','chat',max_bytes=1024)
        response.read.assert_called_once_with(1025)

    def test_identity_part_is_not_lost_when_another_skill_already_produced_it(self):
        chat,_=self.chat([choice(skills=['laptop.dns.inspect']),choice('answer',findings=['laptop.dns'])])
        r=chat.chat('Kiểm tra DNS và định danh laptop')
        self.assertEqual(r['case_status'],'MEASURED')
        self.assertIn('client.identity',r['coverage']['requested_ports'])
        self.assertIn('định danh',r['answer'])
        self.assertEqual(r['calls'],3)

    def test_proposal_rpc_obeys_remaining_timeout_and_response_byte_limit(self):
        import json
        from unittest.mock import patch
        from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
        with patch('gateway_pilot.graph_v3.ollama_goal_model.http_json',side_effect=[
            {'model_info':{'general.parameter_count':1_700_000_000}},
            {'message':{'content':json.dumps({'decision':'clarify','ids':[]})}}]) as http:
            model=OllamaGoalModel('qwen3:1.7b',timeout=60)
            model.choose_skills('Kiểm tra',[['laptop.wifi.inspect','WiFi','READY','client']],
                                {'findings':[],'inference_timeout_s':.25})
            self.assertEqual(http.call_args.kwargs['timeout'],.25)
            self.assertEqual(http.call_args.kwargs['max_bytes'],65536)

    def test_router_owned_query_is_not_answered_with_laptop_telemetry(self):
        chat,model=self.chat([])
        for question in ('Kiểm tra DNS của router','DNS router thế nào?','Xem Wi-Fi của AP','IP của thiết bị khác'):
            r=chat.chat(question)
            self.assertEqual(r['calls'],0)
            self.assertFalse(r['coverage']['complete'])
            self.assertFalse(r['coverage']['scope_confirmed'])
            self.assertEqual(r['stop_reason'],'custom_target_not_supported')
        self.assertEqual(model.inputs,[])
