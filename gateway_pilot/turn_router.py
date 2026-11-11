"""GATEWAY_DESIGN: deterministic Turn Router over the v0.1 joint catalog.

Scores express lexical affinity, never authority. Plans and advisor choices
are gated separately; only verified, fresh CaseState facts guide rerouting.
This module neither executes adapters nor stores conversational sessions.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache

from .core import ROOT, read_json, terms
from .graph_v3.contracts import Truth
from .graph_v3.state import CaseState
from .graph_v3.graphs import rerank_score
from .rag import (DEFAULT_CATALOG, REPLAY_FIRMWARE, REPLAY_PRODUCT, RunbookIndex,
                  lexical_scores)
from .workflow import CHANGE_REQUEST, WORKFLOWS, match_device, normalize, route


THRESHOLDS_PATH = ROOT / 'data/router_thresholds_v01.json'
CUES_PATH = ROOT / 'data/router_cues_v01.json'
CUE_GROUPS = ('question', 'symptom', 'state', 'network', 'capability', 'smalltalk', 'follow_up')


@lru_cache(maxsize=8)
def load_cues(path=CUES_PATH):
    """Compile literal, normalized bilingual phrases; malformed data fails early."""
    data = read_json(path)
    if (not isinstance(data, dict) or not set(CUE_GROUPS) <= set(data)
            or set(data) - {*CUE_GROUPS, 'subject_stopwords'}):
        raise ValueError('invalid_router_cues: expected groups ' + ', '.join(CUE_GROUPS))
    patterns = {}
    for group in (*CUE_GROUPS, 'subject_stopwords'):
        if group == 'subject_stopwords' and group not in data:
            patterns[group] = frozenset()
            continue
        phrases = data[group]
        if (not isinstance(phrases, list) or not phrases or any(
                not isinstance(p, str) or not p or normalize(p) != p for p in phrases)):
            raise ValueError('invalid_router_cues:' + group + ': expected normalized nonempty phrases')
        patterns[group] = (frozenset(phrases) if group == 'subject_stopwords' else
                           re.compile(r'\b(?:' + '|'.join(re.escape(p) for p in phrases) + r')\b'))
    # Question/state/symptom words describe the request, not an explicit
    # technical subject, even when sparse catalog text gives them high IDF.
    patterns['subject_stopwords'] |= frozenset(
        token for group in CUE_GROUPS if group != 'network'
        for phrase in data[group] for token in terms(phrase))
    return patterns


def _thresholds(overrides):
    values = read_json(THRESHOLDS_PATH)
    if overrides:
        values.update(overrides)
    for key in ('tau_low', 'tau_high', 'min_margin', 'rule_min_margin', 'multi_min_score',
                'unsupported_min_score', 'explicit_catalog_min_score'):
        v = values[key]
        if type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1:
            raise ValueError('invalid_router_threshold:' + key)
    if (values['tau_low'] > values['tau_high'] or type(values['candidate_count']) is not int
            or not 2 <= values['candidate_count'] <= 3):
        raise ValueError('invalid_router_thresholds')
    idf = values['explicit_subject_min_idf']
    if type(idf) not in (int, float) or not math.isfinite(idf) or idf < 0:
        raise ValueError('invalid_router_threshold:explicit_subject_min_idf')
    return values


def _blocked_goals(workflow, registry, state):
    """A goal is blocked only when EVERY eligible producer has a FALSE predicate."""
    if state is None:
        return 0
    allowed = registry.eligible(state)
    blocked = 0
    for goal in workflow['goal_ports']:
        if state.fact(goal) is not None:
            continue
        producers = [registry.functions[fid] for fid in registry.hf.producers(registry.ports[goal])
                     if fid in allowed]
        blocked += bool(producers) and all(any(p.evaluate(state) == Truth.FALSE for p in f.predicates)
                                          for f in producers)
    return blocked


def _explicit_subject(text, ranked, registry, limits, view, stopwords):
    """Rare subject tokens must identify one catalog design-skill group.

    Use BM25's existing document frequencies, excluding symptom descriptions
    from the subject fields. Skill IDs group related catalog entries; they
    never seed executable Functions or confer authority.
    """
    _, _, _, _, fields, docs = registry._static_retrieval_graph()
    design = {s['skill_id']: s['title'] for s in registry.workflow_catalog['skills']}
    subjects = {}
    for wid, workflow in registry.workflows.items():
        row = fields['w:' + wid]
        subjects[wid] = set(terms(normalize(' '.join([
            row['name'], *row['tags'], *(design[s] for s in workflow['skill_ids'])]))))
    matches = {}
    for token in set(terms(text)):
        if token in stopwords:
            continue
        df = sum(token in d for d in docs.values())
        if not df or math.log(1 + (len(docs) - df + .5) / (df + .5)) < limits['explicit_subject_min_idf']:
            continue
        owners = [wid for wid, tokens in subjects.items() if token in tokens]
        if not owners or any(registry.workflows[wid]['status'] != 'CATALOG_ONLY' or
                             registry.workflows[wid].get('covered_by') for wid in owners):
            continue
        groups = {tuple(sorted(registry.workflows[wid]['skill_ids'])) for wid in owners}
        if len(groups) == 1:
            for wid in owners:
                matches.setdefault(wid, []).append(token)
    if not matches:
        return ranked, None
    focused = _rank(registry.retrieve(' '.join(sorted({t for ts in matches.values() for t in ts})), (), view,
                                     workflow_top_n=len(registry.workflows)), registry)
    subject = next((c for c in focused if c['id'] in matches), None)
    if subject is None:
        return ranked, None
    return [subject, *(c for c in ranked if c['id'] != subject['id'])], matches[subject['id']]


def _options(ranked, registry):
    candidates = sorted((c for c in ranked if c['status'] == 'SUPPORTED' and c['score'] > 0),
                        key=lambda c: (-c['score'], c['id']))[:3]
    if not candidates:
        candidates = [dict(id=wid, title=w['title'], html_workflow_id=w.get('html_workflow_id'))
                      for wid, w in registry.workflows.items() if w['status'] == 'SUPPORTED']
    return [dict(id=c['id'], title=c['title'], html_workflow_id=c.get('html_workflow_id')) for c in candidates]


def _coverage(workflow, registry, state):
    goals = workflow['goal_ports']
    allowed = registry.eligible(state) if state is not None else {
        fid for fid, f in registry.functions.items() if registry.contract_allowed(f) and f.risk != 'WRITE'}
    if state is not None:
        allowed = {fid for fid in allowed if all(p.evaluate(state) != Truth.FALSE
                                                for p in registry.functions[fid].predicates)}
    return sum(any(fid in allowed for fid in registry.hf.producers(registry.ports[g]))
               for g in goals) / len(goals) if goals else 0.0


def _rank(retrieval, registry):
    """Fold ALL returned workflow scores before truncation, without gate bonuses."""
    merged, sources = {}, {}
    for hit in retrieval['workflows']:
        wid = hit['workflow_id']
        row = registry.workflows[wid]
        dest = row.get('covered_by', wid)
        merged[dest] = merged.get(dest, 0.0) + hit['rerank_score']
        sources.setdefault(dest, []).append(wid)
    return [dict(id=wid, title=registry.workflows[wid]['title'],
                 html_workflow_id=registry.workflows[wid].get('html_workflow_id'),
                 status=registry.workflows[wid]['status'], raw_score=score,
                 score=score / (1 + score), matched_workflows=sources[wid])
            for wid, score in sorted(merged.items(), key=lambda x: (-x[1], x[0]))]


def _docs(message):
    try:
        docs = RunbookIndex(DEFAULT_CATALOG).retrieve(
            message, product=REPLAY_PRODUCT, firmware=REPLAY_FIRMWARE, permissions={'docs.read'})['documents']
    except FileNotFoundError:
        docs = []
    scores = lexical_scores(message, {d['id']: d['title'] + ' ' + d['text'] for d in docs})
    return docs, max(scores.values(), default=0.0)


def _lookup_function(text, retrieval, registry, state):
    """Match state questions to typed output fields, with PPR as a tie break.

    These are bilingual state-cue expansions, not workflow/function IDs.
    No registry symptom text or function contract is changed for calibration.
    """
    query = text
    for pattern, words in ((r'\b(?:len|up)\b', 'link up status'),
                           (r'\b(?:con bao nhieu|how much)\b', 'free available'),
                           (r'\b(?:dang dung|using)\b', 'configured resolver')):
        if re.search(pattern, text):
            query += ' ' + words
    # Completed outputs can be answered from fresh CaseState facts. They are
    # absent from retrieve()['functions'] because they need no new execution.
    candidates = list(dict.fromkeys([*retrieval['functions'], *sorted(registry.eligible(state))]))
    # An output's state cue is not a match for a different subject (e.g. an
    # ONT question cannot authorize a WAN measurement merely because of "up").
    candidates = [fid for fid in candidates if rerank_score(
        text, name=' '.join(registry.functions[fid].outputs),
        description=registry.functions[fid].description) > 0]
    if not candidates:
        return None
    def affinity(fid):
        f = registry.functions[fid]
        fields = [key for port in f.outputs.values() for key in port.schema.get('properties', {})]
        return rerank_score(query, name=' '.join(f.outputs), description=f.description, ports=fields)
    return max(candidates, key=lambda fid: (affinity(fid), -candidates.index(fid)))


def route_turn(message, *, registry, state=None, session=None, inventory=(), advisor=None, thresholds=None):
    """Classify a turn and propose a bounded read-only goal set, without execution."""
    text = normalize(message)
    limits = _thresholds(thresholds)
    cues = load_cues()
    result = dict(turn_type='OUT_OF_SCOPE', confidence=0.0, band='LOW', workflow_candidates=[],
                  skills=[], functions=[], target={'scope': 'gateway', 'selector': None, 'resolved': True},
                  route=None, features=dict(top_score=0.0, margin=0.0, coverage=0.0, rule_hit=False,
                                            doc_score=0.0, question_cue=False, symptom_cue=False, state_cue=False),
                  source='rules', reason='', action='ANSWER',
                  plan_hint=None, options=[], documents=[], nearby_unsupported=[])

    def decision(kind, reason, action='ANSWER'):
        result.update(turn_type=kind, reason=reason, action=action)
        if kind in {'CHANGE', 'SMALLTALK', 'FOLLOW_UP'}:
            result.update(confidence=1.0, band='HIGH')
        return result

    # Certain rules precede every retrieval or optional advisor invocation.
    if re.search(CHANGE_REQUEST, text):
        return decision('CHANGE', 'change_request_read_only_mvp', 'REFUSE')
    if cues['smalltalk'].fullmatch(text):
        return decision('SMALLTALK', 'greeting_or_thanks')
    pending = session.get('pending_question') if isinstance(session, dict) else getattr(session, 'pending_question', None)
    waiting = session.get('status') if isinstance(session, dict) else getattr(session, 'status', None)
    device = match_device(text, inventory)
    exact_target = device and any(text == normalize(alias) for alias in
                                  (device['selector'], *device.get('aliases', ())))
    if pending or waiting == 'WAITING_INPUT' or exact_target or cues['follow_up'].fullmatch(text):
        return decision('FOLLOW_UP', 'pending_question_or_target_reply', 'ASK_USER')
    # "còn <device> thì sao" while the session holds a Case: the device name plus a
    # follow-up phrase, with nothing else, continues that Case for the new device.
    previous = session.get('request') if isinstance(session, dict) else getattr(session, 'request', None)
    if device and previous:
        rest = f' {text} '
        for alias in (device['selector'], *device.get('aliases', ())):
            rest = rest.replace(f' {normalize(alias)} ', ' ')
        rest = ' '.join(rest.split())
        if not rest or cues['follow_up'].fullmatch(rest):
            return decision('FOLLOW_UP', 'session_target_switch', 'ASK_USER')

    view = state if state is not None else CaseState({'target': {}, 'capabilities': list(registry.functions)}, registry)
    retrieval = registry.retrieve(message, (), view, workflow_top_n=len(registry.workflows),
                                  top_n=len(registry.functions))
    ranked = _rank(retrieval, registry)
    ranked, subject_tokens = _explicit_subject(text, ranked, registry, limits, view, cues['subject_stopwords'])
    for candidate in ranked:
        candidate['blocked'] = _blocked_goals(registry.workflows[candidate['id']], registry, state)
    if state is not None:
        ranked.sort(key=lambda c: bool(c['blocked']))  # stable: lexical order within each group
    docs, doc_score = _docs(message)
    result.update(workflow_candidates=ranked[:limits['candidate_count']], documents=docs,
                  source='retrieval', functions=list(retrieval['functions']))
    top = ranked[0] if ranked else None
    score = top['score'] if top else 0.0
    margin = score - (ranked[1]['score'] if len(ranked) > 1 else 0.0)
    workflow = registry.workflows[top['id']] if top else None
    features = dict(top_score=score, margin=margin,
                    retrieval_score=max((c['score'] for c in ranked), default=0.0),
                    coverage=_coverage(workflow, registry, state) if workflow else 0.0,
                    rule_hit=bool(top and route(text) == top['id']), doc_score=doc_score,
                    question_cue=bool(cues['question'].search(text)), symptom_cue=bool(cues['symptom'].search(text)),
                    state_cue=bool(cues['state'].search(text)), network_cue=bool(cues['network'].search(text)),
                    query_focus=subject_tokens)
    band = ('HIGH' if score >= limits['tau_high'] and
            (margin >= limits['min_margin'] or features['rule_hit'] and margin >= limits['rule_min_margin'])
            else 'MID' if score >= limits['tau_low'] else 'LOW')
    result.update(features=features, confidence=score, band=band)

    # Rule table, in priority order. Knowledge such as "cách đổi ..." is not
    # an imperative change; ambiguous symptoms retain a diagnostic turn type.
    if cues['capability'].search(text):
        return decision('CAPABILITY', 'catalog_capability_question')
    if not features['network_cue'] and features['retrieval_score'] < limits['tau_low']:
        return decision('OUT_OF_SCOPE', 'outside_network_and_device_domain')
    if features['question_cue']:
        return decision('KNOWLEDGE', 'knowledge_question_cue')
    kind = 'LOOKUP' if features['state_cue'] and not features['symptom_cue'] else 'DIAGNOSE'
    result.update(turn_type=kind, reason='state_question' if kind == 'LOOKUP' else 'workflow_affinity')
    if top is None:
        result['options'] = _options(ranked, registry)
        return decision(kind, 'no_catalog_candidates', 'ASK_USER')

    workflow = registry.workflows[top['id']]
    unsupported_threshold = limits['explicit_catalog_min_score'] if subject_tokens else limits['unsupported_min_score']
    supported = [c for c in ranked[:3] if c['status'] == 'SUPPORTED']
    catalog_first = top['status'] == 'CATALOG_ONLY'
    catalog_over_threshold = catalog_first and top['score'] >= unsupported_threshold
    if catalog_over_threshold and (subject_tokens or not any(c['score'] >= limits['tau_low'] for c in supported)):
        design = next((w for w in registry.workflow_catalog['workflows'] if w['workflow_id'] == top['id']), workflow)
        result['missing_skills'] = [s for s in design['skill_ids'] if s not in registry.skills]
        result['required_skills'] = list(design['skill_ids'])
        result['skills'] = list(workflow['skill_ids'])
        return decision(kind, 'uncovered_catalog_workflow', 'UNSUPPORTED')

    # Calibrate against the supported candidate that can actually be used.
    lookup_fid = _lookup_function(text, retrieval, registry, view) if kind == 'LOOKUP' else None
    if kind == 'LOOKUP' and lookup_fid is None:
        return decision(kind, 'no_eligible_lookup_function', 'UNSUPPORTED')
    if lookup_fid is not None:
        supported = [c for c in ranked if c['status'] == 'SUPPORTED' and any(
            g in registry.workflows[c['id']]['goal_ports'] for g in registry.functions[lookup_fid].outputs)][:1]
    result['nearby_unsupported'] = [c for c in ranked[:3] if c['status'] == 'CATALOG_ONLY']
    if catalog_first and kind != 'LOOKUP':
        supported = [c for c in supported if c['score'] >= limits['tau_low']]
    if not supported:
        result.update(band='LOW', confidence=0.0, options=_options(ranked, registry))
        result['features'].update(top_score=0.0, margin=0.0, coverage=0.0, rule_hit=False)
        return decision(kind, 'no_supported_candidate_above_threshold', 'ASK_USER')
    top = supported[0]
    score = top['score']
    margin = score - max((c['score'] for c in ranked if c['id'] != top['id']
                          and bool(c['blocked']) == bool(top['blocked'])), default=0.0)
    features.update(top_score=score, margin=margin,
                    coverage=_coverage(registry.workflows[top['id']], registry, state),
                    rule_hit=route(text) == top['id'])
    band = ('HIGH' if score >= limits['tau_high'] and
            (margin >= limits['min_margin'] or features['rule_hit'] and margin >= limits['rule_min_margin'])
            else 'MID' if score >= limits['tau_low'] else 'LOW')
    if catalog_first and band != 'LOW':
        band = 'MID'
    result.update(band=band, confidence=score)
    if any(c['blocked'] for c in ranked):
        result['reason'] = 'verified_preconditions_demote_blocked_goals'

    # Advisor sees only supported, completely gated workflows (including
    # target resolution), and can select an ID, never create goals or facts.
    choose = getattr(advisor, 'choose_workflow', None)
    if band in {'LOW', 'MID'} and callable(choose):
        choices = {c['id']: c['title'] for c in supported
                   if c['status'] == 'SUPPORTED' and _coverage(registry.workflows[c['id']], registry, state) == 1
                   and (not any(registry.ports[g].scope == 'client'
                                for g in registry.workflows[c['id']]['goal_ports']) or device is not None)}
        if choices:
            try:
                proposed = choose(message, choices)
            except (OSError, TimeoutError, ValueError, KeyError, TypeError):
                proposed = None
            if isinstance(proposed, str) and proposed in choices:
                top = next(c for c in ranked if c['id'] == proposed)
                ranked = [top, *(c for c in ranked if c['id'] != proposed)]
                result.update(workflow_candidates=ranked[:limits['candidate_count']], source='llm_advisor',
                              reason='advisor_selected_gated_candidate')

    workflow = registry.workflows[top['id']]
    result['skills'] = list(workflow['skill_ids'])
    selected = [top]
    if band == 'LOW' and result['source'] != 'llm_advisor' and lookup_fid is None:
        result['options'] = _options(ranked, registry)
        return decision(kind, 'low_affinity_choose_workflow', 'ASK_USER')

    # Conjunction alone is insufficient: each clause must independently
    # retrieve a different supported intent above the configured threshold.
    multi = []
    clauses = re.split(r'\b(?:va|voi|and)\b|,', text)
    if kind == 'DIAGNOSE' and len(clauses) > 1:
        for clause in clauses:
            if not cues['symptom'].search(clause):
                continue
            hits = _rank(registry.retrieve(clause, (), view, workflow_top_n=len(registry.workflows)), registry)
            hit = next((c for c in hits if c['status'] == 'SUPPORTED'), None)
            if hit and hit['score'] >= limits['multi_min_score'] and hit['id'] not in {c['id'] for c in multi}:
                multi.append(hit)
    if len(multi) >= 2:
        selected = multi
    elif kind == 'DIAGNOSE' and band == 'MID' and result['source'] != 'llm_advisor':
        selected = supported[:3]
    if not selected:
        result['options'] = _options(ranked, registry)
        return decision(kind, 'no_supported_candidate', 'ASK_USER')

    # LOOKUP chooses an eligible Function's output rather than the entire
    # diagnostic workflow. Retrieval is already gated before its top-k.
    if kind == 'LOOKUP':
        goals = list(registry.functions[lookup_fid].outputs)
        result['functions'] = [lookup_fid]
    else:
        # A generic catalog match can outrank the only executable workflow.
        # Measure that workflow's complete goal set instead of stopping after
        # its initial discriminator, since there is no second branch to choose.
        use_minimal = (band == 'MID' and len(multi) < 2 and result['source'] != 'llm_advisor'
                       and not (catalog_over_threshold and len(selected) == 1))
        goals = list(dict.fromkeys(g for c in selected for g in registry.workflows[c['id']][
            'minimal_goals' if use_minimal else 'goal_ports']))
    client_goals = [g for g in goals if registry.ports[g].scope == 'client']
    pending_client = bool(client_goals and device is None)
    scope = 'client' if client_goals and not pending_client else 'gateway'
    result['target'] = dict(scope=scope, selector=device['selector'] if device and scope == 'client' else None,
                            resolved=not pending_client, pending_client=pending_client)
    if pending_client:
        goals = [g for g in goals if registry.ports[g].scope == 'gateway']
        # Facts already measured in this Case remain usable without another
        # invocation. If only deferred client goals remain, ask for the target.
        if not goals or all(view.fact(g) is not None for g in goals):
            result['options'] = [d['selector'] for d in inventory]
            return decision(kind, 'client_target_not_unique', 'ASK_USER')
        result['target']['resolved'] = True
    if not goals or not any(view.fact(g) is not None or any(fid in registry.eligible(view)
                            for fid in registry.hf.producers(registry.ports[g])) for g in goals):
        result['options'] = _options(ranked, registry)
        return decision(kind, 'no_eligible_goal_producer', 'ASK_USER')
    # Keep client-only candidates as deferred context, never as executable
    # workflow/policy anchors for a gateway-only Case.
    if kind == 'LOOKUP':
        selected = [c for c in ranked if c['status'] == 'SUPPORTED'
                    and any(g in registry.workflows[c['id']]['goal_ports'] for g in goals)][:1]
    else:
        selected = [c for c in selected if any(g in registry.workflows[c['id']]['goal_ports'] for g in goals)]
    fast = (kind == 'DIAGNOSE' and band == 'HIGH' and len(selected) == 1
            and selected[0]['id'] in WORKFLOWS and not pending_client)
    result.update(route='fastpath' if fast else 'resolver', action='RUN',
                  skills=list(dict.fromkeys(s for c in selected for s in registry.workflows[c['id']]['skill_ids'])))
    result['plan_hint'] = dict(workflow=selected[0]['id'], goals=goals,
                              workflows=[c['id'] for c in selected],
                              reroute_after_evidence=kind == 'DIAGNOSE' and (band == 'MID' or pending_client) and len(multi) < 2
                              and result['source'] != 'llm_advisor')
    return result
