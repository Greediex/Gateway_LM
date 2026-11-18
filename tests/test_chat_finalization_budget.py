"""Slow inference must leave time to render fresh scoped evidence."""
import unittest
from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_chat import Model, choice
from tests.test_skill_chat_p0 import FullLaptopBackend


class ChatFinalizationBudgetTests(unittest.TestCase):
    def setUp(self):
        self.now=100.
        self.launcher=SkillLauncher(factory=lambda mode:composition(mode,backend=FullLaptopBackend(),clock=lambda:self.now),clock=lambda:self.now)

    def chat(self, last):
        def first(context):
            self.now+=80
            return choice(skills=['laptop.network.inspect'])
        self.model=Model([first,last]);self.model.timeout=90
        return SkillChat(self.launcher,model_factory=lambda:self.model,clock=lambda:self.now,max_elapsed_s=180).chat(
            'mạng nhà tôi có vấn đề gì không và cần giải quyết thế nào')

    def test_slow_final_rpc_preserves_fresh_measurements_and_truthful_reason(self):
        def slow(context):
            self.rpc_budget=context['inference_timeout_s']
            self.now+=self.rpc_budget
            raise TimeoutError('inference limit reached')
        r=self.chat(slow)
        self.assertLess(self.rpc_budget,30)
        self.assertEqual(r['stop_reason'],'model_timeout')
        self.assertEqual(r['case_status'],'PARTIAL')
        self.assertTrue(r['evidence_ids'])
        self.assertTrue(r['snapshot']['facts'])
        self.assertNotIn('hãy kiểm tra Ollama',r['answer'])
        self.assertNotIn('mang nha toi',r['answer'])
        self.assertIn('DNS',r['answer'])
        self.assertIn('Gateway',r['answer'])

    def test_noncompliant_model_cannot_promote_expired_facts_but_trace_retains_verification(self):
        def late(context):
            self.now+=110
            raise TimeoutError('late noncompliant model')
        r=self.chat(late)
        self.assertEqual(r['stop_reason'],'turn_deadline_exhausted')
        self.assertFalse(r['evidence_ids'])
        self.assertNotIn('hãy kiểm tra Ollama',r['answer'])
        self.assertTrue(r['timeline'])
        self.assertTrue(all(row['verified_at_execution'] for row in r['timeline']))
        self.assertTrue(all(row['status']=='NO_LONGER_VALID' for row in r['timeline']))

    def cached_dns(self):
        model=Model([choice(skills=['laptop.dns.inspect']),choice('answer',findings=['laptop.dns'])])
        model.timeout=90
        chat=SkillChat(self.launcher,model_factory=lambda:model,clock=lambda:self.now,max_elapsed_s=180)
        first=chat.chat('Kiểm tra DNS')
        return chat,model,first['session_id']

    def test_timeout_reuses_matching_fresh_facts_without_new_runs(self):
        chat,model,sid=self.cached_dns()
        def slow(context):
            self.now+=context['inference_timeout_s']
            raise TimeoutError()
        model.outputs=[slow]
        r=chat.chat('Kiểm tra DNS',session_id=sid)
        self.assertEqual(r['calls'],0)
        self.assertEqual(r['case_status'],'PARTIAL')
        self.assertIn('laptop.dns',r['snapshot']['facts'])
        self.assertTrue(r['evidence_ids'])
        self.assertIn('DNS',r['answer'])

    def test_model_initialization_also_reserves_cached_freshness(self):
        from unittest.mock import patch
        chat,model,sid=self.cached_dns()
        def slow_factory(*,timeout):
            self.assertLess(timeout,30)
            self.now+=timeout
            raise TimeoutError()
        chat.model_factory=slow_factory
        with patch('gateway_pilot.application.skill_chat.local_model',slow_factory):
            r=chat.chat('Kiểm tra DNS',session_id=sid)
        self.assertEqual(r['stop_reason'],'model_timeout')
        self.assertTrue(r['evidence_ids'])
        self.assertEqual(r['calls'],0)

    def test_goal_proposal_also_preserves_matching_cached_facts(self):
        chat,model,sid=self.cached_dns()
        def slow_proposal(question,catalog):
            self.assertLess(model.timeout,30)
            self.now+=model.timeout
            raise TimeoutError()
        model.propose_goals=slow_proposal
        r=chat.chat('Kiểm tra DNS và cần xử lý thế nào',session_id=sid)
        self.assertEqual(r['calls'],0)
        self.assertTrue(r['evidence_ids'])
        self.assertEqual(r['case_status'],'PARTIAL')
        self.assertEqual(model.timeout,90)

    def test_catalog_time_is_subtracted_from_cached_freshness(self):
        chat,model,sid=self.cached_dns()
        original=self.launcher.catalog
        def slow_catalog(*args,**kwargs):
            self.now+=10
            return original(*args,**kwargs)
        self.launcher.catalog=slow_catalog
        def slow(context):
            self.assertLess(context['inference_timeout_s'],20)
            self.now+=context['inference_timeout_s']
            raise TimeoutError()
        model.outputs=[slow]
        r=chat.chat('Kiểm tra DNS',session_id=sid)
        self.assertEqual(r['stop_reason'],'model_timeout')
        self.assertTrue(r['evidence_ids'])
        self.assertEqual(r['calls'],0)

    def test_cached_followup_reserves_session_expiry_too(self):
        chat,model,sid=self.cached_dns()
        self.launcher._get(sid)['session'].expires_at=self.now+10
        def slow(context):
            self.assertLess(context['inference_timeout_s'],10)
            self.now+=context['inference_timeout_s']
            raise TimeoutError()
        model.outputs=[slow]
        r=chat.chat('Kiểm tra DNS',session_id=sid)
        self.assertEqual(r['stop_reason'],'model_timeout')
        self.assertTrue(r['evidence_ids'])
