"""Benchmark integrity, inference isolation and fail-closed scoring contracts."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.skill_expansion.deployment import composition
from scripts.evaluate_skill_chat import (DATA, ScriptedModel, SyntheticLaptopBackend,
                                        evaluate, load_cases, score_response)


class SkillChatEvaluationTests(unittest.TestCase):
    def test_frozen_split_hashes_and_scenario_groups(self):
        manifest, dev = load_cases('dev')
        _, test = load_cases('test')
        self.assertEqual(len(dev), 12)
        self.assertEqual(len(test), 12)
        self.assertEqual(manifest['files']['dev']['turns'], 14)
        for field in ('id', 'scenario_group', 'paraphrase_group'):
            self.assertFalse({r[field] for r in dev} & {r[field] for r in test})
        self.assertEqual({r['category'] for r in dev}, {r['category'] for r in test})
        with self.assertRaisesRegex(ValueError, 'invalid_benchmark_split'):
            load_cases('train')

    def test_manifest_and_split_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for filename in ('manifest.json', 'dev.jsonl', 'test.jsonl'):
                shutil.copyfile(DATA / filename, folder / filename)
            (folder / 'dev.jsonl').write_text('{}\n')
            with self.assertRaisesRegex(ValueError, 'split_hash_mismatch'):
                load_cases('dev', folder=folder)
            (folder / 'manifest.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'manifest_hash_mismatch'):
                load_cases('dev', folder=folder)

    def test_real_core_uses_only_synthetic_telemetry_and_no_labels_in_model_inputs(self):
        inputs = []
        class RecordingModel(ScriptedModel):
            def choose_skills(self, request, catalog, context):
                inputs.append((request, catalog, context))
                return super().choose_skills(request, catalog, context)
        with patch.object(SyntheticLaptopBackend, '_command', side_effect=AssertionError('OS call')):
            report = evaluate('dev', limit=1, model_factory=RecordingModel)
        self.assertEqual(report['runtime_errors'], 0)
        self.assertEqual(report['tool_calls'], 2)
        self.assertEqual(report['provider_mode'], 'synthetic_replay')
        self.assertFalse(report['os_measurement'])
        self.assertTrue(inputs)
        for _, _, context in inputs:
            for forbidden in ('expected', 'category', 'scenario_group', 'provider', 'call_bounds'):
                self.assertNotIn(forbidden, context)
        self.assertEqual(report['skill_selection']['recall'], 1)
        self.assertEqual(report['answer_coverage'], 1)
        self.assertEqual(report['rca_proof_valid_rate'], 1)

    def test_model_proposal_cannot_execute_unregistered_function(self):
        class MaliciousModel:
            local_only = True
            model = 'adversarial-test-double'
            def choose_skills(self, request, catalog, context):
                return {'decision': 'measure', 'skill_ids': ['os.system'],
                        'finding_ids': [], 'unavailable_ids': []}
        report = evaluate('dev', limit=1, model_factory=MaliciousModel)
        self.assertEqual(report['invalid_proposals'], 2)
        self.assertEqual(report['tool_calls'], 0)
        self.assertEqual(report['answer_coverage'], 0)
        self.assertEqual(report['skill_selection']['recall'], 0)

    def test_missing_port_cannot_pass_multi_intent_coverage(self):
        expected = dict(skills=['one', 'two'], functions=['f1', 'f2'],
                        answer_ports=['a', 'b'], unavailable=[], abstain=False,
                        call_bounds=[2, 2], root_cause_must_abstain=True)
        response = dict(case_status='MEASURED', skill_runs=[{'skill_id': 'one'}],
                        timeline=[{'function_id': 'f1'}], calls=1,
                        evidence=[{'id': 'e1', 'port': 'a'}], evidence_ids=['e1'])
        score = score_response(response, expected, 10)
        self.assertEqual((score['covered'], score['obligations']), (1, 2))
        self.assertFalse(score['answer_complete'])
        self.assertFalse(score['calls_in_bounds'])
        self.assertEqual(score['skill_selection']['fn'], 1)
        response['case_status']='PARTIAL'
        self.assertFalse(score_response(response,expected,10)['abstention_correct'])
        response['diagnosis'] = 'fabricated_causal_root'
        self.assertFalse(score_response(response, expected, 10)['root_cause_abstention_correct'])

    def test_true_rca_claim_requires_current_verified_evidence(self):
        expected = dict(skills=[], functions=[], answer_ports=[], unavailable=[],
                        abstain=True, call_bounds=[0, 0], root_cause_must_abstain=True)
        response = dict(case_status='NEEDS_INPUT', rca_assessments=[{'claim_results': [
            {'truth': 'TRUE', 'evidence_ids': ['foreign-or-expired']}]}])
        self.assertFalse(score_response(response, expected, 1)['rca_proof_valid'])

    def test_real_inference_requires_explicit_model_and_test_returns_aggregates_only(self):
        manifest, dev = load_cases('dev')
        with patch('scripts.evaluate_skill_chat.OllamaGoalModel', side_effect=AssertionError('inference')), \
             patch('scripts.evaluate_skill_chat.load_cases', return_value=(manifest, dev[:1])):
            report = evaluate('test', limit=1)  # Only output-format behavior; no heldout execution.
        self.assertNotIn('details', report)
        self.assertEqual(report['model_mode'], 'test_double')
        self.assertEqual(report['turns'], 1)
        with self.assertRaisesRegex(ValueError, 'invalid_evaluation_options'):
            evaluate(limit=0)
        with self.assertRaisesRegex(ValueError, 'model_factory_only'):
            evaluate(model='ollama', model_factory=ScriptedModel)

    def test_instrumentation_separates_corrected_rejections_ttl_and_runner_repairs(self):
        expected = dict(skills=[], functions=[], answer_ports=[], unavailable=[],
                        abstain=True, call_bounds=[0, 0], root_cause_must_abstain=True)
        response = dict(case_status='NEEDS_INPUT', stop_reason='needs_clarification',
                        model_calls=3, proposal_rejections=1, repairs=2,
                        recovery_attempts=1, recovery_runs=[{'skill_id': 'registered-owner'}],
                        coverage={'requested_ports': ['a'], 'satisfied_ports': [], 'complete': False},
                        timings_ms={'inference': 12, 'execution': 8},
                        advice=[{'accepted': False, 'reason': 'incomplete_coverage'}, {'accepted': True}])
        row = score_response(response, expected, 30)
        self.assertEqual(row['proposal_rejections'], 1)
        self.assertEqual(row['invalid_proposals'], 1)
        self.assertEqual(row['proposals'], 3)
        self.assertEqual(row['coverage_feedback_rejections'], 1)
        self.assertEqual(row['advice_count'], 2)
        self.assertEqual(row['advice_accepted'], 1)
        self.assertEqual(row['ttl_recovery_attempts'], 1)
        self.assertEqual(row['ttl_recovery_runs'], 1)
        self.assertEqual(row['runner_repairs'], 2)
        self.assertEqual(row['reported_goals'], 1)
        self.assertEqual(row['reported_satisfied_goals'], 0)
        self.assertEqual(row['stage_timings_ms']['inference'], 12)

    def test_corrected_invalid_proposal_is_counted_after_later_valid_proposals(self):
        calls = []
        class CorrectingModel(ScriptedModel):
            def __init__(self):
                self.first = True
            def choose_skills(self, request, catalog, context):
                calls.append(request)
                if self.first:
                    self.first = False
                    return {'command': 'invalid'}
                return super().choose_skills(request, catalog, context)
        report = evaluate('dev', limit=1, model_factory=CorrectingModel)
        self.assertEqual(report['invalid_proposals'], 1)
        self.assertEqual(report['proposal_rejections'], 1)
        self.assertEqual(report['proposals'], len(calls))
        self.assertGreater(report['proposals'], report['proposal_rejections'])
        self.assertEqual(report['answer_complete_rate'], 1)
        self.assertGreater(report['advice_count'], 0)

    def test_runtime_error_is_not_credited_as_abstention_or_complete_answer(self):
        expected = dict(skills=[], functions=[], answer_ports=[], unavailable=[],
                        abstain=True, call_bounds=[0, 0], root_cause_must_abstain=True)
        row = score_response({'case_status': 'ERROR', 'stop_reason': 'RuntimeError'}, expected, 1)
        for key in ('answer_complete', 'abstention_correct', 'root_cause_abstention_correct',
                    'rca_proof_valid', 'request_success'):
            self.assertFalse(row[key])
        with patch('scripts.evaluate_skill_chat.SkillChat.chat', side_effect=RuntimeError('synthetic 500')):
            report = evaluate('dev', limit=1)
        self.assertEqual(report['runtime_errors'], 1)
        self.assertEqual(report['turns'], 1)
        self.assertEqual(report['request_success_rate'], 0)
        self.assertEqual(report['answer_complete_rate'], 0)

    def test_aggregate_keeps_runner_repairs_and_ttl_recovery_separate(self):
        response = dict(case_status='PARTIAL', calls=0, model_calls=3, proposal_rejections=1,
                        repairs=2, recovery_attempts=1, recovery_runs=[{}],
                        timings_ms={'inference': 12, 'execution': 8},
                        coverage={'requested_ports': ['a'], 'satisfied_ports': [], 'complete': False})
        with patch('scripts.evaluate_skill_chat.SkillChat.chat', return_value=response):
            report = evaluate('dev', limit=1)
        self.assertEqual(report['ttl_recovery_attempts'], 1)
        self.assertEqual(report['runner_repairs'], 2)
        self.assertEqual(report['total_recovery_attempts'], 3)
        self.assertEqual(report['proposal_rejections'], 1)
        self.assertEqual(report['proposals'], 3)
        self.assertEqual(report['stage_timings_ms']['inference']['p50'], 12)
        self.assertEqual(report['stage_timings_ms']['execution']['sum'], 8)

    def test_provider_timeout_has_no_successful_observation(self):
        backend = SyntheticLaptopBackend({'error_function': 'laptop.route'})
        now = lambda: 100.
        launcher = SkillLauncher(factory=lambda mode: composition(mode, backend=backend, clock=now), clock=now)
        result = SkillChat(launcher, model_factory=ScriptedModel).chat('Show the route')
        self.assertNotIn('laptop.route', result['snapshot']['facts'])
        self.assertNotEqual(result['case_status'], 'MEASURED')
        self.assertLessEqual(result['calls'], 4)
        launcher.close(result['session_id'])


if __name__ == '__main__':
    unittest.main()
