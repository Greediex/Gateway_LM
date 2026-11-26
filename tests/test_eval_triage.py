"""Evaluation-only contracts for the triage v1 holdout and scorer."""
from __future__ import annotations

import builtins
import io
import json
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gateway_pilot.application.skill_triage import load_taxonomy
from gateway_pilot.skill_expansion.replay_sim import ReplayProfile, SimulationReplayBackend
from scripts import eval_triage as ev, suggest_phrases

LOCKED_TEST_SHA256 = 'ca02bf8a29b1e1500d663118cd4e4c35a6f98ea44689f70c4596fffb3cb2bf40'


def scored(cards=(), groups=(), wanted=(), acceptable=(), must_refuse=False, refused=False, ms=0):
    return dict(cards=list(cards), groups=list(groups), refused=refused, latency_ms=ms,
                expected=dict(groups=list(wanted), acceptable_skills=list(acceptable), must_refuse=must_refuse))


class TriageEvalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.profile = ev.deployment(ev.MODE)
        cls.skill_ids = cls.profile.actions.keys() | cls.profile.incidents.actions.keys() | cls.profile.igate.actions.keys()
        cls.taxonomy = ev.read_json(ev.TAXONOMY)['groups']
        cls.groups = {group['id'] for group in cls.taxonomy}
        cls.phrases = ev.routing_phrases(cls.taxonomy, cls.profile)

    def test_schema_and_verbatim_leak_guard(self):
        rows = [json.loads(line) for line in (ev.DATA / 'cases.jsonl').read_bytes().splitlines()]
        self.assertEqual(len(rows), 250)
        ev.validate_cases(rows, self.groups, self.skill_ids, self.phrases)
        self.assertEqual({row['style'] for row in rows}, ev.STYLES)
        self.assertEqual({g for row in rows for g in row['expected']['groups']}, self.groups)
        self.assertEqual(set(ev.INCIDENT_MAP.values()), self.profile.incident_replay.measurements.keys())
        self.assertTrue(ev.INCIDENT_MAP.keys() <= self.groups)
        row = rows[0]
        for changes, reason in [
            ({'text': 'Tôi bị: CÓ WI-FI MÀ KHÔNG VÀO ĐƯỢC WEB!'}, 'verbatim'),
            ({'text': 'Chào bạn — khách đến nhà KHÔNG kết nối được.'}, 'verbatim'),
            ({'text': 'Có liên quan tới DNS?'}, 'verbatim'),
            ({'expected': {**row['expected'], 'acceptable_skills': ['SK13']}}, 'labels'),
            ({'expected': {**row['expected'], 'groups': ['SYM-99']}}, 'labels'),
            ({'expected': {**row['expected'], 'must_refuse': 1}}, 'labels'),
            ({'label_source': 'human_verified'}, 'metadata'),
        ]:
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, reason):
                ev.validate_cases([{**row, **changes}], self.groups, self.skill_ids, self.phrases)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            ev.validate_cases([row, row], self.groups, self.skill_ids, self.phrases)

    def test_split_determinism_and_locked_test_bytes(self):
        archive = (ev.DATA / 'cases.jsonl').read_bytes().splitlines(keepends=True)
        for split, count in [('dev', 151), ('test', 99)]:
            meta, cases = ev.load_cases(split)
            expected = b''.join(line for line in archive if ev.case_split(json.loads(line)['id']) == split)
            self.assertEqual((ev.DATA / f'{split}.jsonl').read_bytes(), expected)
            self.assertEqual(len(cases), count)
            self.assertEqual(meta['sha256'], ev.sha256(expected))
        self.assertEqual(ev.sha256((ev.DATA / 'test.jsonl').read_bytes()), LOCKED_TEST_SHA256)
        with TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'SPLIT.json').write_bytes((ev.DATA / 'SPLIT.json').read_bytes())
            (folder / 'test.jsonl').write_bytes(expected + b'\n')
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                ev.load_cases('test', folder=folder)

    def test_no_full_dev_or_test_request_is_in_the_taxonomy(self):
        for split in ('dev', 'test'):
            with self.subTest(split=split):
                _, cases = ev.load_cases(split)
                for path in (ev.TAXONOMY, ev.SIGNALS):
                    ev.validate_taxonomy_leaks(cases, ev.read_json(path))
        example = {'text': 'Đường mạng chậm gần cửa sổ.'}
        for taxonomy in [
            {'groups': [{'user_says': ['Đường mạng']}]},
            {'groups': {'some-group': [['chậm', 'cửa sổ']]}},
        ]:
            ev.validate_taxonomy_leaks([example], taxonomy)
        with self.assertRaisesRegex(ValueError, 'verbatim eval request'):
            ev.validate_taxonomy_leaks([example], {'groups': {'some-group': [
                ['Ví dụ: DUONG MANG CHAM GAN CUA SO!']]}})

    def test_scorer_uses_eligible_denominators_and_counts_explicit_refusals(self):
        stats = ev.score([
            scored(['A01', 'B02'], ['other', 'g'], ['g'], ['B02'], ms=1),
            scored(['A01', 'B02', 'C03', 'D04'], [], ['g', 'h'], ['D04'], refused=True, ms=2),
            scored(must_refuse=True, refused=True, ms=3),
            scored(must_refuse=True, ms=4),
        ])
        for key, counts in {'top1': (0, 2), 'top3': (1, 2), 'top6': (2, 2),
                            'group_hit': (1, 2), 'refusal_precision': (1, 2),
                            'refusal_recall': (1, 2), 'no_card': (2, 4)}.items():
            self.assertEqual(stats[key], ev.measure_ratio(*counts))
        self.assertEqual(stats['latency_ms'], {'median': 2.5, 'p95': 4, 'max': 4})
        self.assertIsNone(ev.score([scored()])['refusal_precision']['rate'])

    def test_cli_opens_only_the_selected_split(self):
        for argv, split in [([], 'dev'), (['--split', 'dev'], 'dev'), (['--split', 'test'], 'test')]:
            with (self.subTest(argv=argv), TemporaryDirectory() as directory,
                  patch.object(ev, 'ROOT', Path(directory)),
                  patch.object(ev.subprocess, 'check_output', return_value='reference\n'),
                  patch.object(ev, 'deployment', return_value=self.profile),
                  patch.object(ev, 'run_triage', return_value=[{**scored(), 'style': 'story'}]),
                  patch('io.open', wraps=io.open) as opened, redirect_stdout(io.StringIO())):
                self.assertEqual(ev.main(argv), 0)
                files = {Path(call.args[0]).name for call in opened.call_args_list
                         if not isinstance(call.args[0], int) and Path(call.args[0]).parent == ev.DATA}
                self.assertEqual(files, {'SPLIT.json', f'{split}.jsonl'})

    def test_tuning_entry_points_do_not_read_the_holdout(self):
        locked = {ev.DATA / 'cases.jsonl', ev.DATA / 'test.jsonl', ev.DATA / 'REVIEW.md'}

        def guard(open_file):
            def checked(path, *args, **kwargs):
                if not isinstance(path, int):
                    self.assertNotIn(Path(path).resolve(), locked)
                return open_file(path, *args, **kwargs)
            return checked

        with (patch('io.open', side_effect=guard(io.open)),
              patch('builtins.open', side_effect=guard(builtins.open)),
              patch('sys.argv', ['suggest_phrases', 'B04']), redirect_stdout(io.StringIO())):
            self.assertTrue(load_taxonomy(self.skill_ids))
            self.assertEqual(suggest_phrases.main(), 0)

    def test_intake_uses_only_request_text_and_cannot_read(self):
        chat = ev.make_chat(self.profile)
        case = {'id': 'fixture', 'style': 'mixed', 'text': 'Đổi mật khẩu mạng không dây giúp tôi.',
                'expected': {'groups': ['untrusted label'], 'acceptable_skills': [], 'must_refuse': True}}
        with (patch.object(chat, 'triage', wraps=chat.triage) as triage,
              patch.object(chat.launcher, 'run', side_effect=AssertionError('intake attempted READ')),
              patch.object(ReplayProfile, 'open_sample', side_effect=AssertionError('intake opened a sample'))):
            rows = ev.run_triage(chat, [case], allow_model=False)
        triage.assert_called_once_with(case['text'], triage.call_args.args[1], allow_model=False)
        self.assertEqual(rows[0]['expected'], case['expected'])
        self.assertEqual(rows[0]['cards'], [])

    def test_fault_requires_evidence_from_the_faulting_skill_and_current_world(self):
        evidence = {'id': 'ev-1', 'status': 'OK', 'expires_in_s': 1, 'target': ev.TARGET,
                    'source': SimulationReplayBackend.source}
        result = {'verdict': 'FAULT', 'evidence': [evidence],
                  'triage_results': [{'verdict': 'FAULT', 'evidence_ids': ['ev-1']}]}
        self.assertTrue(ev.evidenced_fault(result))
        for defect in [{'id': 'other'}, {'status': 'REJECTED'}, {'expires_in_s': 0},
                       {'target': 'other-target'}, {'source': 'external'}]:
            with self.subTest(defect=defect):
                self.assertFalse(ev.evidenced_fault({**result, 'evidence': [{**evidence, **defect}]}))
        self.assertFalse(ev.evidenced_fault({**result, 'triage_results': [
            {'verdict': 'FAULT', 'evidence_ids': []}, {'verdict': 'HEALTHY', 'evidence_ids': ['ev-1']}]}))

    def test_incident_and_control_use_same_top_three_through_core(self):
        chat = ev.make_chat(self.profile)
        cards = ['GP01', 'A02', 'B04', 'F02']
        case = {'id': 'fixture', 'text': 'Synthetic question',
                'expected': {'groups': ['SYM-02-dns-hong']}}
        with (patch.object(ev, 'intake', return_value={'cards': cards}),
              patch.object(chat, 'run_selected', wraps=chat.run_selected) as run):
            result = ev.run_incidents(chat, [case], allow_model=False)
        self.assertEqual(result['fault_with_evidence'], ev.measure_ratio(1, 1))
        self.assertEqual(result['false_fault_normal'], ev.measure_ratio(0, 1))
        self.assertEqual(result['normal_verdicts'], {'HEALTHY': 1})
        self.assertEqual([call.args[1] for call in run.call_args_list], [cards[:3], cards[:3]])
        self.assertNotEqual(run.call_args_list[0].args[0], run.call_args_list[1].args[0])
        self.assertTrue(all(row['calls'] > 0 for row in
                            (result['trials'][0]['incident'], result['trials'][0]['normal'])))
