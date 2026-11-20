"""Replay-Sim approval, Core evidence, selection and HTTP boundaries."""
import copy
import io
import json
import time
import unittest
from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gateway_pilot.adapters.bindings import TargetContext
from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.application import replay_sim_run, skill_chat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.core import PlanError, ROOT
from gateway_pilot.skill_expansion import deployment as dep, replay_sim
from gateway_pilot.skill_expansion.coverage import (
    ACCEPTANCE, COMPOSITE_BATCHES, DIRECT_BATCHES, accepted_skills, skill_graph,
)
from web_gateway.server import Handler, analyze


class ReplaySimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = replay_sim.prepare_profile()
        cls.accepted = accepted_skills()

    def approve(self):
        def fake_read(path, **kwargs):
            doc = read_json(path, **kwargs)
            if Path(path).name == 'approvals.json':
                doc['replay_sim'] = copy.deepcopy(self.profile.approval)
            return doc
        return patch.object(dep, 'read_json', side_effect=fake_read)

    def launcher(self, clock=time.monotonic):
        return SkillLauncher(clock=clock,
                             factory=lambda mode, **kw: dep.composition(mode, clock=clock, **kw))

    def test_exact_coverage_and_only_consumed_read_functions(self):
        receipts = json.loads(ACCEPTANCE.read_text())['skills']
        self.assertEqual(set(self.profile.actions), self.accepted)
        self.assertEqual(self.accepted, set(receipts))
        self.assertNotIn('SK13', self.profile.actions)
        for sid, action in self.profile.actions.items():
            with self.subTest(skill=sid):
                self.assertEqual(skill_chat._replay_candidates(
                    action['name'], self.profile.diagnostics['routing']['phrases'])[1], [sid])
        expected = set()
        for directory, _ in DIRECT_BATCHES.values():
            expected.update(row.function_id for row in replay_sim.simulation.load_scenarios(replay_sim.DATA_DIR / directory)
                            if row.skill_id in self.accepted)
        for batch in COMPOSITE_BATCHES:
            expected.update(spec['function_id']
                            for sid, row in replay_sim.composite.contracts(batch)['workflows'].items()
                            if sid in self.accepted for spec in row['sources'].values())
        self.assertEqual(set(self.profile.registries), expected)
        for artifact, _, _ in self.profile.registries.values():
            self.assertTrue(all(f['risk'] == 'READ_ONLY' for f in artifact['functions']))
        with self.approve():
            response = self.launcher().catalog('replay_sim')
        self.assertEqual({row['skill_id'] for row in response['rows']}, self.accepted)

    def test_production_gate_and_specific_http_response(self):
        path = ROOT / 'config/skill_launcher/approvals.json'
        approval = path.read_bytes()
        real_read = dep.read_json

        def unapproved(p):  # an operator config without a replay_sim pin, independent of the repo's file
            doc = real_read(p)
            return {k: v for k, v in doc.items() if k != 'replay_sim'} if Path(p).name == 'approvals.json' else doc
        with patch.object(dep, 'read_json', unapproved):
            self._assert_unapproved(path, approval)

    def _assert_unapproved(self, path, approval):
        with self.assertRaisesRegex(PlanError, 'skill_deployment_not_approved'):
            dep.composition('replay_sim')
        payload = {'message': 'Kiểm tra WAN', 'source_mode': 'replay_sim'}
        handler = Handler.__new__(Handler)
        body = json.dumps(payload).encode()
        handler.path, handler.server = '/api/chat', SimpleNamespace(server_port=8765)
        handler.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(body)),
                           'Host': 'localhost:8765'}
        handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
        handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
        handler.do_POST()
        self.assertEqual(handler.send_response.call_args.args[0], HTTPStatus.FORBIDDEN)
        error = json.loads(handler.wfile.getvalue())
        self.assertEqual(error['reason'], 'skill_deployment_not_approved')
        self.assertIn('-m scripts.prepare_replay_sim_approval', error['error'])
        self.assertIs(error['synthetic_only'], True)
        self.assertEqual(path.read_bytes(), approval)

    def test_approval_checks_every_pin_and_rejects_malformed_fixture(self):
        for key in self.profile.approval:
            with self.subTest(pin=key), patch.object(replay_sim, 'prepare_profile', return_value=self.profile):
                with self.assertRaisesRegex(PlanError, key + '_pin'):
                    replay_sim.approved_profile({**self.profile.approval, key: 'incorrect'})
        load = replay_sim.composite.load_scenarios

        def broken(batch):
            rows = load(batch)
            if batch == 'A':
                sample = next(iter(rows[0]['sources'].values()))
                sample['values'] = {'not_a_port_field': 'malformed'}
            return rows

        with self.approve(), patch.object(replay_sim.composite, 'load_scenarios', side_effect=broken):
            with self.assertRaisesRegex(PlanError, 'skill_sim_fixture_schema'):
                dep.composition('replay_sim')

    def test_chat_topics_scenarios_and_graph_without_reading_gold(self):
        open_file = io.open

        def no_gold(path, *args, **kwargs):
            if not isinstance(path, int) and Path(path).name.startswith('gold'):
                self.fail(f'runtime opened {path}')
            return open_file(path, *args, **kwargs)

        launcher = self.launcher()
        model = Mock(side_effect=AssertionError('known phrases must route deterministically'))
        chat = skill_chat.SkillChat(launcher, model_factory=model, fast=True)
        questions = {
            'WAN có ổn không?': 'SK04', 'Kiểm tra DNS': 'F02', 'Wi-Fi có yếu không?': 'SK02',
            'VPN đang hoạt động không?': 'J01', 'Nhiệt độ router bao nhiêu?': 'H05',
        }
        with self.approve(), patch('io.open', side_effect=no_gold), patch.object(skill_chat, 'CHAT', chat):
            graph = skill_graph(replay_sim=True)
            graph_edges = {(row['source'], row['target']) for row in graph['edges']}
            for state, expected in [('normal', 'HEALTHY'), ('fault', 'FAULT'), ('missing', 'UNKNOWN')]:
                options = {'scenario': state} if state != 'normal' else {}
                for question, skill in questions.items():
                    with self.subTest(state=state, skill=skill):
                        r = analyze({'message': question, 'source_mode': 'replay_sim', **options})
                        options = {'session_id': r['session_id']}
                        self.assertEqual(r['scenario'], state)
                        self.assertEqual(r['verdict'], expected)
                        self.assertIs(r['synthetic_only'], True)
                        self.assertIn(replay_sim.NOTICE, r['answer'])
                        self.assertLessEqual(len(r['answer'].splitlines()), 4)
                        self.assertEqual([run['skill_id'] for run in r['skill_runs']], [skill])
                        self.assertEqual(r['calls'], len(r['timeline']))
                        self.assertTrue(all((skill, row['function_id']) in graph_edges for row in r['timeline']))
                        self.assertEqual(bool(r['evidence_ids']), expected != 'UNKNOWN')
                        self.assertTrue(all(row['source'] == replay_sim.SimulationReplayBackend.source for row in r['evidence']))
                if state == 'fault':
                    with self.assertRaisesRegex(ValueError, 'chat_scenario_requires_new_session'):
                        chat.chat('Nhiệt độ router?', mode='replay_sim', scenario='normal', **options)
                launcher.close(options['session_id'])
        model.assert_not_called()

    def test_unsupported_topics_targets_write_and_model_proposals(self):
        launcher = self.launcher()
        model = SimpleNamespace(local_only=True, choose_skills=Mock())
        chat = skill_chat.SkillChat(launcher, model_factory=lambda: model)
        with self.approve():
            session = launcher.create_session('replay_sim')['session_id']
            for question, status in [('Chẩn đoán phân giải DNS', 'UNAVAILABLE'),
                                     ('Kiểm tra Bluetooth', 'UNAVAILABLE'),
                                     ('Đổi cấu hình DNS', 'BLOCKED'),
                                     ('Nhiệt độ router 192.168.4.1?', 'NEEDS_INPUT'),
                                     ('Nhiệt độ của laptop?', 'NEEDS_INPUT'),
                                     ('Kiểm tra VPN của router khác', 'NEEDS_INPUT')]:
                with self.subTest(question=question):
                    r = chat.chat(question, mode='replay_sim', session_id=session)
                    self.assertEqual(r['case_status'], status)
                    self.assertIn(replay_sim.NOTICE, r['answer'])
                    self.assertEqual(r['calls'], 0)
            self.assertEqual(launcher.run(session, 'SK13')['calls_this_run'], 0)
            for question, skill in [('Đối chiếu IP–MAC–hostname', 'A06'),
                                    ('Phân tích reboot/crash', 'H07'),
                                    ('Kiểm tra trạng thái radio và SSID', 'B02')]:
                r = chat.chat(question, mode='replay_sim', session_id=session)
                self.assertEqual(r['routing']['plan'], [skill])
                self.assertEqual(r['verdict'], 'HEALTHY')
            model.choose_skills.assert_not_called()
            with patch.object(skill_chat, '_replay_candidates', return_value=('graph', ['H05', 'H06'])):
                for skill, count in [('SK13', 0), ('F02', 0), ('H05', 1)]:
                    model.choose_skills.return_value = {'decision': 'measure', 'skill_ids': [skill],
                                                        'finding_ids': [], 'unavailable_ids': []}
                    r = chat.chat('Sức khỏe router?', mode='replay_sim', session_id=session)
                    self.assertEqual(r['calls'], count)
            self.assertTrue(all({r[0] for r in call.args[1]} == {'H05', 'H06'}
                                for call in model.choose_skills.call_args_list))

    def test_generic_question_uses_retrieval_but_only_the_model_can_pick(self):
        launcher = self.launcher()
        model = SimpleNamespace(local_only=True, choose_skills=Mock())
        chat = skill_chat.SkillChat(launcher, model_factory=lambda: model)
        with self.approve():
            session = launcher.create_session('replay_sim')['session_id']
            # Every word of "sức khỏe router" is generic, so the name match is empty.
            r = chat.chat('Sức khỏe router', mode='replay_sim', session_id=session, allow_model=False)
            self.assertEqual((r['case_status'], r['calls']), ('NEEDS_INPUT', 0))  # top hit never auto-runs
            for skill, count in [('SK08', 1), ('F02', 0), ('SK13', 0)]:  # F02/SK13: not offered or not approved
                with self.subTest(skill=skill):
                    model.choose_skills.return_value = {'decision': 'measure', 'skill_ids': [skill],
                                                        'finding_ids': [], 'unavailable_ids': []}
                    r = chat.chat('Sức khỏe router', mode='replay_sim', session_id=session)
                    self.assertEqual(r['calls'] > 0, bool(count))
            offered = {row[0] for row in model.choose_skills.call_args.args[1]}
            self.assertIn('SK08', offered)
            self.assertNotIn('SK13', offered)
            self.assertTrue(offered <= {row['skill_id'] for row in launcher.catalog('replay_sim')['rows']})

    def test_wrong_target_scope_malformed_timeout_stale_and_no_permission(self):
        launcher = self.launcher()
        def sample(backend, metadata, arguments, context):
            if defect == 'timeout':
                raise TimeoutError('test transport timeout')
            rows = list(backend.sample_preview(metadata, arguments, context))
            row = rows[0]
            if defect == 'scope':
                row['scope'] = 'client'
            elif defect == 'target':
                row['target'] = 'synthetic-foreign'
            elif defect == 'malformed':
                row['value'] = {'celsius': 'broken'}
            elif defect == 'stale':
                row['age_s'] = row['ttl_s'] + 1
            return ToolResult(observations=tuple(rows))

        with self.approve():
            session_id = launcher.create_session('replay_sim')['session_id']
            for defect in ('scope', 'target', 'malformed', 'timeout', 'stale'):
                with self.subTest(defect=defect), patch.object(replay_sim.SimulationReplayBackend, 'sample', sample):
                    r = launcher.run(session_id, 'H05')
                    self.assertEqual((r['status'], r['verdict'], r['calls_this_run']), ('UNAVAILABLE', 'UNKNOWN', 1))
                    self.assertEqual(r['evidence'], [])
                    self.assertEqual(r['evidence_ids'], [])
                    self.assertNotEqual(r['timeline'][0]['node_state'], 'SUCCEEDED')
            from gateway_pilot.command_catalog.runtime import ReadRuntime
            original = ReadRuntime.__init__

            def denied(runtime, *args, **kwargs):
                original(runtime, *args, **{**kwargs, 'permissions': frozenset()})

            with patch.object(ReadRuntime, '__init__', denied):
                r = launcher.run(session_id, 'H05')
            self.assertEqual((r['verdict'], r['calls_this_run'], r['evidence']), ('UNKNOWN', 0, []))
            self.assertIn('function_not_available', str(r['source_errors']))
            entry = launcher._get(session_id)['session']
            sample_row = next(iter(entry.profile.samples['H05']['normal'].values()))
            scoped, *_ = entry.profile.open_sample(sample_row, environment=entry.environment, clock=entry.clock,
                                                   max_calls=2, ttl_s=10)
            backend = scoped.runtime._selection.checked_binding(
                'launcher.expansion.temperature', scoped.runtime.context, scoped.runtime.permissions)[-1]
            self.assertFalse(backend.supports(sample_row.function_id,
                                             TargetContext(sample_row.scope, 'synthetic-foreign', entry.environment)))

    def test_history_uses_distinct_proofs_and_expiry_revokes_composite_claim(self):
        now = [100.]
        launcher = self.launcher(clock=lambda: now[0])
        with self.approve():
            session_id = launcher.create_session('replay_sim')['session_id']
            r = launcher.run(session_id, 'K01')
            history = r['assessment']['history']
            self.assertEqual(len(history), len({row['evidence_id'] for row in history}))
            self.assertGreater(len(history), 1)
            self.assertTrue(set(r['evidence_ids']) >= {row['evidence_id'] for row in history})
            original = replay_sim_run.assess_workflow

            def expire(*args, **kwargs):
                result = original(*args, **kwargs)
                self.assertEqual(result['verdict'], 'HEALTHY')
                now[0] += 60
                return result

            with patch.object(replay_sim_run, 'assess_workflow', expire):
                expired = launcher.run(session_id, 'SK04')
            self.assertEqual(expired['verdict'], 'UNKNOWN')
            self.assertEqual(expired['evidence_ids'], [])
            self.assertTrue(all(r['status'] != 'OK' for r in expired['timeline']))
            self.assertFalse(any(c['value'] == 'TRUE' for c in expired['assessment']['claims'].values()))

    def test_composite_cannot_reset_the_session_call_budget(self):
        replay = replay_sim.ReplaySession(self.profile, 'normal', max_calls=2)
        result = replay_sim_run.run_replay_skill(replay, 'test-only', 'SK04', deadline=None)
        self.assertEqual(result['calls_total'], 2)
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertEqual(result['evidence_ids'], [])
        self.assertIn('READ_BUDGET_EXHAUSTED', result['source_errors'].values())
        second = replay_sim_run.run_replay_skill(replay, 'test-only', 'H05', deadline=None)
        self.assertEqual(second['calls_this_run'], 0)
        self.assertEqual(second['verdict'], 'UNKNOWN')

    def test_all_accepted_scenarios_replay_verdicts(self):
        expected = json.loads(ACCEPTANCE.read_text())['skills']
        for scenario in replay_sim.STATES:
            for skill in sorted(expected):
                with self.subTest(skill=skill, scenario=scenario):
                    replay = replay_sim.ReplaySession(self.profile, scenario)
                    result = replay_sim_run.run_replay_skill(replay, 'test-only', skill, deadline=None)
                    self.assertEqual(result['verdict'], expected[skill][scenario]['verdict'])
                    self.assertEqual(len(result['timeline']), result['calls_this_run'])
                    self.assertTrue(set(result['evidence_ids']) <= {row['id'] for row in result['evidence']})
