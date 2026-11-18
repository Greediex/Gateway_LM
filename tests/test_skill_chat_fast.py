"""Fast chat routing: phrase/graph route without LLM; ambiguous asks <=1 LLM call."""
import unittest

from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_chat import Model, choice
from tests.test_skill_launcher import FakeLaptopBackend


class NoModel:
    calls = 0
    def __call__(self):
        NoModel.calls += 1
        raise AssertionError('LLM must not be constructed on a direct route')


class FastChatTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.launcher = SkillLauncher(
            factory=lambda m: composition(m, backend=FakeLaptopBackend(), clock=lambda: self.now),
            clock=lambda: self.now)
        NoModel.calls = 0

    def fast(self, factory):
        return SkillChat(self.launcher, model_factory=factory, fast=True, clock=lambda: self.now)

    def test_phrase_route_measures_without_llm(self):
        r = self.fast(NoModel()).chat('Wi-Fi laptop có vấn đề gì?')
        self.assertEqual((r['stop_reason'], r['model_calls'], NoModel.calls), ('direct_route', 0, 0))
        self.assertEqual(r['routing']['plan'], ['laptop.wifi.inspect'])
        self.assertEqual(r['case_status'], 'MEASURED')
        self.assertTrue(r['evidence_ids'])
        self.assertFalse(r['answer_synthesis']['used_llm'])

    def test_graph_route_uses_retrieval_top_hit_only_if_runnable(self):
        r = self.fast(NoModel()).chat('Xác định client đích')
        self.assertEqual(r['routing']['method'], 'graph')
        self.assertEqual(r['routing']['plan'], ['SK01'])
        self.assertEqual(NoModel.calls, 0)

    def test_followup_reuses_fresh_evidence_with_zero_calls(self):
        chat = self.fast(NoModel())
        first = chat.chat('Wi-Fi laptop có vấn đề gì?')
        again = chat.chat('Wi-Fi laptop thế nào?', session_id=first['session_id'])
        self.assertEqual((again['calls'], again['routing']['plan'], NoModel.calls), (0, [], 0))

    def test_ambiguous_request_makes_at_most_one_llm_call(self):
        model = Model([choice(skills=['laptop.route.inspect']), choice('answer', findings=['laptop.route'])])
        r = self.fast(lambda: model).chat('Mạng hôm nay ra sao?')
        self.assertEqual(len(model.inputs), 1)
        self.assertEqual(r['model_calls'], 1)
        self.assertFalse(r['answer_synthesis']['used_llm'])
        self.assertFalse(r['routing']['direct'])

    def test_write_and_custom_target_never_route_or_call_llm(self):
        chat = self.fast(NoModel())
        for text in ('Xóa cấu hình DNS của router', 'Ping 203.0.113.8'):
            r = chat.chat(text)
            self.assertEqual((r['calls'], NoModel.calls), (0, 0))
            self.assertIsNone(r['routing']['plan'])

    def test_non_bool_fast_flag_rejected(self):
        with self.assertRaises(ValueError):
            SkillChat(self.launcher, fast='yes')


if __name__ == '__main__':
    unittest.main()
