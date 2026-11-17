"""Registered LLM goal proposals bridge paraphrases without tool authority."""
import unittest
from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_chat import Model, choice
from tests.test_skill_launcher import FakeLaptopBackend


class ChatGoalProposalTests(unittest.TestCase):
    def test_unknown_paraphrase_gets_typed_goal_before_skill_selection(self):
        now=100.
        launcher=SkillLauncher(factory=lambda mode:composition(mode,backend=FakeLaptopBackend(),clock=lambda:now),clock=lambda:now)
        model=Model([choice(skills=['laptop.route.inspect']),choice('answer',findings=['laptop.route'])])
        request='Cho biết đường thoát mặc định'
        model.timeout=60
        model.propose_goals=lambda text,catalog: {'goals':['laptop.route'],'confidence':.95,
            'spans':{'laptop.route':'đường thoát'},'needs_clarification':False}
        chat=SkillChat(launcher,model_factory=lambda:model,clock=lambda:now)
        result=chat.chat(request)
        self.assertEqual(result['goal_proposal']['status'],'READY')
        self.assertIn('laptop.route',result['coverage']['requested_ports'])
        self.assertEqual(result['model_calls'],3)
        self.assertEqual(model.timeout,60)
        self.assertIn('Gateway',result['answer'])

    def test_unregistered_goal_cannot_execute_arbitrary_function(self):
        launcher=SkillLauncher(factory=lambda mode:composition(mode,backend=FakeLaptopBackend(),clock=lambda:100.),clock=lambda:100.)
        model=Model([choice('clarify')])
        model.propose_goals=lambda text,catalog:{'goals':['shell.exec'],'confidence':1.,
            'spans':{'shell.exec':'đường thoát'},'needs_clarification':False}
        result=SkillChat(launcher,model_factory=lambda:model,clock=lambda:100.).chat('Cho biết đường thoát mặc định')
        self.assertEqual(result['goal_proposal']['status'],'NEEDS_INPUT')
        self.assertEqual(result['calls'],0)
