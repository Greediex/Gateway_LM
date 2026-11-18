"""Long CPU inference remains bounded and synthetic replay stays separate."""
import unittest
from unittest.mock import patch, Mock
from gateway_pilot.workflow_advisor import OllamaProbeAdvisor
from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
from web_gateway.server import analyze


class ExtendedTimeoutTests(unittest.TestCase):
    def test_qwen4b_accepts_long_timeout_but_checks_verified_size(self):
        for model_type in (OllamaProbeAdvisor,OllamaGoalModel):
            with self.subTest(model_type=model_type.__name__):
                with patch(model_type.__module__+'.http_json',return_value={'model_info':{'general.parameter_count':4_022_468_096}}) as http:
                    kwargs={'max_parameters':4_500_000_000} if model_type is OllamaGoalModel else {}
                    model=model_type('qwen3:4b',timeout=240,**kwargs)
                    self.assertEqual(model.timeout,240)
                    self.assertEqual(http.call_args.kwargs['timeout'],240)
                    with self.assertRaises(ValueError):model_type('qwen3:4b',timeout=241,**kwargs)
                with patch(model_type.__module__+'.http_json',return_value={'model_info':{'general.parameter_count':8_000_000_000}}):
                    with self.assertRaises(ValueError):model_type('qwen3:4b',timeout=240,**kwargs)

    def test_other_models_and_invalid_timeouts_do_not_gain_unbounded_wait(self):
        for timeout in (True,float('nan'),float('inf'),0,61):
            with self.subTest(timeout=timeout),self.assertRaises(ValueError):
                OllamaProbeAdvisor('qwen3:1.7b',timeout=timeout)

    def test_replay_default_uses_4b_long_timeout_and_keeps_synthetic_label(self):
        advisor=Mock(model='qwen3:4b')
        advisor.understand_request.return_value='WF-INTERNET'
        advisor.reason_next.return_value={'next_stage':'client.probe','hypothesis':'Đo từ client.', 'evidence_ids':[]}
        with patch.dict('os.environ',{'GATEWAY_LM_CHAT_MODEL':'qwen3:4b'}),patch('gateway_pilot.workflow_advisor.OllamaProbeAdvisor',return_value=advisor) as factory:
            result=analyze({'message':'Laptop An vẫn có Wi-Fi, sao không truy cập Internet?',
                            'source_mode':'replay','fixture_id':'WEB-WAN-TIMEOUT-1',
                            'with_llm':True,'policy':'dynamic'})
        self.assertEqual(factory.call_args.args[0],'qwen3:4b')
        self.assertEqual(factory.call_args.kwargs['timeout'],240)
        self.assertEqual(result['mode'],'synthetic_replay')
        self.assertEqual(result['llm_limits'],{'rpc_timeout_s':240})
        self.assertIn('KHÔNG phản ánh',result['notice'])
        self.assertTrue(result['llm_advisor_ready'])
        self.assertTrue(result['evidence_ids'])
