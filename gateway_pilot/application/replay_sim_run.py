"""Run an approved simulated Skill via scoped READ sessions and Claims."""
from __future__ import annotations

import math

from ..core import PlanError
from ..graph_v3.claims import ClaimBook
from ..observability.snapshot import VerifiedSnapshot
from ..skill_expansion.composite import VerifiedSource, assess_workflow
from ..skill_expansion.replay_sim import MODE, NOTICE, ReplaySession
from ..skill_expansion.runtime_bridge import SkillNotReady


def run_replay_skill(replay: ReplaySession, session_id: str, skill_id: str, *, deadline: float | None) -> dict:
    profile = replay.profile
    catalog = profile.igate if skill_id in profile.igate.actions else profile
    if skill_id not in catalog.actions:
        return {'session_id': session_id, 'mode': MODE, 'scenario': replay.scenario, 'synthetic_only': True,
                'skill_id': skill_id, 'status': 'UNAVAILABLE', 'verdict': 'UNKNOWN',
                'summary': f'{NOTICE} Skill này chưa được hỗ trợ trong Replay mô phỏng.',
                'calls_this_run': 0, 'calls_total': replay.calls, 'reused_ports': [], 'missing_ports': [],
                'evidence_ids': [], 'plans': [], 'timeline': []}
    if deadline is not None and (type(deadline) not in (int, float) or not math.isfinite(deadline)):
        raise ValueError('invalid_execution_deadline')
    limit = replay.expires_at if deadline is None else min(replay.expires_at, deadline)
    before = replay.calls
    sessions, plans, attempts, errors = {}, [], [], {}
    samples = catalog.samples[skill_id][replay.scenario]
    diagnostic = catalog.diagnostics['skills'][skill_id]

    for alias, sample in samples.items():
        time_left = limit - replay.clock()
        calls_left = replay.max_calls - replay.calls
        cost_left = replay.cost_budget - replay.spent
        if sample.values is None:
            errors[alias] = 'SIMULATED_SOURCE_MISSING'
            continue
        if time_left <= 0 or calls_left <= 0 or cost_left <= 0 or replay.plans >= replay.max_plans:
            errors[alias] = 'READ_BUDGET_EXHAUSTED'
            continue
        try:
            session, bridge, owner = profile.open_sample(sample, environment=replay.environment, clock=replay.clock,
                                                         max_calls=calls_left, ttl_s=time_left, cost_budget=cost_left)
        except PlanError as exc:
            errors[alias] = str(exc)
            continue
        sessions[alias] = session
        runner = session.runner
        # Session construction time also counts against the turn deadline.
        runner.deadline_s = min(runner.deadline_s, limit - runner.started)
        try:
            bridge.execute(owner, snapshot=session.refresh(), session=session)
        except (PlanError, SkillNotReady) as exc:
            errors[alias] = str(exc)
        finally:
            replay.calls += runner.calls
            replay.plans += len(runner.plans)
            replay.spent += runner.spent
            plans.extend(plan.export() for plan in runner.plans)
            for plan in runner.plans:
                for node_id in plan.topological():
                    node = plan.nodes[node_id]
                    if any(step['from'] == 'RUNNING' for step in node.history):
                        attempts.append((alias, node))

    sources = {}
    for alias, session in sessions.items():
        try:
            session.refresh()
        except PlanError as exc:
            errors[alias] = str(exc)
        else:
            sources[alias] = VerifiedSource(session.state, samples[alias].simulated_at)

    assessment = {'verdict': 'UNKNOWN', 'claims': {}}
    if diagnostic['kind'] == 'composite':
        assessment = assess_workflow(skill_id, sources, diagnostic)
    elif sources:
        state = next(iter(sources.values())).state
        book = ClaimBook(diagnostic['claims'], state.registry.ports, diagnostic['workflows'])
        claims = {}
        for workflow in diagnostic['workflows']:
            claims.update(book.evaluate_all(state, workflow))
        assessment['claims'] = claims

    # Export original proofs only. Aliases keep separate observations distinct,
    # even when several history samples came from the same Function/Port.
    snapshots = {}
    if replay.clock() < limit:
        for alias in sources:
            session = sessions[alias]
            try:
                session._validate()
                snapshots[alias] = VerifiedSnapshot.from_state(
                    session.state, session.runtime.registry.ports,
                    context_valid=session._context_valid, allow_replay=True).export()
            except PlanError as exc:
                errors[alias] = str(exc)
    evidence = [{'id': fact['evidence_id'], 'port': port, 'status': 'OK', 'sample': alias,
                 'simulated_at': samples[alias].simulated_at, **fact}
                for alias, snapshot in snapshots.items() for port, fact in snapshot['facts'].items()]
    missing = [alias for alias, sample in samples.items()
               if sample.function_id not in snapshots.get(alias, {}).get('facts', {})]
    proof_ids = {row['id'] for row in evidence}
    active = []
    for claim in assessment['claims'].values():
        if claim['value'] != 'TRUE':
            continue
        if missing or not claim['evidence'] or not set(claim['evidence']) <= proof_ids:
            claim.update(value='UNKNOWN', evidence=[])
        elif claim['severity'] in {'HEALTHY', 'FAULT'}:
            active.append(claim)
    severities = {claim['severity'] for claim in active}
    verdict = next(iter(severities)) if len(severities) == 1 else 'UNKNOWN'
    assessment['verdict'] = verdict
    if 'history' in assessment and (missing or any(row['evidence_id'] not in proof_ids for row in assessment['history'])):
        del assessment['history']
    by_id = {row['id']: row for row in evidence}
    timeline = []
    for index, (alias, node) in enumerate(attempts, 1):
        ids = list(node.output_evidence.values())
        fact = next((by_id[eid] for eid in ids if eid in by_id), None)
        verified = node.state == 'SUCCEEDED'
        timeline.append({'index': index, 'function_id': node.function_id, 'node_state': node.state,
                         'status': 'OK' if fact else 'NO_LONGER_VALID' if verified else 'UNVERIFIED',
                         'verified_at_execution': verified, 'historical_evidence_ids': ids,
                         'evidence_id': fact['id'] if fact else None, 'value': fact['value'] if fact else None,
                         'reason': node.reason, 'sample': alias})

    proof = list(dict.fromkeys(eid for claim in active for eid in claim['evidence'])) if verdict != 'UNKNOWN' else []
    status = 'MEASURED' if not missing else 'PARTIAL' if any(
        row['port'] != 'client.identity' for row in evidence) else 'UNAVAILABLE'
    return {'session_id': session_id, 'mode': MODE, 'scenario': replay.scenario, 'synthetic_only': True,
            'skill_id': skill_id, 'status': status, 'verdict': verdict, 'assessment': assessment,
            'summary': f"{NOTICE} {catalog.actions[skill_id]['name']} · {verdict}.",
            'calls_this_run': replay.calls - before, 'calls_total': replay.calls, 'reused_ports': [],
            'missing_ports': sorted({samples[alias].function_id for alias in missing}), 'missing_sources': missing,
            'source_errors': errors, 'evidence': evidence, 'evidence_ids': proof,
            'plans': plans, 'timeline': timeline}
