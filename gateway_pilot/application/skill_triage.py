"""Suggest approved replay Skills and summarize their verified READ results."""
from __future__ import annotations

import re
from itertools import zip_longest
from pathlib import Path
from typing import TYPE_CHECKING

from ..adapters.bindings import require
from ..command_catalog.loader import read_json
from ..skill_expansion.catalog import DATA_DIR
from ..skill_expansion.incident_replay import ADVISORY, _source_url, _text, _texts
from ..skill_expansion.replay_sim import MODE, NOTICE, ReplaySession
from ..workflow import normalize
from .claim_guidance import (
    GENERIC_WARNING, build_next_steps, evidenced_claims,
    incident_recommendation, load_claim_guidance, missing_sources, next_steps_text,
)
from .replay_sim_run import current_replay_result
from .skill_chat import (
    _MODEL_SLOT, _phrase, _replay_candidates, _replay_refusal, _replay_scopes,
    _retriever, local_model, validate_choice,
)

if TYPE_CHECKING:
    from .skill_chat import SkillChat

MAX_CARDS = 6
OWN_HOME_PHRASES = frozenset({'router nha toi', 'router cua toi', 'wifi nha toi'})
TAXONOMY = DATA_DIR / 'symptom_taxonomy_v1.json'
SIGNALS = DATA_DIR / 'symptom_signals_v1.json'
QUESTIONS = DATA_DIR / 'triage_questions_v1.json'
# Expand complete tokens only. In particular, leave net addresses and Skill IDs
# to the existing checks on the original request.
SPELLINGS = {
    'dt': 'dien thoai', 'ko': 'khong', 'k': 'khong', 'kh': 'khong', 'hong': 'khong',
    'dc': 'duoc', 'dk': 'duoc', 'bth': 'binh thuong', 'bt': 'binh thuong',
    'trc': 'truoc', 'r': 'roi', 'mn': 'moi nguoi', 'xai': 'dung', 'e': 'em',
    'igaet': 'igate', 'wiffi': 'wifi', 'wfi': 'wifi',
    'gigahec': 'gigahertz', 'gahec': 'gigahertz',
    'wiff': 'wifi', 'vifi': 'wifi', 'ruter': 'router', 'moderm': 'modem',
}
NETWORK_TERMS = re.compile(
    r'\b(?:wifi|wi fi|internet|router|gateway|modem|igate|ethernet|lan|wan|dns|dhcp|ipv[46]|'
    r'pppoe|ssid|rssi|snr|nat|vpn|mtu|dfs|upnp|ping|toc do mang|ket noi mang|diem phat|'
    r'mang cham|mang yeu|mat mang|duong truyen|ten mien|cap quang|tinh hieu wifi|'
    r'port forwarding|ket noi|truy cap|do tre|trinh duyet|bo phat|hop phat|'
    r'mang noi bo|chuyen tiep|toc do lien ket|diem goc|chia cong|tai len)\b'
)
WRITE_REQUEST = re.compile(
    r'(?:^|\b(?:hay|vui long|lam on|giup toi|nho ban) +)'
    r'(?:tat|bat|mo|luu|cai|cap|thu hoi|chuyen|chan|cho phep) +'
    r'(?:.{0,50} )?(?:wifi|diem phat|dai tan|che do|cau hinh|ten phat|quyen|cong|'
    r'modem|gateway|router|thiet bi|firmware|mat khau)\b'
)
CLAUSE_BREAK = re.compile(r'[.,;!?]+|\b(?:và|va|đồng thời|dong thoi|riêng|rieng|còn|con|nhưng|nhung|and|also)\b', re.I)


def normalize_triage(request: str) -> str:
    text = normalize(request)
    text = re.sub(r'\bwi fi\b', 'wifi', text)
    text = ' '.join(SPELLINGS.get(token, token) for token in text.split())
    return re.sub(r'\b(?:ghi|gi|gi ga) (?:ga )?(?:hec|gigahertz)\b', 'gigahertz', text)



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
        groups.append({**group, 'user_says': list(map(normalize_triage, phrases))})
    signals = read_json(SIGNALS)
    require(set(signals) == {'format', 'groups'} and signals['format'] == 'gateway-lm.symptom-signals/v1'
            and type(signals['groups']) is dict and signals['groups'].keys() <= group_ids,
            'skill_triage_signals_format')
    for group in groups:
        variants = signals['groups'].get(group['id'], [])
        require(type(variants) is list and all(_texts(cues) for cues in variants),
                'skill_triage_taxonomy_signals')
        cues = [tuple(map(normalize_triage, signal)) for signal in variants]
        require(all(all(signal) and len(set(signal)) == len(signal) for signal in cues)
                and len(set(cues)) == len(cues), 'skill_triage_taxonomy_signals')
        group['signals'] = cues
    return groups


def replay_rows(catalog: dict) -> dict[str, dict]:
    return {row['skill_id']: row for key in ('rows', 'incident_rows', 'igate_rows') for row in catalog[key]
            if row['availability'] == 'READY'}


def public_group(group: dict) -> dict:
    return {key: group[key] for key in ('id', 'label_vi', 'gap_vi') if key in group}


def group_scores(text: str, groups: list[dict]) -> dict[str, int]:
    words = f' {text} '
    scores = {}
    for group in groups:
        exact = max((len(phrase.split()) + 2 for phrase in group['user_says']
                     if f' {phrase} ' in words), default=0)
        cues = max((sum(len(term.split()) for term in signal) for signal in group['signals']
                    if all(f' {term} ' in words for term in signal)), default=0)
        if score := max(exact, cues):
            scores[group['id']] = score
    return scores


def clarification(request: str, matched: list[dict], scores: dict[str, int],
                  eligible_ids: set[str]) -> dict[str, dict]:
    if len(matched) < 2:
        return {}
    first, second = matched[:2]
    pair = {first['id'], second['id']}
    if scores[first['id']] - scores[second['id']] > 2:
        return {}
    skill_sets = [{card['skill_id'] for card in group['cards']} & eligible_ids for group in (first, second)]
    if not all(skill_sets) or set.intersection(*skill_sets):
        return {}
    clause_matches = [set(group_scores(normalize_triage(clause), [first, second]))
                      for clause in CLAUSE_BREAK.split(request) if clause.strip()]
    if all({group_id} in clause_matches for group_id in pair):
        return {}  # Two independently described symptoms can both be investigated.
    questions = read_json(QUESTIONS)
    require(set(questions) == {'format', 'questions'} and questions['format'] == 'gateway-lm.triage-questions/v1'
            and type(questions['questions']) is list, 'skill_triage_questions_format')
    offered = {}
    for item in questions['questions']:
        require(type(item) is dict and set(item) == {'id', 'question_vi', 'options'}
                and _text(item['id']) and _text(item['question_vi'])
                and type(item['options']) is list and len(item['options']) == 2
                and all(type(option) is dict and set(option) == {'label_vi', 'group_id'}
                        and all(map(_text, option.values())) for option in item['options']),
                'skill_triage_question_fields')
        if {option['group_id'] for option in item['options']} == pair:
            require(item['id'] not in offered, 'skill_triage_duplicate_question')
            offered[item['id']] = {'question_vi': item['question_vi'], 'options': item['options']}
    return offered


def validate_triage_choice(choice: object, group_ids: set[str], card_ids: set[str],
                           question_ids: set[str]) -> dict:
    allowed = {'group_ids': group_ids, 'card_ids': card_ids, 'question_ids': question_ids}
    if type(choice) is not dict or set(choice) != set(allowed):
        raise ValueError('invalid_triage_model_fields')
    for key, ids in allowed.items():
        selected = choice[key]
        limit = 1 if key == 'question_ids' else 3
        if (type(selected) is not list or len(selected) > limit
                or any(type(item) is not str or item not in ids for item in selected)
                or len(set(selected)) != len(selected)):
            raise ValueError('invalid_triage_model_ids')
    return choice


def model_choice(chat: SkillChat, request: str, started: float, replay: ReplaySession,
                 groups: list[dict], cards: dict[str, dict], questions: dict[str, dict],
                 eligible: dict[str, dict]) -> tuple[dict, str]:
    remaining = min(15, started + chat.max_elapsed_s - chat.clock(), replay.expires_at - replay.clock())
    if remaining <= 1 or not _MODEL_SLOT.acquire(blocking=False):
        return {}, 'fallback'
    deadline = chat.clock() + remaining
    try:
        model = (chat.model_factory(timeout=remaining - 1) if chat.model_factory is local_model
                 else chat.model_factory())
        if getattr(model, 'local_only', None) is not True:
            raise ValueError('local_skill_model_required')
        if hasattr(model, 'choose_triage'):
            available = {group['id'] for group in groups}
            choice = model.choose_triage(request, [public_group(group) for group in groups],
                                         list(cards.values()), questions,
                                         timeout=deadline - chat.clock())
            choice = validate_triage_choice(choice, available, set(cards), set(questions))
        else:
            shortlist = {sid: eligible[sid] for sid in cards}
            docs = [[sid, row['name'], row['availability'], row['runtime_scope']] for sid, row in shortlist.items()]
            proposal = model.choose_skills(request, docs, {
                'scope': 'Prioritize suggested READ Skills for a fixed synthetic scenario.',
                'simulation_only': True, 'inference_timeout_s': remaining - 1, 'last_round': False,
            })
            choice = {'card_ids': validate_choice(proposal, shortlist, {}, ())['skill_ids']}
        if not replay.closed and chat.clock() < deadline and replay.clock() < replay.expires_at:
            return choice, 'accepted'
    except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
        pass  # Optional advice failed; preserve the deterministic proposal.
    finally:
        _MODEL_SLOT.release()
    return {}, 'fallback'


def interleaved_cards(groups: list[dict], eligible: dict[str, dict],
                      preferred_ids: list[str] | tuple[str, ...] = ()) -> list[tuple[dict, dict]]:
    rank = {sid: index for index, sid in enumerate(preferred_ids)}
    decks = [sorted(((group, card) for card in group['cards'] if card['skill_id'] in eligible),
                    key=lambda item: rank.get(item[1]['skill_id'], len(rank))) for group in groups]
    ordered = {}
    represented = set()
    for layer in zip_longest(*decks):
        for item in layer:
            if item is None:
                continue
            group, card = item
            sid = card['skill_id']
            if sid in ordered:
                represented.add(group['id'])  # A shared card can serve both groups.
            elif group['id'] not in represented:
                represented.add(group['id'])
                ordered[sid] = item
    # The first pass ensures representation before any group takes a second slot.
    for layer in zip_longest(*decks):
        for item in layer:
            if item is not None:
                ordered.setdefault(item[1]['skill_id'], item)
    return list(ordered.values())


def propose(chat: SkillChat, request: str, session_id: str, entry: dict, started: float, *,
            allow_model: bool, selected_group: str | None = None) -> dict:
    replay = entry['session']
    profile = replay.profile
    rows = replay_rows(chat.launcher.catalog(MODE, entry=entry))
    routing = profile.diagnostics['routing']
    incident_phrases = profile.incident_replay.symptom_routes
    original = normalize(request)
    text = normalize_triage(request)
    response = {'session_id': session_id, 'mode': MODE, 'scenario': replay.scenario, 'synthetic_only': True,
                'cards': [], 'symptom_groups': [], 'notice': NOTICE}
    if warning := GENERIC_WARNING.get(replay.scenario):
        response['warning'] = warning
    # Role-play speaks as the owner of the simulated home; other real-device phrases stay refused.
    role_play = {**routing, 'nonlocal_scope_phrases': [
        p for p in routing['nonlocal_scope_phrases'] if p not in OWN_HOME_PHRASES]}
    refusal = _replay_refusal(request, original, rows, role_play, incident_phrases.get(original))
    if not refusal and WRITE_REQUEST.search(text):
        refusal = ('write_intent_requires_approval', 'BLOCKED', 'Phiên chỉ hỗ trợ thao tác đọc trong mô phỏng.')
    if refusal:
        reason, status, message = refusal
        return dict(response, stop_reason=reason, case_status=status, answer=f'{NOTICE}\n{message}')

    scopes = _replay_scopes(original)
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

    groups = load_taxonomy(set(rows))
    scores = group_scores(text, groups)
    matched = sorted((group for group in groups if group['id'] in scores),
                     key=lambda group: -scores[group['id']])
    if selected_group is not None:
        matched = [group for group in matched if group['id'] == selected_group]
        if not matched:
            raise ValueError('triage_group_not_offered')
    response['symptom_groups'] = list(map(public_group, matched))
    for group, card in interleaved_cards(matched, eligible):
        add(card['skill_id'], f"symptom:{group['id']}", plain_vi=card['plain_vi'], why_vi=card['why_vi'])
    if selected_group is not None:
        return dict(response, cards=list(cards.values()))

    if matched and all(not group['cards'] for group in matched):
        return dict(response, stop_reason='unsupported_topic', case_status='NEEDS_INPUT',
                    answer=f"{NOTICE}\n" + ' '.join(group['gap_vi'] for group in matched))
    for phrase, sid in incident_phrases.items():
        if _phrase(original, phrase) or _phrase(text, normalize_triage(phrase)):
            add(sid, 'incident')
    incident_routing = profile.incidents.diagnostics['routing']
    for sid, phrases in incident_routing.items():
        if any(_phrase(original, phrase) for phrase in (*phrases, normalize(rows[sid]['name']), sid.lower())):
            add(sid, 'incident')
    for sid, row in eligible.items():
        if _phrase(original, sid.lower()) or _phrase(original, normalize(row['name'])):
            add(sid, 'phrase')
    phrase_routes = sorted(routing['phrases'].items(), key=lambda item: -max(
        (len(p.split()) for p in item[1] if _phrase(original, p)), default=0))
    for sid, phrases in phrase_routes:
        if any(_phrase(original, p) for p in phrases):
            add(sid, 'phrase')
    if not (cards or matched or NETWORK_TERMS.search(text)):
        return dict(response, stop_reason='unsupported_topic', case_status='NEEDS_INPUT',
                    answer=f'{NOTICE}\nPhiên chỉ hỗ trợ kiểm tra mạng mô phỏng. Bạn có thể mô tả vấn đề Wi-Fi, thiết bị kết nối hoặc đường Internet.')
    if len(cards) < MAX_CARDS:
        method, candidates = _replay_candidates(text, routing['phrases'])
        for sid in candidates:
            add(sid, 'phrase' if method == 'phrase' else 'search')
    if len(cards) < MAX_CARDS:
        retriever = _retriever()
        for hit in retriever.search(text, limit=len(retriever.catalog.skills), include_proposed=True):
            add(hit.skill_id, 'search')
            if len(cards) == MAX_CARDS:
                break

    ordered = list(cards)
    questions = clarification(request, matched, scores, set(eligible))
    chosen_question = next(iter(questions), None)
    # Ask for help when the wording supplied weak cues or a curated ambiguity.
    if allow_model and cards and (questions or not matched or scores[matched[0]['id']] < 4):
        # Offer matched groups and a bounded shortlist grounded in the current cards.
        priority = {sid: rank for rank, sid in enumerate(ordered)}
        related = sorted((group for group in groups if group['id'] not in scores
                          and any(card['skill_id'] in cards for card in group['cards'])),
                         key=lambda group: min(priority.get(card['skill_id'], MAX_CARDS)
                                               for card in group['cards']))
        offered = matched + related[:max(0, 8 - len(matched))]
        choice, response['triage_model'] = model_choice(chat, request, started, replay, offered,
                                                        cards, questions, eligible)
        group_ids = choice.get('group_ids', [])
        preferred = choice.get('card_ids', [])
        selected = [group for group_id in group_ids for group in offered if group['id'] == group_id]
        ranked = selected + [group for group in matched if group['id'] not in group_ids]
        response['symptom_groups'] = list(map(public_group, ranked))
        if ranked and (group_ids or preferred):
            visible = {sid: eligible[sid] for sid in cards}
            grouped = [card['skill_id'] for _, card in interleaved_cards(ranked, visible, preferred)]
            ordered = list(dict.fromkeys(grouped + preferred + ordered))
        else:
            ordered = list(dict.fromkeys(preferred + ordered))
        if choice.get('question_ids'):
            chosen_question = choice['question_ids'][0]
    if chosen_question is not None:
        response['clarify'] = questions[chosen_question]
    response['cards'] = [cards[sid] for sid in ordered]
    return response


def aggregate(session_id: str, replay: ReplaySession, rows: dict[str, dict],
              runs: list[tuple[str, dict | None]], catalog_total: int, *, elapsed_s: float,
              offered_ids: list[str] | None = None) -> dict:
    claim_guidance = load_claim_guidance(replay.profile)
    messages = claim_guidance['text']
    evidence, plans, timeline, skill_runs, per_skill = {}, [], [], [], []
    source_errors, claim_details = {}, []
    faults, healthy, unknown, guidance = [], [], [], []
    fault_ids, missing, incident_from = [], [], ''
    now = replay.clock()
    for sid, result in runs:
        run = current_replay_result(replay, result or {}, now)
        fresh = {row['id']: row for row in run['evidence']}
        evidence.update(fresh)
        status = run.get('status', 'UNAVAILABLE')
        errors = dict(run.get('source_errors', {}))
        if run.get('assessment', {}).get('reason') == 'evidence_expired':
            errors['evidence'] = 'EXPIRED'
        if result is None:
            errors['session'] = 'session_expired'
        if errors:
            source_errors[sid] = errors

        assessment = run.get('assessment', {})
        claims = evidenced_claims(run, fresh)
        fault_ids.extend((sid, cid) for cid, claim in claims.items() if claim['severity'] == 'FAULT')
        name = rows[sid]['name']
        verdict = run.get('verdict', 'UNKNOWN')
        verdict_claims = [cid for cid, claim in claims.items() if claim['severity'] == verdict]
        if not verdict_claims:
            verdict = 'UNKNOWN'
        if verdict == 'FAULT':
            finding = ' '.join(dict.fromkeys(messages[cid] for cid in verdict_claims))
            faults.append(f'Phát hiện: {name} — {finding}')
            if item := incident_recommendation(replay, run, claims, fresh):
                guidance.append(item)
                incident_from = incident_from or f'{replay.scenario} · {sid}'
        elif verdict == 'HEALTHY':
            healthy.append(name)
        else:
            unknown.append(name)
            missing.extend(f'{sid} · {source}' for source in missing_sources(run))
            if result is None:
                missing.append(f'{sid} · phiên đã hết hạn')
        per_skill.append({'skill_id': sid, 'name': name, 'verdict': verdict, 'status': status,
                          'claims': list(dict.fromkeys(messages[cid] for cid in claims)),
                          'evidence_ids': list(dict.fromkeys(eid for claim in claims.values()
                                                            for eid in claim['evidence']))})

        skill_runs.append({'skill_id': sid, 'status': status, 'calls_this_run': run.get('calls_this_run', 0),
                           'reused_ports': run.get('reused_ports', []), 'missing_ports': run.get('missing_ports', [])})
        plans.extend(run.get('plans', []))
        for event in run.get('timeline', []):
            timeline.append({**event, 'index': len(timeline) + 1})
        if limitation := assessment.get('limitation'):
            claim_details.append(limitation)

    verdict = 'FAULT' if faults else 'UNKNOWN' if unknown else 'HEALTHY'
    answer = [NOTICE, *faults]
    if healthy:
        answer.append(f"Bình thường: {', '.join(healthy)}.")
    if unknown:
        answer.append(f"Chưa đủ bằng chứng: {', '.join(unknown)}.")
    incident_guidance = {'label': ADVISORY, **{
        key: list(dict.fromkeys(value for item in guidance for value in item[key]))
        for key in ('steps', 'sources')}} if guidance else None
    next_steps = build_next_steps(claim_guidance, verdict, faults=fault_ids, incident=incident_guidance,
                                  incident_from=incident_from, missing=missing)
    answer.append(next_steps_text(next_steps))
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
              'skill_runs': skill_runs, 'triage_results': per_skill, 'next_steps': next_steps,
              'source_errors': source_errors,
              'measurement_details': [f"{r['sample']} · {r['port']} · {r['value']}" for r in measurements],
              'claim_details': list(dict.fromkeys(claim_details)), 'notice': NOTICE, 'target': target,
              'model_calls': 0, 'advice': [], 'llm_advisor_used': False,
              'routing': {'method': 'triage', 'plan': [row['skill_id'] for row in per_skill]},
              'answer_kind': 'evidence' if measurements else None,
              'timings_ms': {'total': round(elapsed_s * 1000, 3)}, 'user_input_required': False}
    if incident_guidance:
        result['incident_guidance'] = incident_guidance
    if verdict == 'HEALTHY' and offered_ids:
        selected = {sid for sid, _ in runs}
        result['unrun_cards'] = [{'skill_id': sid, 'name': rows[sid]['name']}
                                 for sid in offered_ids if sid not in selected]
    if warning := GENERIC_WARNING.get(replay.scenario):
        result['warning'] = warning
    return result
