"""Suggest approved replay Skills and summarize their verified READ results."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ..adapters.bindings import require
from ..command_catalog.loader import read_json
from ..skill_expansion.catalog import DATA_DIR
from ..skill_expansion.incident_replay import ADVISORY, _source_url, _text, _texts
from ..skill_expansion.replay_sim import MODE, NOTICE, ReplaySession
from ..workflow import normalize
from .skill_chat import (
    _MODEL_SLOT, _phrase, _replay_candidates, _replay_refusal, _replay_scopes,
    _retriever, local_model, validate_choice,
)

if TYPE_CHECKING:
    from .skill_chat import SkillChat

MAX_CARDS = 6
OWN_HOME_PHRASES = frozenset({'router nha toi', 'router cua toi', 'wifi nha toi'})
TAXONOMY = DATA_DIR / 'symptom_taxonomy_v1.json'


def load_taxonomy(approved_ids: set[str], path: Path = TAXONOMY) -> list[dict]:
    doc = read_json(path)
    require(set(doc) == {'format', 'note_vi', 'groups'}
            and doc['format'] == 'gateway-lm.symptom-taxonomy/v1'
            and _text(doc['note_vi']) and type(doc['groups']) is list and bool(doc['groups']),
            'skill_triage_taxonomy_format')
    groups = []
    group_ids = set()
    fields = {'id', 'label_vi', 'user_says', 'cards', 'sources'}
    for group in doc['groups']:
        require(type(group) is dict and fields <= group.keys() <= fields | {'gap_vi'},
                'skill_triage_taxonomy_group_fields')
        group_id = group['id']
        require(_text(group_id) and group_id == group_id.strip() and group_id not in group_ids,
                'skill_triage_taxonomy_group_id')
        group_ids.add(group_id)
        require(_text(group['label_vi']) and _text(group.get('gap_vi', '—'))
                and _texts(group['user_says']) and _texts(group['sources'])
                and all(map(_source_url, group['sources']))
                # A surveyed symptom with no fitting Skill is kept as a documented gap.
                and type(group['cards']) is list and (bool(group['cards']) or 'gap_vi' in group),
                'skill_triage_taxonomy_group')
        phrases = list(map(normalize, group['user_says']))
        require(all(phrases) and len(set(phrases)) == len(phrases), 'skill_triage_taxonomy_phrases')
        skill_ids = set()
        for card in group['cards']:
            require(type(card) is dict and set(card) == {'skill_id', 'plain_vi', 'why_vi'}
                    and all(map(_text, card.values())), 'skill_triage_taxonomy_card')
            skill_id = card['skill_id']
            require(skill_id in approved_ids, 'skill_triage_taxonomy_unknown_skill')
            require(skill_id not in skill_ids, 'skill_triage_taxonomy_duplicate_skill')
            skill_ids.add(skill_id)
        groups.append({**group, 'user_says': phrases})
    return groups


def replay_rows(catalog: dict) -> dict[str, dict]:
    return {row['skill_id']: row for key in ('rows', 'incident_rows', 'igate_rows') for row in catalog[key]
            if row['availability'] == 'READY'}


def propose(chat: SkillChat, request: str, session_id: str, entry: dict, started: float, *,
            allow_model: bool) -> dict:
    replay = entry['session']
    profile = replay.profile
    rows = replay_rows(chat.launcher.catalog(MODE, entry=entry))
    routing = profile.diagnostics['routing']
    incident_phrases = profile.incident_replay.symptom_routes
    text = normalize(request)
    response = {'session_id': session_id, 'mode': MODE, 'scenario': replay.scenario, 'synthetic_only': True,
                'cards': [], 'symptom_groups': [], 'notice': NOTICE}
    # Role-play speaks as the owner of the simulated home; other real-device phrases stay refused.
    role_play = {**routing, 'nonlocal_scope_phrases': [
        p for p in routing['nonlocal_scope_phrases'] if p not in OWN_HOME_PHRASES]}
    refusal = _replay_refusal(request, text, rows, role_play, incident_phrases.get(text))
    if refusal:
        reason, status, message = refusal
        return dict(response, stop_reason=reason, case_status=status, answer=f'{NOTICE}\n{message}')

    scopes = _replay_scopes(text)
    eligible = {sid: row for sid, row in rows.items() if not scopes or row['runtime_scope'] in scopes}
    cards: dict[str, dict] = {}

    def add(sid: str, source: str, *, plain_vi: str = '', why_vi: str = '') -> None:
        if sid not in eligible or sid in cards or len(cards) >= MAX_CARDS:
            return
        name = eligible[sid]['name']
        cards[sid] = {'skill_id': sid, 'name': name, 'plain_vi': plain_vi or name,
                      'why_vi': why_vi or {
                          'incident': 'Phép kiểm tra đã được liên kết với mẫu sự cố này.',
                          'phrase': 'Mô tả của bạn có cụm từ liên quan đến phép kiểm tra này.',
                          'search': 'Danh mục có nội dung gần với mô tả của bạn.',
                      }[source], 'source': source}

    matches = []
    for group in load_taxonomy(set(rows)):
        length = max((len(p.split()) for p in group['user_says'] if _phrase(text, p)), default=0)
        if length:
            matches.append((length, group))
    for _, group in sorted(matches, key=lambda match: -match[0]):
        response['symptom_groups'].append({key: group[key] for key in ('id', 'label_vi', 'gap_vi') if key in group})
        for card in group['cards']:
            add(card['skill_id'], f"symptom:{group['id']}", plain_vi=card['plain_vi'], why_vi=card['why_vi'])

    for phrase, sid in incident_phrases.items():
        if _phrase(text, phrase):
            add(sid, 'incident')
    incident_routing = profile.incidents.diagnostics['routing']
    for sid, phrases in incident_routing.items():
        if any(_phrase(text, phrase) for phrase in (*phrases, normalize(rows[sid]['name']), sid.lower())):
            add(sid, 'incident')
    for sid, row in eligible.items():
        if _phrase(text, sid.lower()) or _phrase(text, normalize(row['name'])):
            add(sid, 'phrase')
    phrase_routes = sorted(routing['phrases'].items(), key=lambda item: -max(
        (len(p.split()) for p in item[1] if _phrase(text, p)), default=0))
    for sid, phrases in phrase_routes:
        if any(_phrase(text, p) for p in phrases):
            add(sid, 'phrase')
    if len(cards) < MAX_CARDS:
        method, candidates = _replay_candidates(request, routing['phrases'])
        for sid in candidates:
            add(sid, 'phrase' if method == 'phrase' else 'search')
    if len(cards) < MAX_CARDS:
        retriever = _retriever()
        for hit in retriever.search(request, limit=len(retriever.catalog.skills), include_proposed=True):
            add(hit.skill_id, 'search')
            if len(cards) == MAX_CARDS:
                break

    ordered = list(cards)
    remaining = min(started + chat.max_elapsed_s - chat.clock(), replay.expires_at - replay.clock())
    if allow_model and len(cards) > 1 and remaining > 1 and _MODEL_SLOT.acquire(blocking=False):
        try:
            model = (chat.model_factory(timeout=remaining - 1) if chat.model_factory is local_model
                     else chat.model_factory())
            if getattr(model, 'local_only', None) is not True:
                raise ValueError('local_skill_model_required')
            shortlisted = {sid: eligible[sid] for sid in cards}
            docs = [[r['skill_id'], r['name'], r['availability'], r['runtime_scope']]
                    for r in shortlisted.values()]
            proposal = model.choose_skills(request, docs, {
                'scope': 'Prioritize the most helpful suggested READ Skills for a fixed synthetic scenario.',
                'simulation_only': True, 'inference_timeout_s': remaining - 1, 'last_round': False,
            })
            choice = validate_choice(proposal, shortlisted, {}, ())
            if choice['decision'] == 'measure' and not replay.closed and (
                    chat.clock() < started + chat.max_elapsed_s and replay.clock() < replay.expires_at):
                ordered = list(dict.fromkeys(choice['skill_ids'] + ordered))
        except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
            pass  # Optional advice failed; preserve the deterministic cards.
        finally:
            _MODEL_SLOT.release()
    response['cards'] = [cards[sid] for sid in ordered]
    return response


def aggregate(session_id: str, replay: ReplaySession, rows: dict[str, dict],
              runs: list[tuple[str, dict | None]], catalog_total: int, *, elapsed_s: float) -> dict:
    profile = replay.profile
    claim_text = {**profile.incidents.diagnostics['claim_text'], **profile.incident_replay.claim_text}
    evidence, plans, timeline, skill_runs, per_skill = {}, [], [], [], []
    source_errors, claim_details = {}, []
    faults, healthy, unknown, guidance = [], [], [], []
    now = replay.clock()
    for sid, result in runs:
        run = result or {}
        age = now - run.get('evidence_checked_at_monotonic', float('inf'))
        fresh = {r['id']: {**r, 'expires_in_s': r['expires_in_s'] - age}
                 for r in run.get('evidence', []) if r['status'] == 'OK' and 0 <= age < r['expires_in_s']
                 and now < replay.expires_at}
        evidence.update(fresh)
        status = run.get('status', 'UNAVAILABLE')
        errors = dict(run.get('source_errors', {}))
        if len(fresh) < len(run.get('evidence', [])):
            status = 'PARTIAL' if any(r['port'] != 'client.identity' for r in fresh.values()) else 'UNAVAILABLE'
            errors['evidence'] = 'EXPIRED'
        if result is None:
            errors['session'] = 'session_expired'
        if errors:
            source_errors[sid] = errors

        assessment = run.get('assessment', {})
        claims = [(claim_text.get(cid) or f'Điều kiện mô phỏng: {cid}', claim)
                  for cid, claim in assessment.get('claims', {}).items()
                  if claim['value'] == 'TRUE' and claim['evidence'] and set(claim['evidence']) <= fresh.keys()]
        name = rows[sid]['name']
        verdict = run.get('verdict', 'UNKNOWN')
        verdict_claims = [message for message, claim in claims if claim['severity'] == verdict]
        if not verdict_claims:
            verdict = 'UNKNOWN'
        if verdict == 'FAULT':
            faults.append(f"Phát hiện: {name} — {' '.join(dict.fromkeys(verdict_claims))}")
            if run.get('incident_guidance'):
                proof = [eid for _, claim in claims if claim['severity'] == 'FAULT' for eid in claim['evidence']]
                if item := profile.incident_replay.recommendation(replay.scenario, proof, list(fresh.values())):
                    guidance.append(item)
        elif verdict == 'HEALTHY':
            healthy.append(name)
        else:
            unknown.append(name)
        per_skill.append({'skill_id': sid, 'name': name, 'verdict': verdict, 'status': status,
                          'claims': list(dict.fromkeys(message for message, _ in claims)),
                          'evidence_ids': list(dict.fromkeys(eid for _, claim in claims for eid in claim['evidence']))})

        skill_runs.append({'skill_id': sid, 'status': status, 'calls_this_run': run.get('calls_this_run', 0),
                           'reused_ports': run.get('reused_ports', []), 'missing_ports': run.get('missing_ports', [])})
        plans.extend(run.get('plans', []))
        for event in run.get('timeline', []):
            if event['evidence_id'] is not None and event['evidence_id'] not in fresh:
                event = {**event, 'status': 'NO_LONGER_VALID', 'evidence_id': None, 'value': None}
            timeline.append({**event, 'index': len(timeline) + 1})
        if limitation := assessment.get('limitation'):
            claim_details.append(limitation)

    verdict = 'FAULT' if faults else 'UNKNOWN' if unknown else 'HEALTHY'
    answer = [NOTICE, *faults]
    if healthy:
        answer.append(f"Bình thường: {', '.join(healthy)}.")
    if unknown:
        answer.append(f"Chưa đủ bằng chứng: {', '.join(unknown)}.")
    statuses = {row['status'] for row in per_skill}
    status = statuses.pop() if len(statuses) == 1 else 'PARTIAL'
    measurements = [row for row in evidence.values() if row['port'] != 'client.identity']
    scopes = {rows[sid]['runtime_scope'] for sid, _ in runs}
    scope = next(iter(scopes)) if len(scopes) == 1 else None
    target = {'scope': scope, 'selector': {'gateway': 'Gateway mô phỏng', 'client': 'Client mô phỏng'}.get(
        scope, 'Gateway và client mô phỏng')}
    result = {'answer': '\n'.join(answer), 'session_id': session_id, 'mode': MODE,
              'synthetic_only': True, 'scenario': replay.scenario,
              'fixture': f'Replay mô phỏng · {replay.scenario}', 'fixture_id': replay.scenario,
              'catalog_total': catalog_total, 'workflow': 'REPLAY-SIM-SKILL-CHAT',
              'action': 'REPORT', 'case_status': status,
              'stop_reason': 'simulation_assessed' if status == 'MEASURED' else 'simulation_data_missing',
              'policy': 'core', 'method': 'core', 'diagnosis': None, 'verdict': verdict,
              'assessment': {'verdict': verdict}, 'evidence': list(evidence.values()),
              'evidence_ids': list(dict.fromkeys(eid for row in per_skill for eid in row['evidence_ids'])),
              'status_ok_evidence_ids': list(evidence), 'calls': sum(row['calls_this_run'] for row in skill_runs),
              'calls_total': replay.calls, 'repairs': 0, 'timeline': timeline, 'plans': plans,
              'skill_runs': skill_runs, 'triage_results': per_skill, 'source_errors': source_errors,
              'measurement_details': [f"{r['sample']} · {r['port']} · {r['value']}" for r in measurements],
              'claim_details': list(dict.fromkeys(claim_details)), 'notice': NOTICE, 'target': target,
              'model_calls': 0, 'advice': [], 'llm_advisor_used': False,
              'routing': {'method': 'triage', 'plan': [row['skill_id'] for row in per_skill]},
              'answer_kind': 'evidence' if measurements else None,
              'timings_ms': {'total': round(elapsed_s * 1000, 3)}, 'user_input_required': False}
    if guidance:
        result['incident_guidance'] = {'label': ADVISORY, **{
            key: list(dict.fromkeys(value for item in guidance for value in item[key]))
            for key in ('steps', 'sources')}}
    return result
