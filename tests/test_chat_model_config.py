"""Trusted server model selection; legacy size limits remain unchanged."""
import os
import unittest
from unittest.mock import patch
from gateway_pilot.application.skill_chat import local_model


class ChatModelConfigTests(unittest.TestCase):
    def test_default_4b_and_legacy_override(self):
        with patch('gateway_pilot.application.skill_chat._chat_context', return_value='trusted-context'), patch.dict(os.environ, {}, clear=True), patch('gateway_pilot.application.skill_chat.OllamaGoalModel') as model:
            local_model(timeout=9)
            model.assert_called_once_with('qwen3:4b', timeout=9, max_parameters=4_500_000_000, chat_context='trusted-context')
        with patch('gateway_pilot.application.skill_chat._chat_context', return_value='trusted-context'), patch.dict(os.environ, {'GATEWAY_LM_CHAT_MODEL': 'qwen3:1.7b'}), patch('gateway_pilot.application.skill_chat.OllamaGoalModel') as model:
            local_model(timeout=9)
            model.assert_called_once_with('qwen3:1.7b', timeout=9, max_parameters=3_000_000_000, chat_context='trusted-context')
