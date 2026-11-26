"""Vietnamese presentation metadata for already-assessed replay claims."""
from __future__ import annotations

from collections.abc import Sequence
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from ..adapters.bindings import require
from ..command_catalog.loader import read_json
from ..skill_expansion.catalog import DATA_DIR
from ..skill_expansion.incident_replay import ADVISORY, _text, _texts
from ..skill_expansion.replay_sim import ReplayProfile, ReplaySession

GUIDANCE = DATA_DIR / 'claim_guidance_v1.json'
RELATIONS = DATA_DIR / 'claim_relations_v1.json'
GENERIC_WARNING = {
    'fault': 'Kịch bản fault tạo lỗi riêng cho từng phép kiểm tra, nên các lỗi có thể không cùng xảy ra trên một router.',
    'missing': 'Kịch bản missing làm thiếu dữ liệu riêng cho từng phép kiểm tra, nên kết quả không mô tả một router chung.',
}


def _claim_severities(profile: ReplayProfile) -> dict[str, str]:
    diagnostics = [diagnostic for catalog in (profile, profile.igate, profile.incidents)
                   for diagnostic in catalog.diagnostics['skills'].values()]
    diagnostics.extend(diagnostic for _, diagnostic in profile.incident_replay.joint_checks.values())
    return {claim['claim_id']: claim['severity'] for diagnostic in diagnostics for claim in diagnostic['claims']}


def load_claim_guidance(profile: ReplayProfile, path: Path = GUIDANCE) -> dict:
    doc = read_json(path, max_bytes=128 * 1024)
    require(set(doc) == {'format', 'note_vi', 'claims', 'next_steps_vi'}
            and doc['format'] == 'gateway-lm.claim-guidance/v1' and _text(doc['note_vi'])
            and type(doc['claims']) is dict and type(doc['next_steps_vi']) is dict
            and set(doc['next_steps_vi']) == {'healthy', 'unknown'}
            and all(map(_texts, doc['next_steps_vi'].values())), 'claim_guidance_format')
    severities = _claim_severities(profile)
    existing = profile.incidents.diagnostics['claim_text'] | profile.incident_replay.claim_text
    claims = doc['claims']
    require(all(type(claims[cid]) is dict and 'text_vi' not in claims[cid]
                for cid in claims.keys() & existing.keys()), 'claim_guidance_overlapping_id')
    require(claims.keys() <= severities.keys(), 'claim_guidance_unknown_id')
    require((claims.keys() | existing.keys()) == severities.keys(), 'claim_guidance_missing_id')
    for cid, row in claims.items():
        if cid in existing:
            require(set(row) == {'fix_vi'}, 'claim_guidance_fix')
        else:
            require(type(row) is dict and {'text_vi'} <= row.keys() <= {'text_vi', 'fix_vi'}
                    and _text(row['text_vi']) and len(row['text_vi'].splitlines()) == 1, 'claim_guidance_text')
        if severities[cid] == 'FAULT':
            steps = row.get('fix_vi')
            require(_texts(steps) and 2 <= len(steps) <= 4
                    and all(len(step.splitlines()) == 1 for step in steps), 'claim_guidance_fix')
        else:
            require('fix_vi' not in row, 'claim_guidance_fix')
    return {'text': {**{cid: row['text_vi'] for cid, row in claims.items() if cid not in existing}, **existing},
            'fix': {cid: row['fix_vi'] for cid, row in claims.items() if 'fix_vi' in row},
            'next_steps': doc['next_steps_vi']}


def relation_depths(relations: dict[str, list[str]], active: set[str]) -> dict[str, int]:
    """Rank only present endpoints. An absent intermediate Claim breaks the chain."""
    predecessors: dict[str, list[str]] = {}
    for cause, effects in relations.items():
        if cause in active:
            for effect in effects:
                if effect in active:
                    predecessors.setdefault(cause, [])
                    predecessors.setdefault(effect, []).append(cause)
    depths: dict[str, int] = {}
    for cid in TopologicalSorter(predecessors).static_order():
        depths[cid] = 1 + max((depths[parent] for parent in predecessors[cid]), default=-1)
    return depths


def load_claim_relations(profile: ReplayProfile, path: Path = RELATIONS) -> dict[str, list[str]]:
    relations = read_json(path)
    severities = _claim_severities(profile)
    for cause, effects in relations.items():
        require(_texts(effects) and len(effects) == len(set(effects)), 'claim_relations_effects')
        require(all(cid in severities for cid in [cause, *effects]), 'claim_relations_unknown_id')
        require(all(severities[cid] == 'FAULT' for cid in [cause, *effects]), 'claim_relations_non_fault')
    try:
        relation_depths(relations, set(severities))
    except CycleError:
        require(False, 'claim_relations_cycle')
    return relations


def evidenced_claims(run: dict, evidence: dict[str, dict]) -> dict[str, dict]:
    return {cid: claim for cid, claim in run.get('assessment', {}).get('claims', {}).items()
            if claim['value'] == 'TRUE' and claim['evidence'] and set(claim['evidence']) <= evidence.keys()}


def missing_sources(run: dict) -> list[str]:
    return list(dict.fromkeys([*run.get('missing_sources', []), *run.get('source_errors', {})]))


def incident_recommendation(replay: ReplaySession, run: dict, claims: dict[str, dict],
                            evidence: dict[str, dict]) -> dict | None:
    if not run.get('incident_guidance'):
        return None
    proof = [eid for claim in claims.values() if claim['severity'] == 'FAULT' for eid in claim['evidence']]
    return replay.profile.incident_replay.recommendation(replay.scenario, proof, list(evidence.values()))


def _fault_steps(guidance: dict, faults: Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    return [(step, f'{sid} · {cid}') for sid, cid in faults for step in guidance['fix'].get(cid, ())]


def _fallback_fault_steps(fault: tuple[str, str]) -> list[tuple[str, str]]:
    sid, cid = fault
    return [(step, f'{sid} · {cid}') for step in (
        'Đối chiếu dấu hiệu trên với mục trạng thái tương ứng trên router thật.',
        'Nếu dấu hiệu lặp lại, ghi thời điểm và gửi kết quả kiểm tra cho bộ phận hỗ trợ.',
    )]


def build_next_steps(guidance: dict, verdict: str, *, faults: list[tuple[str, str]],
                     incident: dict | None = None, incident_from: str = '', missing: Sequence[str] = (),
                     primary_faults: Sequence[tuple[str, str]] = ()) -> dict:
    sources = []
    if verdict == 'FAULT':
        primary = _fault_steps(guidance, primary_faults)
        if primary_faults and not primary:
            primary = _fallback_fault_steps(primary_faults[0])
        steps = primary + ([(step, incident_from) for step in incident['steps']] if incident else [])
        sources = incident['sources'] if incident else []
        steps.extend(_fault_steps(guidance, faults))
        if not steps:
            steps = _fallback_fault_steps(faults[0])
    else:
        steps = [(step, 'Hướng dẫn chung') for step in guidance['next_steps'][verdict.lower()]]
        if verdict == 'UNKNOWN':
            sources = list(dict.fromkeys(missing))
    unique = {}
    for step, origin in steps:
        unique.setdefault(step, origin)
    return {'label': ADVISORY, 'kind': verdict.lower(),
            'steps': [{'text': step, 'from': origin} for step, origin in list(unique.items())[:6]],
            **({'sources': sources} if sources else {})}


def next_steps_text(next_steps: dict, *, compact: bool = False) -> str:
    heading = f"Cần làm gì: {next_steps['label']}"
    if compact:
        return ' '.join([f'{heading}.', *(step['text'] for step in next_steps['steps'][:2])])
    return '\n'.join([heading, *(f"• {step['text']}" for step in next_steps['steps'][:3])])


def single_result_guidance(replay: ReplaySession, run: dict) -> tuple[list[str], dict]:
    guidance = load_claim_guidance(replay.profile)
    fresh = {row['id']: row for row in run.get('evidence', [])}
    claims = evidenced_claims(run, fresh)
    sid = run['skill_id']
    verdict = run['verdict']
    matching = [cid for cid, claim in claims.items() if claim['severity'] == verdict]
    if not matching:
        verdict = 'UNKNOWN'
    incident = incident_recommendation(replay, run, claims, fresh) if verdict == 'FAULT' else None
    return list(dict.fromkeys(guidance['text'][cid] for cid in claims)), build_next_steps(
        guidance, verdict, faults=[(sid, cid) for cid in matching] if verdict == 'FAULT' else [],
        incident=incident, incident_from=f'{replay.scenario} · {sid}',
        missing=[f'{sid} · {source}' for source in missing_sources(run)],
    )
