"""Vietnamese incident replay through approved Core READ sessions and Web chat."""
from __future__ import annotations

import io
import json
import unittest
from collections import Counter
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.application import skill_chat
from gateway_pilot.application.replay_sim_run import run_replay_skill
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.command_catalog.runtime import ReadRuntime
from gateway_pilot.core import PlanError
from gateway_pilot.skill_expansion import deployment, incident_replay, replay_sim
from web_gateway.server import Handler


def request(path: str, body: dict | None = None) -> tuple[int, dict]:
    raw = b'' if body is None else json.dumps(body).encode()
    handler = Handler.__new__(Handler)
    handler.path, handler.server = path, SimpleNamespace(server_port=8765)
    handler.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(raw)),
                       'Host': 'localhost:8765'}
    handler.rfile, handler.wfile = io.BytesIO(raw), io.BytesIO()
    handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
    (handler.do_GET if body is None else handler.do_POST)()
    return handler.send_response.call_args.args[0], json.loads(handler.wfile.getvalue())


class IncidentReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        directory = incident_replay.DIRECTORY
        cls.references = read_json(directory / 'router_incidents_v1.json')['incidents']
        cls.gold = read_json(directory / 'gold.json')['expected']
        cls.profile = replay_sim.prepare_profile()

    def setUp(self):
        def operator_approval(path):
            doc = read_json(path)
            return {**doc, 'replay_sim': self.profile.approval.copy()} if path.name == 'approvals.json' else doc

        self.launcher = SkillLauncher()
        self.model = Mock(side_effect=AssertionError('known symptoms must route deterministically'))
        self.chat = skill_chat.SkillChat(self.launcher, model_factory=self.model, fast=True)
        self.enterContext(patch.object(deployment, 'read_json', side_effect=operator_approval))
        self.enterContext(patch.object(skill_chat, 'CHAT', self.chat))

    def test_all_user_questions_with_exact_fault_claims_and_core_proofs(self):
        self.assertEqual(len(self.references), 14)
        self.assertEqual({row['id'] for row in self.references}, self.gold.keys())
        original_open = io.open

        def no_gold(path, *args, **kwargs):
            if not isinstance(path, int):
                self.assertFalse(Path(path).name.startswith('gold'), f'runtime opened {path}')
            return original_open(path, *args, **kwargs)

        # Rebuild the actual profile under the file guard, then reuse it for the HTTP requests.
        with patch('io.open', side_effect=no_gold):
            profile = replay_sim.prepare_profile()
            with patch.object(replay_sim, 'prepare_profile', return_value=profile):
                for item in self.references:
                    key = item['id']
                    expected = self.gold[key]
                    options = {'scenario': key}
                    self.assertGreaterEqual(len(item['user_says']), 2)
                    for question in item['user_says']:
                        with self.subTest(incident=key, question=question):
                            status, result = request('/api/chat', {
                                'source_mode': 'replay_sim', 'message': question, **options})
                            self.assertEqual(status, HTTPStatus.OK, result)
                            options['session_id'] = result['session_id']
                            self.assertEqual(result['scenario'], key)
                            self.assertEqual(result['routing'], {'method': 'symptom', 'plan': [expected['skill_id']]})
                            self.assertEqual((result['verdict'], result['answer_kind']), ('FAULT', 'evidence'))
                            self.assertIs(result['synthetic_only'], True)
                            self.assertIn(replay_sim.NOTICE, result['answer'])
                            self.assertGreater(result['calls'], 0)
                            self.assertEqual(result['calls'], len(result['timeline']))
                            claims = {cid: claim for cid, claim in result['assessment']['claims'].items()
                                      if claim['value'] == 'TRUE' and claim['severity'] == 'FAULT'}
                            self.assertEqual(set(claims), set(expected['fault_claims']))
                            core_evidence = {row['id'] for row in result['evidence']}
                            proof = set()
                            for claim in claims.values():
                                self.assertTrue(claim['evidence'])
                                proof.update(claim['evidence'])
                            self.assertEqual(proof, set(result['evidence_ids']))
                            self.assertTrue(proof <= core_evidence)
                            for row in result['evidence']:
                                self.assertEqual(row['source'], replay_sim.SimulationReplayBackend.source)
                                self.assertEqual(row['target'], replay_sim.TARGET)
                                self.assertGreater(row['expires_in_s'], 0)
                            for plan in result['plans']:
                                for node in plan['nodes'].values():
                                    self.assertEqual(node['risk'], 'READ_ONLY')
                                    self.assertEqual(node['state'], 'SUCCEEDED')
                                    self.assertIn(('READY', 'RUNNING'),
                                                  [(step['from'], step['to']) for step in node['history']])
                            self.assertEqual(result.pop('incident_guidance'), {
                                'label': incident_replay.ADVISORY, 'steps': item['fix_vi'], 'sources': item['sources']})
                            without_guidance = json.dumps(result, ensure_ascii=False)
                            for advisory in [*item['fix_vi'], *item['sources'], expected['root_cause']]:
                                self.assertNotIn(advisory, without_guidance)
                            self.assertNotIn('command_proposal', result)
                    self.launcher.close(options['session_id'])
        self.model.assert_not_called()

    def test_each_world_keeps_unrelated_checks_at_their_normal_verdict(self):
        profile = self.profile
        ordinary = profile.actions.keys() | profile.incidents.actions.keys()
        skills = ordinary | profile.igate.actions.keys()
        observational = {'IG01', 'IG02', 'IG04', 'IG05'}
        for item in self.references:
            key = item['id']
            covered = Counter()
            related = self.gold[key]['related_verdicts']
            self.assertTrue(set(item['skills']) <= ordinary)
            for sid in sorted(skills):
                with self.subTest(incident=key, skill=sid):
                    result = run_replay_skill(replay_sim.ReplaySession(profile, key), 'verification', sid, deadline=None)
                    expected = related.get(sid, 'UNKNOWN' if sid in observational else 'HEALTHY')
                    self.assertEqual(result['verdict'], expected)
                    self.assertFalse(result['missing_ports'])
                    if expected != 'FAULT':
                        self.assertNotIn('incident_guidance', result)
                    overrides = profile.incident_replay.measurements[key]
                    for row in result['evidence']:
                        if (row['port'] in overrides
                                and row['simulated_at'] == profile.incident_replay.current_time.isoformat()):
                            self.assertEqual(row['value'], overrides[row['port']])
                            covered[row['port']] += 1
            self.assertEqual(set(covered), profile.incident_replay.measurements[key].keys())

    def test_same_symptom_does_not_take_its_verdict_from_the_scenario_name(self):
        with patch.object(replay_sim, 'prepare_profile', return_value=self.profile):
            for item in self.references:
                with self.subTest(incident=item['id']):
                    result = self.chat.chat(item['user_says'][0], mode='replay_sim', scenario='normal')
                    self.launcher.close(result['session_id'])
                    self.assertEqual(result['routing']['plan'], [self.gold[item['id']]['skill_id']])
                    self.assertEqual(result['verdict'], 'HEALTHY')
                    self.assertNotIn('incident_guidance', result)
            for scenario, claim in [('INC-CGNAT', 'gp05_carrier_grade_nat_v1'),
                                    ('INC-DOUBLE-NAT', 'gp05_double_nat_v1')]:
                result = self.chat.chat('Kiểm tra GP05', mode='replay_sim', scenario=scenario)
                self.launcher.close(result['session_id'])
                self.assertEqual(result['assessment']['claims'][claim]['value'], 'TRUE')
        self.model.assert_not_called()

    def test_web_options_session_binding_and_payload_allowlist(self):
        with patch('web_gateway.server._status', return_value={'gos_available': False, 'react_available': False}):
            status, result = request('/api/config')
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(result['replay_sim_skill_count'], 101)
        self.assertEqual(result['replay_sim_incidents'],
                         [{'id': row['id'], 'title': row['title_vi']} for row in self.references])

        with patch.object(replay_sim, 'prepare_profile', return_value=self.profile):
            sid = self.launcher.create_session('replay_sim', scenario='INC-WAN-DOWN')['session_id']
            msg = {'source_mode': 'replay_sim', 'message': 'Cả nhà mất mạng'}
            status, error = request('/api/chat', {**msg, 'session_id': sid, 'scenario': 'INC-DNS-FAIL'})
            self.assertEqual((status, error['reason']), (HTTPStatus.BAD_REQUEST, 'chat_scenario_requires_new_session'))
            for invalid in ('INC-UNKNOWN', '../gold.json', {}):
                status, error = request('/api/chat', {**msg, 'scenario': invalid})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST, error)
            for field in ('target', 'measurements', 'incident_guidance'):
                status, error = request('/api/chat', {**msg, field: {}})
                self.assertEqual(status, HTTPStatus.BAD_REQUEST, error)
            status, blocked = request('/api/chat', {**msg, 'session_id': sid,
                'message': 'Router hay tự khởi động lại, hãy xóa lease'})
            self.assertEqual((status, blocked['case_status'], blocked['calls']), (HTTPStatus.OK, 'BLOCKED', 0))
            self.assertNotIn('incident_guidance', blocked)
            self.assertNotIn('command_proposal', blocked)
            self.assertEqual(self.launcher.run(sid, 'SK13')['calls_this_run'], 0)
            self.assertEqual(request('/api/commands/execute', {'scenario': 'INC-WAN-DOWN'})[0], HTTPStatus.NOT_FOUND)

    def test_unverified_sources_never_produce_a_fault_or_guidance(self):
        def bad_sample(backend, metadata, arguments, context):
            rows = backend.sample_preview(metadata, arguments, context)
            if metadata['function_id'] != 'expansion.dns_resolvers':
                return ToolResult(observations=tuple(rows))
            if defect == 'timeout':
                raise TimeoutError('test only')
            row = dict(rows[0])
            row.update({
                'target': {'target': 'foreign-target'},
                'scope': {'scope': 'client'},
                'malformed': {'value': {'healthy_count': '0'}},
                'stale': {'age_s': row['ttl_s'] + 1},
            }[defect])
            return ToolResult(observations=(row,))

        def denied(runtime, *args, **kwargs):
            original(runtime, *args, **{**kwargs, 'permissions': frozenset()})

        original = ReadRuntime.__init__
        with patch.object(replay_sim, 'prepare_profile', return_value=self.profile):
            sid = self.launcher.create_session('replay_sim', scenario='INC-DNS-FAIL')['session_id']
            for defect in ('target', 'scope', 'malformed', 'timeout', 'stale', 'permission'):
                guard = (patch.object(ReadRuntime, '__init__', denied) if defect == 'permission' else
                         patch.object(replay_sim.SimulationReplayBackend, 'sample', bad_sample))
                with self.subTest(defect=defect), guard:
                    result = self.chat.chat('Có Wi-Fi mà không vào được web', mode='replay_sim', session_id=sid)
                    self.assertEqual((result['verdict'], result['evidence_ids']), ('UNKNOWN', []))
                    self.assertNotIn('incident_guidance', result)

    def test_new_pin_is_required_and_malformed_measurements_are_rejected(self):
        def invalid_fixture(path):
            doc = read_json(path)
            if path.name == 'scenarios.json':
                doc['scenarios']['INC-DNS-FAIL']['expansion.dns_resolvers']['healthy_count'] = '0'
            return doc

        old = {k: v for k, v in self.profile.approval.items() if k != 'incident_scenarios_digest'}
        with patch.object(replay_sim, 'prepare_profile', return_value=self.profile):
            with self.assertRaisesRegex(PlanError, 'incident_scenarios_digest_pin'):
                replay_sim.approved_profile(old)
        with patch.object(incident_replay, 'read_json', side_effect=invalid_fixture):
            with self.assertRaisesRegex(PlanError, 'incident_fixture_schema'):
                replay_sim.prepare_profile()

        def reordered_sources(path):
            doc = read_json(path)
            if path.name == 'diagnostics.json':
                check = doc['joint_checks']['H05']
                check['sources'] = dict(reversed(list(check['sources'].items())))
            return doc

        with patch.object(incident_replay, 'read_json', side_effect=reordered_sources):
            with self.assertRaisesRegex(PlanError, 'incident_scenarios_digest_pin'):
                replay_sim.approved_profile(self.profile.approval)


if __name__ == '__main__':
    unittest.main()
