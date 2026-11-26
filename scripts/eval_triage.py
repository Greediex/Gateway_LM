"""Offline role-play intake benchmark. Only explicit --split test opens the holdout."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import statistics
import subprocess
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.application.skill_triage import TAXONOMY
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.skill_expansion.deployment import deployment
from gateway_pilot.skill_expansion.incident_replay import DIRECTORY as INCIDENTS
from gateway_pilot.skill_expansion.replay_sim import MODE, TARGET, ReplayProfile, ReplaySession, SimulationReplayBackend
from gateway_pilot.workflow import normalize

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data/eval/triage_eval_v1'
LABEL_SOURCE = 'ai_draft_needs_human_review'
STYLES = {'story', 'indirect', 'no_diacritics', 'teencode', 'typo', 'mixed', 'off_topic', 'write_request'}
REFUSALS = {'write_intent_requires_approval', 'custom_target_not_supported'}
INCIDENT_MAP = {
    'SYM-01-dhcp-het-ip': 'INC-DHCP-EXHAUST',
    'SYM-02-dns-hong': 'INC-DNS-FAIL',
    'SYM-03-mat-mang-ca-nha': 'INC-WAN-DOWN',
    'SYM-04-wifi-cham-toi': 'INC-24G-COCHANNEL',
    'SYM-05-song-yeu': 'INC-WEAK-SIGNAL',
    'SYM-06-bufferbloat': 'INC-BUFFERBLOAT',
    'SYM-07-mtu-pppoe': 'INC-PPPOE-MTU',
    'SYM-08-cgnat-camera': 'INC-CGNAT',
    'SYM-09-double-nat': 'INC-DOUBLE-NAT',
    'SYM-10-ipv6-cham': 'INC-IPV6-BROKEN',
    'SYM-11-dfs-5g-rot': 'INC-DFS-RADAR',
    'SYM-12-bam-diem-phat-xa': 'INC-STICKY-CLIENT',
    'SYM-13-router-nong-reboot': 'INC-OVERHEAT-REBOOT',
    'SYM-14-qua-tai-toi': 'INC-CAPACITY',
    'SYM-15-router-qua-tai': 'INC-CAPACITY',
}


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def case_split(case_id: str) -> str:
    return 'dev' if int(sha256(case_id.encode('utf-8')), 16) % 100 < 60 else 'test'


def routing_phrases(taxonomy: list[dict], profile: ReplayProfile) -> set[str]:
    routing = read_json(INCIDENTS / 'routing.json')['phrases']
    refs = read_json(INCIDENTS / 'router_incidents_v1.json')['incidents']
    phrase_lists = [
        *(g['user_says'] for g in taxonomy),
        *(row['user_says'] for row in refs),
        *routing.values(),
        *profile.diagnostics['routing']['phrases'].values(),
        *profile.incidents.diagnostics['routing'].values(),
    ]
    return {phrase for phrases in phrase_lists for raw in phrases if (phrase := normalize(raw))}


def unique_ids(value: object, allowed: set[str]) -> bool:
    return (isinstance(value, list) and all(isinstance(v, str) and v in allowed for v in value)
            and len(value) == len(set(value)))


def validate_cases(rows: list[dict], groups: set[str], skills: set[str], phrases: set[str]) -> None:
    seen_ids, seen_texts = set(), set()
    for line, row in enumerate(rows, 1):
        if not isinstance(row, dict) or set(row) != {'id', 'text', 'style', 'expected', 'label_source'}:
            raise ValueError(f'line {line}: invalid case fields')
        case_id, text, style, label = (row[k] for k in ('id', 'text', 'style', 'expected'))
        if (not isinstance(case_id, str) or not re.fullmatch(r'TRIAGE-\d{3}', case_id)
                or not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000
                or not isinstance(style, str) or style not in STYLES or row['label_source'] != LABEL_SOURCE):
            raise ValueError(f'line {line}: invalid case metadata')
        normalized = normalize(text)
        if not normalized or normalized in seen_texts or case_id in seen_ids:
            raise ValueError(f'{case_id}: empty or duplicate case')
        seen_texts.add(normalized)
        seen_ids.add(case_id)
        if (not isinstance(label, dict) or not {'groups', 'acceptable_skills'} <= label.keys()
                or label.keys() - {'groups', 'acceptable_skills', 'must_refuse'}
                or not unique_ids(label['groups'], groups) or not unique_ids(label['acceptable_skills'], skills)
                or type(label.get('must_refuse', False)) is not bool
                or (bool(label['acceptable_skills']) == label.get('must_refuse', False))):
            raise ValueError(f'{case_id}: invalid expected labels')
        if any(f' {phrase} ' in f' {normalized} ' for phrase in phrases):
            raise ValueError(f'{case_id}: verbatim routing phrase')


def load_cases(split: str, *, folder: Path = DATA) -> tuple[dict, list[dict]]:
    if split not in ('dev', 'test'):
        raise ValueError('invalid_triage_eval_split')
    meta = read_json(folder / 'SPLIT.json')['splits'][split]
    raw = (folder / f'{split}.jsonl').read_bytes()
    if sha256(raw) != meta['sha256']:
        raise ValueError(f'{split} split SHA-256 mismatch')
    rows = [json.loads(line) for line in raw.splitlines()]
    if len(rows) != meta['cases'] or any(case_split(row['id']) != split for row in rows):
        raise ValueError(f'{split} split membership mismatch')
    return meta, rows


def measure_ratio(hits: int, total: int) -> dict:
    return {'hits': hits, 'total': total, 'rate': hits / total if total else None}


def score(rows: list[dict]) -> dict:
    skills = [row for row in rows if row['expected']['acceptable_skills']]
    groups = [row for row in rows if row['expected']['groups']]
    expected_refusal = sum(row['expected'].get('must_refuse', False) for row in rows)
    actual_refusal = sum(row['refused'] for row in rows)
    true_refusal = sum(row['refused'] and row['expected'].get('must_refuse', False) for row in rows)
    latency = sorted(row['latency_ms'] for row in rows)
    result = {
        f'top{k}': measure_ratio(sum(bool(set(row['cards'][:k]) & set(row['expected']['acceptable_skills']))
                                    for row in skills), len(skills)) for k in (1, 3, 6)
    }
    return dict(result, cases=len(rows),
                group_hit=measure_ratio(sum(bool(set(row['groups']) & set(row['expected']['groups']))
                                            for row in groups), len(groups)),
                refusal_precision=measure_ratio(true_refusal, actual_refusal),
                refusal_recall=measure_ratio(true_refusal, expected_refusal),
                no_card=measure_ratio(sum(not row['cards'] for row in rows), len(rows)),
                latency_ms={'median': statistics.median(latency),
                            'p95': latency[(95 * len(latency) + 99) // 100 - 1],
                            'max': latency[-1]} if latency else None)


def make_chat(profile: ReplayProfile) -> SkillChat:
    # Reuse the validated, locally approved profile. Every case gets a fresh session.
    def compose(mode: str, *, scenario: str) -> dict:
        if mode != MODE:
            raise ValueError('triage_eval_requires_replay_sim')
        return {'session': ReplaySession(profile, scenario), 'actions': profile.actions}

    return SkillChat(SkillLauncher(factory=compose))


@contextmanager
def session(chat: SkillChat, scenario: str = 'normal') -> Iterator[str]:
    sid = chat.launcher.create_session(MODE, scenario=scenario)['session_id']
    try:
        yield sid
    finally:
        chat.launcher.close(sid)


def intake(chat: SkillChat, text: str, sid: str, *, allow_model: bool) -> dict:
    started = time.perf_counter()
    result = chat.triage(text, sid, allow_model=allow_model)
    elapsed_ms = (time.perf_counter() - started) * 1000
    return {'cards': [card['skill_id'] for card in result['cards']],
            'groups': [group['id'] for group in result['symptom_groups']],
            'refused': result.get('stop_reason') in REFUSALS,
            'stop_reason': result.get('stop_reason'), 'latency_ms': elapsed_ms}


def run_triage(chat: SkillChat, cases: list[dict], *, allow_model: bool) -> list[dict]:
    rows = []
    for case in cases:
        with session(chat) as sid:
            prediction = intake(chat, case['text'], sid, allow_model=allow_model)
        rows.append({**prediction, **{key: case[key] for key in ('id', 'style', 'expected')}})
    return rows


def evidenced_fault(result: dict) -> bool:
    fresh = {e['id'] for e in result['evidence']
             if e['status'] == 'OK' and e['expires_in_s'] > 0 and e['target'] == TARGET
             and e['source'] == SimulationReplayBackend.source}
    return result['verdict'] == 'FAULT' and any(
        row['verdict'] == 'FAULT' and row['evidence_ids'] and set(row['evidence_ids']) <= fresh
        for row in result['triage_results'])


def run_selection(chat: SkillChat, sid: str, cards: list[str]) -> dict:
    if not cards:
        return {'verdict': 'NO_CARDS', 'evidenced_fault': False, 'calls': 0}
    result = chat.run_selected(sid, cards[:3], offered_ids=cards)
    return {'verdict': result['verdict'], 'evidenced_fault': evidenced_fault(result), 'calls': result['calls']}


def run_incidents(chat: SkillChat, cases: list[dict], *, allow_model: bool) -> dict:
    trials = []
    for case in cases:
        label = case['expected']
        if label.get('must_refuse', False):
            continue
        worlds = dict.fromkeys(INCIDENT_MAP[group] for group in label['groups'] if group in INCIDENT_MAP)
        for world in worlds:
            with session(chat, world) as sid:
                cards = intake(chat, case['text'], sid, allow_model=allow_model)['cards']
                incident = run_selection(chat, sid, cards)
            with session(chat) as sid:
                normal = run_selection(chat, sid, cards)
            trials.append({'id': case['id'], 'scenario': world, 'selected': cards[:3],
                           'incident': incident, 'normal': normal})
    return {
        'cases': len({row['id'] for row in trials}), 'worlds': len({row['scenario'] for row in trials}),
        'fault_with_evidence': measure_ratio(sum(row['incident']['evidenced_fault'] for row in trials), len(trials)),
        'false_fault_normal': measure_ratio(sum(row['normal']['verdict'] == 'FAULT' for row in trials), len(trials)),
        'incident_verdicts': dict(Counter(row['incident']['verdict'] for row in trials)),
        'normal_verdicts': dict(Counter(row['normal']['verdict'] for row in trials)),
        'trials': trials,
    }


def cell(metric: dict) -> str:
    if metric['rate'] is None:
        return '— (0/0)'
    return f"{metric['rate']:.1%} ({metric['hits']}/{metric['total']})"


def print_table(overall: dict, styles: dict[str, dict]) -> None:
    metrics = ['top1', 'top3', 'top6', 'group_hit', 'refusal_precision', 'refusal_recall', 'no_card']
    print('| Style | Cases | Top-1 | Top-3 | Top-6 | Group | Ref. precision | Ref. recall | No card | Median / p95 / max ms |')
    print('|' + '---|' * 10)
    for label, row in [('all', overall), *styles.items()]:
        latency = ' / '.join(f'{row["latency_ms"][p]:.2f}' for p in ('median', 'p95', 'max'))
        print('| ' + ' | '.join([label, str(row['cases']), *(cell(row[k]) for k in metrics), latency]) + ' |')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--split', choices=('dev', 'test'), default='dev')
    parser.add_argument('--with-llm', action='store_true', help='Allow the configured local model to rerank cards.')
    parser.add_argument('--incidents', action='store_true', help='Run paired dev incident and normal READ replays.')
    args = parser.parse_args(argv)
    if args.incidents and args.split != 'dev':
        parser.error('--incidents requires --split dev')
    meta, cases = load_cases(args.split)
    profile = deployment(MODE)
    taxonomy = read_json(TAXONOMY)['groups']
    skills = profile.actions.keys() | profile.incidents.actions.keys() | profile.igate.actions.keys()
    validate_cases(cases, {g['id'] for g in taxonomy}, skills, routing_phrases(taxonomy, profile))
    chat = make_chat(profile)
    scored = run_triage(chat, cases, allow_model=args.with_llm)
    overall = score(scored)
    styles = {style: score([row for row in scored if row['style'] == style])
              for style in sorted({row['style'] for row in scored})}
    now = datetime.now(timezone.utc)
    report = {
        'format': 'gateway-lm.triage-eval/v1', 'created_at': now.isoformat(),
        'commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'split': args.split, 'split_sha256': meta['sha256'], 'label_source': LABEL_SOURCE,
        'mode': MODE, 'synthetic_only': True, 'replay_pins': profile.approval, 'allow_model': args.with_llm,
        'configured_model': os.environ.get('GATEWAY_LM_CHAT_MODEL', 'qwen3:4b') if args.with_llm else None,
        'overall': overall, 'by_style': styles,
    }
    if args.split == 'dev':
        report['predictions'] = [{k: v for k, v in row.items() if k != 'expected'} for row in scored]
    if args.incidents:
        report['incidents'] = run_incidents(chat, cases, allow_model=args.with_llm)
    out = ROOT / 'runs' / f"triage_eval_v1_{args.split}_{now.strftime('%Y%m%dT%H%M%S%fZ')}.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'{args.split} · {LABEL_SOURCE} · allow_model={args.with_llm}')
    print_table(overall, styles)
    if args.incidents:
        incident = report['incidents']
        print(f"FAULT with evidence {cell(incident['fault_with_evidence'])}; "
              f"false FAULT on normal {cell(incident['false_fault_normal'])}")
    print(out.relative_to(ROOT))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
