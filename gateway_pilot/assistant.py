"""GATEWAY_DESIGN: minimal C2 turn entry point; synthetic replay, read-only.

Templates deliberately remain small. General claim composition and persistent
conversation sessions belong to C3/C4, not to this routing layer.
"""
from __future__ import annotations

import argparse
import json
import sys

from .answer import SCOPE_TEXT, compose
from .core import ROOT, read_json
from .graph_v3.graphs import GraphRegistry
from .graph_v3.state import CaseState
from .session import Session
from .turn_router import route_turn
from .workflow import diagnose, match_device, normalize, replay_from_fixture


def answer(message, replay, *, registry=None, session=None, advisor=None, method='gos', llm=None):
    """One turn: route, execute only a gated plan, then compose a grounded Turn (C3).

    ``llm`` is an optional ``callable(payload) -> str`` that may only rephrase the
    selected claim, facts and documents; its text is checked before use.
    """
    return compose(_answer(message, replay, registry=registry, session=session, advisor=advisor,
                           method=method), message, llm=llm)


def _answer(message, replay, *, registry=None, session=None, advisor=None, method='gos'):
    """Route once, then execute only a gated DIAGNOSE/LOOKUP plan.

    ``session`` may be a :class:`Session` (C4): the turn then reuses the session's
    still-fresh evidence, a device reply continues the pending Case, and the Case
    is remembered afterwards. A plain dict keeps the C2 behaviour (routing only).
    """
    registry = registry or GraphRegistry.from_v01()
    live_session = session if isinstance(session, Session) else None
    if live_session is not None:
        replay = live_session.carry(replay)
    inventory = replay.get('devices', ())
    device = match_device(normalize(message), inventory)
    target = {'scope': 'gateway', 'id': 'gateway_01'}
    if device:
        target = {'scope': 'client', 'selector': device['selector']}
        if device.get('client_id'):
            target['client_id'] = device['client_id']
    case = dict(target=target, capabilities=replay['capabilities'],
                initial_evidence=replay.get('initial_evidence', ()))
    if 'permissions' in replay:
        case['permissions'] = replay['permissions']
    state = CaseState(case, registry)
    routed = route_turn(message, registry=registry, state=state, session=session,
                        inventory=inventory, advisor=advisor)
    kind, hint = routed['turn_type'], routed['plan_hint']
    result = dict(turn_type=kind, answer='', route=routed['route'], router=routed,
                  case_status=None, calls=0, route_history=[])
    if live_session is not None:
        result['session_id'] = live_session.session_id
        follow = live_session.request and (kind == 'FOLLOW_UP' or routed['action'] == 'ASK_USER'
                                           or routed['band'] == 'LOW')
        if follow and device is not None:
            # Continue the session's Case with the named device. diagnose() re-checks
            # permission and that the device is in the trusted inventory.
            measured = diagnose(live_session.request, replay, registry=registry, advisor=advisor, method=method,
                                workflow=live_session.workflow, device_selector=device['selector'],
                                return_state=True)
            live_session.remember(measured, request=live_session.request)
            measured.pop('case_state', None)
            result.update(measured, turn_type='FOLLOW_UP', router=routed, answer=measured['terminal']['response'],
                          calls=measured.get('graph', {}).get('calls', 0), session_id=live_session.session_id)
            return result
        if follow and live_session.pending_question:
            result.update(answer='Bạn muốn kiểm tra thiết bị nào? ' + '; '.join(d['selector'] for d in inventory),
                          case_status='NEEDS_INPUT')
            return result
    if kind in {'DIAGNOSE', 'LOOKUP'} and hint is not None:
        latest = routed
        history = [dict(workflow=hint['workflow'], goals=hint['goals'], band=routed['band'],
                        reason=routed['reason'], plan_revision=0, after_call=0)]

        def reroute(diag):
            nonlocal latest
            revised = route_turn(message, registry=registry, state=diag.state, inventory=inventory, advisor=advisor)
            latest = revised
            new_hint = revised['plan_hint']
            if revised['band'] == 'HIGH' and new_hint is not None:
                history.append(dict(workflow=new_hint['workflow'], goals=new_hint['goals'], band=revised['band'],
                                    reason=revised['reason'], after_call=diag.runner.calls,
                                    plan_revision=diag.contracts[-1]['plan_revision'] + 1))
                return new_hint
            return None

        measured = diagnose(message, replay, registry=registry, advisor=advisor, method=method,
                            workflow=hint['workflow'], turn_type=kind, route=routed['route'], plan_hint=hint,
                            reroute=reroute if hint.get('reroute_after_evidence') else None,
                            return_state=live_session is not None)
        if live_session is not None:
            live_session.remember(measured, request=message)
            measured.pop('case_state', None)
        result.update(measured, turn_type=kind, router=routed, route_history=history,
                      calls=measured.get('graph', {}).get('calls', 0), answer=measured['terminal']['response'])
        pending_client = (routed['target'].get('pending_client', False)
                          or latest['target'].get('pending_client', False))
        unresolved = measured['case_status'] != 'RESOLVED'
        if kind == 'LOOKUP' or len(hint['workflows']) > 1 or pending_client and unresolved:
            # Values below are exclusively verified runner evidence; no
            # generic "no fault" claim is inferred from a successful lookup.
            facts = measured.get('goal_facts', [])
            result['answer'] = '\n'.join(
                f"{e['port']}: {json.dumps(e['value'], ensure_ascii=False)} "
                f"({SCOPE_TEXT.get(e['scope'], '')}, phạm vi {e['scope']}, thời điểm {e.get('observed_at', 'chưa có')})."
                for e in facts
            ) or 'Chưa đủ dữ liệu trong phạm vi tra cứu.'
            # A lookup that measured every requested port is answered (RESOLVED); a
            # multi-goal or deferred-client turn with only some facts stays PARTIAL.
            complete = facts and len(facts) == len(hint['goals'])
            result['case_status'] = (('RESOLVED' if kind == 'LOOKUP' and complete else 'PARTIAL') if facts
                                     else measured['case_status'])
            result['facts_listed'] = True
        if pending_client and unresolved:
            result['answer'] += ('\nBạn muốn kiểm tra thiết bị nào? '
                                 + '; '.join(d['selector'] for d in inventory))
            result['case_status'] = 'NEEDS_INPUT'
            result['follow_up_router'] = latest
            if live_session is not None:
                # Gateway facts are already in the session; the reply continues this request.
                candidate = next((c['id'] for c in routed['workflow_candidates']
                                  if registry.workflows[c['id']]['target_scope'] == 'client'), hint['workflow'])
                live_session.workflow = candidate
                live_session.pending_question = {'kind': 'target', 'request': message, 'workflow': candidate}
        return result

    if routed['action'] == 'UNSUPPORTED':
        if routed['reason'] == 'no_eligible_lookup_function':
            result.update(answer='Nguồn dữ liệu hiện tại chưa cung cấp thông tin bạn muốn tra cứu.',
                          case_status='INCONCLUSIVE')
        else:
            skills = routed.get('missing_skills') or routed.get('required_skills', [])
            result['answer'] = ('Chưa hỗ trợ workflow này; thiếu contract hoặc nguồn dữ liệu đo cho: '
                                + ', '.join(skills) + '. ' + routed['workflow_candidates'][0]['title'])
    elif routed['action'] == 'ASK_USER' and kind != 'FOLLOW_UP':
        labels = [o['title'] if isinstance(o, dict) else o for o in routed['options']]
        result.update(answer='Bạn muốn kiểm tra mục hoặc thiết bị nào? ' + '; '.join(labels),
                      case_status='NEEDS_INPUT')
        if live_session is not None and routed['reason'] == 'client_target_not_unique':
            candidate = routed['workflow_candidates'][0]['id']
            live_session.request, live_session.workflow = message, candidate
            live_session.pending_question = {'kind': 'target', 'request': message, 'workflow': candidate}
    elif kind == 'CAPABILITY':
        supported = [w['title'] for w in registry.workflows.values() if w['status'] == 'SUPPORTED']
        result['answer'] = ('Tôi hỗ trợ kiểm tra chỉ đọc: ' + '; '.join(supported)
                            + '. Các workflow CATALOG_ONLY còn thiếu contract hoặc nguồn đo và chưa chạy được.')
    elif kind == 'KNOWLEDGE':
        result['answer'] = ('\n'.join(f"{d['text']} [{d['id']}]" for d in routed['documents'])
                            or 'Chưa có tài liệu phù hợp trong phạm vi tra cứu.')
    elif kind == 'CHANGE':
        result.update(answer='MVP chỉ đọc trạng thái; chưa hỗ trợ thay đổi cấu hình.', case_status='BLOCKED')
    elif kind == 'SMALLTALK':
        result['answer'] = 'Chào bạn! Tôi có thể giúp kiểm tra mạng và trạng thái thiết bị.'
    elif kind == 'FOLLOW_UP':
        result.update(answer='Đã nhận câu trả lời tiếp theo. Cần ngữ cảnh Case để tiếp tục kiểm tra.',
                      case_status='NEEDS_INPUT')
    else:
        result['answer'] = 'Câu hỏi nằm ngoài phạm vi mạng và thiết bị. Tôi hỗ trợ kiểm tra WAN, DNS, DHCP và router.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', required=True)
    parser.add_argument('--request', required=True)
    parser.add_argument('--trace', action='store_true')
    args = parser.parse_args()
    fixture = next((c for c in read_json(ROOT / 'data/cases.json') if c['id'] == args.fixture), None)
    if fixture is None:
        parser.error('Unknown replay fixture')
    registry = GraphRegistry.from_v01()
    result = answer(args.request, replay_from_fixture(fixture, registry), registry=registry)
    sys.stdout.reconfigure(encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.trace else result['answer'])


if __name__ == '__main__':
    main()
