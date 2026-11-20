"""Replay role-play contracts, approval gates and evidence-only aggregation."""
from __future__ import annotations

import copy
import json
import unittest
from http import HTTPStatus
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gateway_pilot.adapters.results import ToolResult
from gateway_pilot.application import skill_chat
from gateway_pilot.application.claim_guidance import GUIDANCE, load_claim_guidance
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.application.skill_triage import TAXONOMY, load_taxonomy
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.command_catalog.runtime import ReadRuntime
from gateway_pilot.core import PlanError
from gateway_pilot.observability.snapshot import VerifiedSnapshot
from gateway_pilot.skill_expansion import deployment, replay_sim
from gateway_pilot.skill_expansion.incident_replay import ADVISORY
from tests.test_incident_replay import request


class SkillTriageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = replay_sim.prepare_profile()
        cls.approved = set(cls.profile.actions) | cls.profile.igate.actions.keys() | cls.profile.incidents.actions.keys()

    def setUp(self):
        self.now = 10.0
        self.launcher = SkillLauncher(clock=self.clock, factory=self.compose)
        self.model = SimpleNamespace(local_only=True, choose_skills=Mock())
        self.chat = skill_chat.SkillChat(self.launcher, clock=self.clock, model_factory=lambda: self.model)
        self.enterContext(patch.object(replay_sim, 'prepare_profile', return_value=self.profile))
        self.enterContext(patch.object(skill_chat, 'CHAT', self.chat))

    def clock(self):
        return self.now

    def compose(self, mode, **kwargs):
        return deployment.composition(mode, clock=self.clock, **kwargs)

    def session(self, scenario='normal'):
        return self.launcher.create_session('replay_sim', scenario=scenario)['session_id']

    def test_symptom_cards_and_incident_phrases_do_not_read(self):
        with (patch.object(self.launcher, 'run', side_effect=AssertionError('triage executed a Skill')),
              patch.object(replay_sim.ReplayProfile, 'open_sample', side_effect=AssertionError('triage opened READ'))):
            for text, group, first_ids in [
                ('Chào bạn, tối đông người là mạng chậm lắm.', 'SYM-14-qua-tai-toi', ['GP04', 'SK08', 'G05']),
                ('Có Wi-Fi mà không vào được web', 'SYM-02-dns-hong', ['GP01', 'F02', 'F03']),
                ('Chào bạn, router hay tự khởi động lại. Nhờ bạn xem giúp.',
                 'SYM-13-router-nong-reboot', ['H07', 'H05', 'SK08']),
            ]:
                with self.subTest(text=text):
                    result = self.chat.triage(text)
                    cards = result['cards']
                    ids = [c['skill_id'] for c in cards]
                    self.assertEqual(ids[:3], first_ids)
                    self.assertEqual([c['source'] for c in cards[:3]], [f'symptom:{group}'] * 3)
                    self.assertEqual(result['symptom_groups'][0]['id'], group)
                    self.assertEqual(result['notice'], replay_sim.NOTICE)
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertLessEqual(len(ids), 6)
                    self.assertTrue(set(ids) <= self.approved)
                    self.assertTrue(all(c['plain_vi'] and c['why_vi'] and c['name'] for c in cards))
                    self.assertEqual(self.launcher._get(result['session_id'])['session'].calls, 0)
            sid = self.session()
            self.assertEqual(self.chat.triage('GP01', sid)['cards'][0]['source'], 'incident')
            self.assertEqual(self.chat.triage('Nhiệt độ router bao nhiêu?', sid)['cards'][0]['source'], 'phrase')
            both = self.chat.triage('Kiểm tra A04, H05 trên laptop và router', sid)['cards']
            self.assertEqual({c['skill_id'] for c in both[:2]}, {'A04', 'H05'})
        self.model.choose_skills.assert_not_called()

    def test_refusals_match_direct_replay(self):
        sid = self.session()
        with patch.object(self.launcher, 'run') as run:
            for question, reason in [
                ('Đổi cấu hình DNS', 'write_intent_requires_approval'),
                ('Router hay tự khởi động lại. Hãy khởi động lại router.', 'write_intent_requires_approval'),
                ('Router hãy tự khởi động lại', 'write_intent_requires_approval'),
                ('Kiểm tra 192.168.1.9', 'custom_target_not_supported'),
                ('Kiểm tra 2001:db8::1', 'custom_target_not_supported'),
                ('Kiểm tra router khác', 'custom_target_not_supported'),
                ('Kiểm tra router này', 'custom_target_not_supported'),
                ('Đây là mạng thật', 'custom_target_not_supported'),
            ]:
                with self.subTest(question=question):
                    result = self.chat.triage(question, sid, allow_model=True)
                    direct = self.chat.chat(question, session_id=sid, mode='replay_sim', allow_model=False)
                    self.assertEqual(result['cards'], [])
                    self.assertEqual(result['stop_reason'], reason)
                    self.assertEqual(result['answer'], direct['answer'])
                    self.assertEqual(result['case_status'], direct['case_status'])
            self.assertEqual(self.chat.triage('Đổi mật khẩu Wi-Fi', sid)['cards'], [])
            # Role-play speaks as the simulated home owner; direct chat keeps refusing the same phrase.
            owner = 'Có người lạ dùng wifi nhà tôi'
            self.assertEqual(self.chat.triage(owner, sid)['symptom_groups'][0]['id'], 'SYM-40-nghi-bi-xam-nhap')
            self.assertEqual(self.chat.chat(owner, session_id=sid, mode='replay_sim', allow_model=False)['stop_reason'],
                             'custom_target_not_supported')
            run.assert_not_called()
        self.model.choose_skills.assert_not_called()

    def test_search_fallback_and_model_shortlist_validation(self):
        sid = self.session()
        query = 'Sức khỏe router'
        with patch.object(self.launcher, 'run') as run:
            expected = self.chat.triage(query, sid)['cards']
            self.assertEqual(expected[0]['skill_id'], 'SK08')
            self.assertTrue(all(card['source'] == 'search' for card in expected))
            offered = {card['skill_id'] for card in expected}
            for skills in [['SK13'], ['F02'], ['SK08', 'SK08'], [None]]:
                with self.subTest(skills=skills):
                    self.model.choose_skills.return_value = self.proposal(skills)
                    self.assertEqual(self.chat.triage(query, sid, allow_model=True)['cards'], expected)
            self.model.choose_skills.return_value = self.proposal([expected[-1]['skill_id']])
            self.assertEqual(self.chat.triage(query, sid, allow_model=True)['cards'], expected[-1:] + expected[:-1])
            self.assertEqual({r[0] for r in self.model.choose_skills.call_args.args[1]}, offered)
            self.model.choose_skills.side_effect = TimeoutError
            self.assertEqual(self.chat.triage(query, sid, allow_model=True)['cards'], expected)
            run.assert_not_called()

    @staticmethod
    def proposal(ids):
        return dict(decision='measure', skill_ids=ids, finding_ids=[], unavailable_ids=[])

    def test_taxonomy_schema_is_strict(self):
        seed = read_json(TAXONOMY)
        groups = load_taxonomy(self.approved)
        self.assertEqual(len(groups), 50)
        self.assertEqual(sum(not g['cards'] for g in groups), 2)
        self.assertTrue(all('gap_vi' in g for g in groups if not g['cards']))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'taxonomy.json'
            for defect, reason in [('format', 'format'), ('group', 'group_id'), ('skill', 'unknown_skill'),
                                   ('duplicate_skill', 'duplicate_skill'), ('extra', 'group_fields'),
                                   ('phrases', 'phrases'), ('source', 'group'), ('no_cards', 'group')]:
                with self.subTest(defect=defect):
                    doc = copy.deepcopy(seed)
                    group = doc['groups'][0]
                    if defect == 'format':
                        doc['format'] = 'other/v1'
                    elif defect == 'group':
                        doc['groups'][1]['id'] = group['id']
                    elif defect == 'skill':
                        group['cards'][0]['skill_id'] = 'SK13'
                    elif defect == 'duplicate_skill':
                        group['cards'].append(group['cards'][0])
                    elif defect == 'extra':
                        group['unexpected'] = True
                    elif defect == 'phrases':
                        group['user_says'] = ['abc', 'ABC']
                    elif defect == 'source':
                        group['sources'] = ['file:///local']
                    elif defect == 'no_cards':  # empty cards are allowed only as a documented gap
                        group['cards'] = []
                        group.pop('gap_vi', None)
                    path.write_text(json.dumps(doc), encoding='utf-8')
                    with self.assertRaisesRegex(PlanError, f'skill_triage_taxonomy_{reason}$'):
                        load_taxonomy(self.approved, path)

    def test_incident_run_aggregates_real_core_proof_and_dedupes_guidance(self):
        sid = self.session('INC-DNS-FAIL')
        selected = ['A02', 'GP01', 'F02']
        with patch.object(self.launcher, 'run', wraps=self.launcher.run) as run:
            result = self.chat.run_selected(sid, selected)
        self.assertEqual([call.args for call in run.call_args_list], [(sid, key) for key in selected])
        self.assertEqual({call.kwargs['deadline'] for call in run.call_args_list}, {130.0})
        self.assertEqual(result['verdict'], 'FAULT')
        self.assertEqual([r['verdict'] for r in result['triage_results']], ['HEALTHY', 'FAULT', 'FAULT'])
        self.assertEqual(result['routing'], {'method': 'triage', 'plan': selected})
        self.assertEqual([r['skill_id'] for r in result['skill_runs']], selected)
        self.assertEqual([r['index'] for r in result['timeline']], list(range(1, result['calls'] + 1)))
        self.assertEqual(result['answer'].splitlines()[0], replay_sim.NOTICE)
        self.assertIn('Kết nối IP tới upstream thông', result['answer'].splitlines()[1])
        findings, _, steps = result['answer'].partition('\nCần làm gì:')
        self.assertTrue(findings.splitlines()[-1].startswith('Bình thường: '))
        self.assertGreater(len(steps.splitlines()), 1)
        self.assertLessEqual(len(steps.splitlines()), 4)
        self.assertTrue(all(r['claims'] and r['evidence_ids'] for r in result['triage_results']))
        self.assertEqual(set(result['evidence_ids']),
                         {eid for row in result['triage_results'] for eid in row['evidence_ids']})
        self.assertTrue(set(result['evidence_ids']) <= {r['id'] for r in result['evidence']})
        self.assertEqual(result['incident_guidance'], self.profile.incident_replay.guidance['INC-DNS-FAIL'])
        self.assertEqual(result['incident_guidance']['label'], ADVISORY)
        next_steps = result['next_steps']
        incident = result['incident_guidance']
        self.assertEqual((next_steps['kind'], next_steps['label']), ('fault', ADVISORY))
        self.assertEqual(next_steps['sources'], incident['sources'])
        texts = [step['text'] for step in next_steps['steps']]
        self.assertEqual(texts[:len(incident['steps'])], incident['steps'])
        self.assertEqual(len(texts), len(set(texts)))
        self.assertLessEqual(len(texts), 6)
        self.assertTrue(any(step['from'] == 'F02 · no_healthy_resolver_v1' for step in next_steps['steps']))
        self.model.choose_skills.assert_not_called()

    def test_healthy_and_mixed_verdicts_respect_shared_call_budget(self):
        for scenario, keys, budget, verdict, statuses in [
            ('normal', ['A02', 'GP01'], 24, 'HEALTHY', ['HEALTHY', 'HEALTHY']),
            ('normal', ['A02', 'GP01'], 1, 'UNKNOWN', ['HEALTHY', 'UNKNOWN']),
            ('INC-DNS-FAIL', ['GP01', 'A02'], 2, 'FAULT', ['FAULT', 'UNKNOWN']),
            ('missing', ['GP01', 'A02'], 24, 'UNKNOWN', ['UNKNOWN', 'UNKNOWN']),
        ]:
            with self.subTest(scenario=scenario, budget=budget):
                sid = self.session(scenario)
                replay = self.launcher._get(sid)['session']
                replay.max_calls = budget
                result = self.chat.run_selected(sid, keys)
                self.assertEqual(result['verdict'], verdict)
                self.assertEqual([r['verdict'] for r in result['triage_results']], statuses)
                self.assertLessEqual(result['calls_total'], budget)
                self.assertEqual(result['calls_total'], replay.calls)
                for row in result['triage_results']:
                    if row['verdict'] == 'UNKNOWN':
                        self.assertEqual(row['evidence_ids'], [])
                        unknown_line = result['answer'].partition('\nCần làm gì:')[0].splitlines()[-1]
                        self.assertTrue(unknown_line.startswith('Chưa đủ bằng chứng: '))
                        self.assertIn(row['name'], unknown_line)

    def test_earlier_fault_proof_expires_during_later_skill(self):
        sid = self.session('INC-DNS-FAIL')
        original = self.launcher.run

        def run(session_id, skill_id, *, deadline):
            result = original(session_id, skill_id, deadline=deadline)
            if skill_id == 'GP01':
                self.now += 50
            return result

        with patch.object(self.launcher, 'run', side_effect=run):
            result = self.chat.run_selected(sid, ['GP01', 'A02'])
        self.assertEqual(result['verdict'], 'UNKNOWN')
        fault = result['triage_results'][0]
        self.assertEqual((fault['verdict'], fault['claims'], fault['evidence_ids']), ('UNKNOWN', [], []))
        self.assertNotIn('incident_guidance', result)
        self.assertEqual(result['next_steps']['kind'], 'unknown')
        self.assertTrue(any(source.startswith('GP01 · ') for source in result['next_steps']['sources']))
        self.assertNotIn('Phát hiện:', result['answer'])
        self.assertTrue(all(event['evidence_id'] is None for event in result['timeline'][:2]))

    def test_collection_time_is_already_accounted_for_in_snapshot_ttl(self):
        sid = self.session()
        export = VerifiedSnapshot.export

        def slow_export(snapshot, **kwargs):
            self.now += 18
            return export(snapshot, **kwargs)

        with patch.object(VerifiedSnapshot, 'export', slow_export):
            result = self.chat.run_selected(sid, ['A02'])
        self.assertEqual(result['verdict'], 'HEALTHY')
        self.assertTrue(0 < result['evidence'][0]['expires_in_s'] < 13)

    def test_turn_deadline_is_not_reset_between_skills(self):
        sid = self.session()
        chat = skill_chat.SkillChat(self.launcher, clock=self.clock, max_elapsed_s=1)
        original = self.launcher.run

        def run(session_id, skill_id, *, deadline):
            result = original(session_id, skill_id, deadline=deadline)
            if skill_id == 'A02':
                self.now += 2
            return result

        with patch.object(self.launcher, 'run', side_effect=run) as launcher:
            result = chat.run_selected(sid, ['A02', 'GP01'])
        self.assertEqual({call.kwargs['deadline'] for call in launcher.call_args_list}, {11.0})
        self.assertEqual([row['calls_this_run'] for row in result['skill_runs']], [1, 0])
        self.assertEqual(result['verdict'], 'UNKNOWN')
        self.assertIn('READ_BUDGET_EXHAUSTED', result['source_errors']['GP01'].values())

    def test_adapter_defects_and_missing_read_permission_fail_closed(self):
        sid = self.session()
        backend = replay_sim.SimulationReplayBackend

        def sample(self, metadata, arguments, context):
            if defect == 'timeout':
                raise TimeoutError('simulated transport timeout')
            obs, = self.sample_preview(metadata, arguments, context)
            if defect == 'target':
                obs['target'] = 'other-device'
            else:
                obs['value'] = {'celsius': 'invalid'}
            return ToolResult(observations=(obs,))

        for defect in ('timeout', 'target', 'malformed'):
            with self.subTest(defect=defect), patch.object(backend, 'sample', sample):
                result = self.chat.run_selected(sid, ['H05'])
                self.assertEqual((result['verdict'], result['evidence'], result['evidence_ids']), ('UNKNOWN', [], []))
        original = ReadRuntime.__init__

        def denied(runtime, *args, **kwargs):
            original(runtime, *args, **{**kwargs, 'permissions': frozenset()})

        with patch.object(ReadRuntime, '__init__', denied):
            result = self.chat.run_selected(sid, ['H05'])
        self.assertEqual((result['verdict'], result['calls'], result['evidence']), ('UNKNOWN', 0, []))

    def test_invalid_selections_and_non_replay_sessions_never_run(self):
        sid = self.session()
        legacy = self.launcher.create_session('replay')['session_id']
        with patch.object(self.launcher, 'run') as run:
            for invalid in [[], ['A02'] * 7, ['A02', 'A02'], ['A02', 'SK13'], ['UNKNOWN'], ['A02', {}], 'A02']:
                with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                    self.chat.run_selected(sid, invalid)
            for invalid in [sorted(self.approved)[:7], ['GP01', 'GP01'], ['SK13'], ['UNKNOWN'], ['A02', {}], 'A02']:
                with self.subTest(offered_ids=invalid), self.assertRaises(ValueError):
                    self.chat.run_selected(sid, ['A02'], offered_ids=invalid)
            with self.assertRaisesRegex(ValueError, 'scenario_requires_new_session'):
                self.chat.run_selected(sid, ['A02'], scenario='fault')
            with self.assertRaisesRegex(ValueError, 'triage_requires_replay_sim_session'):
                self.chat.run_selected(legacy, ['A02'])
            with self.assertRaisesRegex(ValueError, 'triage_requires_replay_sim_session'):
                self.chat.triage('Có Wi-Fi mà không vào được web', legacy)
            run.assert_not_called()

    def test_server_endpoints_validate_payload_and_preserve_the_bound_scenario(self):
        triage, selected = '/api/skills/triage', '/api/skills/run_selected'
        status, cards = request(triage, {'message': 'Cả nhà mất mạng', 'scenario': 'INC-WAN-DOWN'})
        self.assertEqual(status, HTTPStatus.OK, cards)
        self.assertEqual(cards['cards'][0]['skill_id'], 'O07')
        sid = cards['session_id']
        status, reused = request(triage, {'session_id': sid, 'message': 'Cả nhà mất mạng'})
        self.assertEqual((status, reused['session_id']), (HTTPStatus.OK, sid))
        with patch.object(self.launcher, 'run') as run:
            for path, payload, expected in [
                (triage, {'scenario': 'normal'}, HTTPStatus.BAD_REQUEST),
                (triage, {'message': 'DNS', 'mode': 'live'}, HTTPStatus.BAD_REQUEST),
                (triage, {'message': 9}, HTTPStatus.BAD_REQUEST),
                (triage, {'message': 'DNS', 'session_id': []}, HTTPStatus.BAD_REQUEST),
                (triage, {'message': 'DNS', 'session_id': sid, 'scenario': 'normal'}, HTTPStatus.BAD_REQUEST),
                (triage, {'message': 'DNS', 'scenario': 'unknown'}, HTTPStatus.BAD_REQUEST),
                (triage, {'message': 'DNS', 'scenario': None}, HTTPStatus.BAD_REQUEST),
                (selected, {'skill_ids': ['O07']}, HTTPStatus.BAD_REQUEST),
                (selected, {'session_id': sid, 'skill_ids': []}, HTTPStatus.BAD_REQUEST),
                (selected, {'session_id': sid, 'skill_ids': ['SK13']}, HTTPStatus.BAD_REQUEST),
                (selected, {'session_id': sid, 'skill_ids': ['O07'], 'offered_ids': None}, HTTPStatus.BAD_REQUEST),
                (selected, {'session_id': sid, 'skill_ids': ['O07'], 'offered_ids': ['SK13']}, HTTPStatus.BAD_REQUEST),
                (selected, {'session_id': sid, 'skill_ids': ['O07'], 'target': 'router'}, HTTPStatus.BAD_REQUEST),
                (selected, {'session_id': 'f' * 32, 'skill_ids': ['O07']}, HTTPStatus.GONE),
            ]:
                with self.subTest(path=path, payload=payload):
                    status, body = request(path, payload)
                    self.assertEqual(status, expected, body)
                    self.assertIn('error', body)
            run.assert_not_called()
        status, result = request(selected, {'session_id': sid, 'skill_ids': ['O07', 'A02']})
        self.assertEqual(status, HTTPStatus.OK, result)
        self.assertEqual((result['scenario'], result['verdict']), ('INC-WAN-DOWN', 'FAULT'))

    def test_claim_guidance_covers_current_diagnostics_and_preserves_existing_text(self):
        profile = self.profile
        diagnostics = [d for catalog in (profile, profile.igate, profile.incidents)
                       for d in catalog.diagnostics['skills'].values()]
        diagnostics += [d for _, d in profile.incident_replay.joint_checks.values()]
        claims = {c['claim_id']: c['severity'] for d in diagnostics for c in d['claims']}
        existing = profile.incidents.diagnostics['claim_text'] | profile.incident_replay.claim_text
        metadata = load_claim_guidance(profile)
        self.assertEqual(set(metadata['text']), set(claims))
        self.assertTrue(all(text.strip() for text in metadata['text'].values()))
        self.assertTrue(all(metadata['text'][cid] == text for cid, text in existing.items()))
        self.assertEqual(set(metadata['fix']), {cid for cid, severity in claims.items()
                                                if severity == 'FAULT' and cid not in existing})

    def test_claim_guidance_rejects_invalid_metadata(self):
        seed = json.loads(GUIDANCE.read_text(encoding='utf-8'))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'guidance.json'
            fault_id = 'inventory_empty_v1'
            for defect, reason in [
                ('unknown', 'unknown_id'), ('overlap', 'overlapping_id'), ('missing_id', 'missing_id'),
                ('missing_text', 'text'), ('empty_text', 'text'), ('healthy_fix', 'fix'),
                ('observation_fix', 'fix'), ('missing_fix', 'fix'), ('bad_fix', 'fix'),
            ]:
                with self.subTest(defect=defect):
                    doc = copy.deepcopy(seed)
                    claims = doc['claims']
                    if defect == 'unknown':
                        claims['unknown_id'] = claims[fault_id]
                    elif defect == 'overlap':
                        claims['gp01_dns_all_resolvers_down_v1'] = claims[fault_id]
                    elif defect == 'missing_id':
                        del claims[fault_id]
                    elif defect == 'missing_text':
                        del claims[fault_id]['text_vi']
                    elif defect == 'empty_text':
                        claims[fault_id]['text_vi'] = '  '
                    elif defect in {'healthy_fix', 'observation_fix'}:
                        cid = 'inventory_present_v1' if defect == 'healthy_fix' else 'igate_inventory_complete_v1'
                        claims[cid]['fix_vi'] = claims[fault_id]['fix_vi']
                    elif defect == 'missing_fix':
                        del claims[fault_id]['fix_vi']
                    else:
                        claims[fault_id]['fix_vi'] = ['Một bước.']
                    path.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
                    with self.assertRaisesRegex(PlanError, f'claim_guidance_{reason}$'):
                        load_claim_guidance(self.profile, path)
            duplicate = json.dumps(seed, ensure_ascii=False).replace(f'"{fault_id}":', f'"{fault_id}": {{}}, "{fault_id}":')
            path.write_text(duplicate, encoding='utf-8')
            with self.assertRaisesRegex(PlanError, 'duplicate_json_key$'):
                load_claim_guidance(self.profile, path)

    def test_healthy_offered_cards_are_returned_but_not_executed(self):
        sid = self.session()
        with patch.object(self.launcher, 'run', wraps=self.launcher.run) as run:
            status, result = request('/api/skills/run_selected', {
                'session_id': sid, 'skill_ids': ['A02'], 'offered_ids': ['F02', 'A02', 'GP01'],
            })
            self.assertEqual(status, HTTPStatus.OK, result)
            self.assertEqual([c.args for c in run.call_args_list], [(sid, 'A02')])
        self.assertEqual(result['next_steps']['kind'], 'healthy')
        self.assertEqual([card['skill_id'] for card in result['unrun_cards']], ['F02', 'GP01'])
        self.assertNotIn('unrun_cards', self.chat.run_selected(sid, ['A02']))

    def test_generic_scenarios_keep_working_with_warning_and_next_steps(self):
        for scenario, verdict in [('fault', 'FAULT'), ('missing', 'UNKNOWN')]:
            with self.subTest(scenario=scenario):
                triage = self.chat.triage('Kiểm kê thiết bị trong mạng', scenario=scenario)
                result = self.chat.run_selected(triage['session_id'], ['A02'])
                self.assertEqual(result['warning'], triage['warning'])
                self.assertIn('từng phép kiểm tra', result['warning'])
                self.assertEqual((result['verdict'], result['next_steps']['kind']), (verdict, verdict.lower()))
                self.assertNotIn('Điều kiện mô phỏng:', result['answer'])
                if scenario == 'fault':
                    self.assertIn('Router không thấy thiết bị nào trong danh sách kết nối.', result['answer'])
                    self.assertTrue(all(s['from'] == 'A02 · inventory_empty_v1'
                                        for s in result['next_steps']['steps']))
                    self.assertNotIn('incident_guidance', result)
                else:
                    self.assertTrue(result['next_steps']['sources'])
                    self.assertTrue(all(source.startswith('A02 · ') for source in result['next_steps']['sources']))

    def test_direct_replay_uses_the_same_guidance_for_single_results(self):
        for scenario, expected in [('normal', 'healthy'), ('fault', 'fault'), ('missing', 'unknown')]:
            with self.subTest(scenario=scenario):
                sid = self.session(scenario)
                direct = self.chat.chat('A02', mode='replay_sim', session_id=sid, allow_model=False)
                self.assertEqual(direct['routing']['plan'], ['A02'])
                triage = self.chat.run_selected(sid, ['A02'])
                self.assertEqual(direct['next_steps'], triage['next_steps'])
                self.assertEqual(direct['next_steps']['kind'], expected)
                self.assertIn('Cần làm gì:', direct['answer'])
                self.assertNotIn('Điều kiện mô phỏng:', direct['answer'])
                for claim in triage['triage_results'][0]['claims']:
                    self.assertIn(claim, direct['answer'])

    def test_direct_replay_and_igate_drop_expired_claims_and_advice(self):
        run = self.launcher.run

        def expire_after_run(*args, **kwargs):
            result = run(*args, **kwargs)
            self.assertEqual(result['verdict'], 'FAULT')
            self.now += max(row['expires_in_s'] for row in result['evidence']) + 1
            return result

        for query, skill in [('A02', 'A02'), ('Có Internet không?', 'IG03')]:
            with self.subTest(skill=skill):
                sid = self.session('fault')
                with patch.object(self.launcher, 'run', side_effect=expire_after_run):
                    result = self.chat.chat(query, mode='replay_sim', session_id=sid, allow_model=False)
                self.assertEqual(result['routing']['plan'], [skill])
                self.assertEqual((result['verdict'], result['assessment']['verdict'], result['next_steps']['kind']),
                                 ('UNKNOWN', 'UNKNOWN', 'unknown'))
                self.assertEqual((result['evidence'], result['evidence_ids']), ([], []))
                self.assertTrue(all(event['evidence_id'] is None for event in result['timeline']))
                self.assertTrue(result['next_steps']['sources'])

    def test_expired_required_source_suppresses_advice_even_with_fresh_claim_proof(self):
        sid = self.session('fault')
        run = self.launcher.run

        def expire_only_link(*args, **kwargs):
            result = run(*args, **kwargs)
            self.assertEqual(result['verdict'], 'FAULT')
            link = next(row for row in result['evidence'] if row['sample'] == 'link')
            self.assertNotIn(link['id'], result['evidence_ids'])
            link['expires_in_s'] = 1
            self.now += 2
            return result

        with patch.object(self.launcher, 'run', side_effect=expire_only_link):
            result = self.chat.run_selected(sid, ['SK04'])
        self.assertEqual((result['verdict'], result['case_status'], result['next_steps']['kind']),
                         ('UNKNOWN', 'PARTIAL', 'unknown'))
        self.assertTrue(result['evidence'])
        self.assertEqual(result['evidence_ids'], [])
        self.assertEqual(result['next_steps']['sources'], ['SK04 · link'])

    def test_server_reports_unapproved_replay(self):
        with patch.object(self.launcher, 'create_session',
                          side_effect=PlanError('binding_v02:skill_deployment_not_approved')):
            status, body = request('/api/skills/triage', {'message': 'DNS'})
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        self.assertEqual(body['reason'], 'skill_deployment_not_approved')
        self.assertTrue(body['synthetic_only'])

    def test_model_opt_in_is_server_side_and_only_changes_order(self):
        query = 'Sức khỏe router'
        sid = self.session()
        payload = {'message': query, 'session_id': sid}
        expected = self.chat.triage(query, sid)['cards']
        preferred = expected[-1]['skill_id']
        self.model.choose_skills.return_value = self.proposal([preferred])
        with patch.dict('os.environ', {'GATEWAY_LM_TRIAGE_MODEL': '1'}):
            status, result = request('/api/skills/triage', payload)
            self.assertEqual(status, HTTPStatus.OK, result)
            self.assertEqual(result['cards'], expected[-1:] + expected[:-1])
            status, result = request('/api/skills/triage', {**payload, 'allow_model': True})
            self.assertEqual(status, HTTPStatus.BAD_REQUEST, result)

    def test_expired_session_cannot_return_cards_after_rerank(self):
        sid = self.session()

        def close_during_inference(*args):
            self.launcher.close(sid)
            return self.proposal(['SK08'])

        self.model.choose_skills.side_effect = close_during_inference
        with self.assertRaisesRegex(ValueError, 'session_expired'):
            self.chat.triage('Sức khỏe router', sid, allow_model=True)
