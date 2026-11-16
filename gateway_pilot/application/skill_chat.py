"""Connect local LLM catalog selection to existing Skill sessions and RCA assessment."""
from __future__ import annotations

import os
import re
import threading
from functools import lru_cache

from ..core import PlanError
from ..graph_v3.ollama_goal_model import OllamaGoalModel
from ..graph_v3.rca_agent import RCAAgent
from ..graph_v3.task_decomposer import TaskDecomposer
from ..observability.snapshot import VerifiedSnapshot
from ..workflow import normalize
from .skill_launcher import LAUNCHER, SkillSessionError


@lru_cache(maxsize=1)
def local_model():
    # Trusted startup environment only; HTTP/model text cannot set endpoint/model.
    return OllamaGoalModel(os.environ.get('GATEWAY_LM_CHAT_MODEL', 'qwen3:1.7b'), timeout=60)


def findings(view: dict) -> dict:
    """Render verified values with fixed semantics; model orders IDs, never invents numbers."""
    result = {}
    for port, fact in view['facts'].items():
        v = fact['value']
        if port == 'laptop.route':
            text = (f"Gateway: {v['gateway']}; interface định tuyến: {v['interface']}." if v['has_route']
                    else 'Laptop chưa có đường IPv4 tới IP kiểm tra.')
        elif port in {'laptop.gateway_probe', 'laptop.internet_probe'}:
            label = ('Gateway ' if port.endswith('gateway_probe') else 'IP Internet kiểm tra ') + v['destination']
            latency = f"{v['latency_ms']:g} ms" if v['latency_ms'] >= 0 else 'chưa có RTT'
            text = f"{label}: nhận {v['received']}/{v['sent']} gói ICMP, mất {v['loss_pct']:g}%, {latency}."
        elif port == 'laptop.dns':
            text = f"DNS {v['query']}: {'phân giải được' if v['resolved'] else 'chưa phân giải được'}; interface {v['interface']}."
        elif port == 'laptop.wifi':
            signal = f"{v['signal_pct']:g}%" if v['signal_pct'] >= 0 else 'chưa đọc được'
            text = f"Wi-Fi {v['interface']}: {'đã associated' if v['associated'] else 'chưa associated'}; signal {signal} (không phải RSSI dBm/SNR)."
        elif port == 'client.ipv4':
            text = f"IPv4 của Wi-Fi laptop: {v['address'] if v['configured'] else 'chưa được cấu hình'}."
        elif port == 'client.identity':
            text = 'Đã xác minh định danh của chính laptop đang chạy ứng dụng.'
        elif port == 'expansion.client_association':
            text = f"Laptop {'đang associated với AP ' + v['access_point_id'] if v['associated'] else 'chưa associated với AP'}."
        else:
            continue
        result[port] = {'id':port, 'text':text, 'evidence_ids':[fact['evidence_id']]}
    return result


def validate_choice(choice, rows, available_findings, attempted):
    if type(choice) is not dict or set(choice) != {'decision','skill_ids','finding_ids','unavailable_ids'}:
        raise ValueError('invalid_skill_proposal')
    if choice['decision'] not in {'measure','answer','clarify'}:
        raise ValueError('invalid_skill_decision')
    for key, limit, allowed in [('skill_ids',3,set(rows)), ('finding_ids',4,set(available_findings)),
                                 ('unavailable_ids',3,set(rows))]:
        values=choice[key]
        if (type(values) is not list or len(values)>limit or any(type(x) is not str or x not in allowed for x in values)
                or len(set(values))!=len(values)):
            raise ValueError('invalid_skill_proposal_ids')
    if any(rows[s]['availability'] not in {'READY','DEGRADED'} or s in attempted for s in choice['skill_ids']):
        raise ValueError('unsupported_or_repeated_skill')
    if any(rows[s]['availability'] != 'UNAVAILABLE' for s in choice['unavailable_ids']):
        raise ValueError('invalid_unavailable_skill')
    if (choice['decision']=='measure') != bool(choice['skill_ids']):
        raise ValueError('invalid_skill_decision_payload')
    return choice


class SkillChat:
    def __init__(self, launcher=LAUNCHER, *, model_factory=local_model, max_rounds=4):
        if type(max_rounds) is not int or not 1 <= max_rounds <= 6:
            raise ValueError('invalid_chat_round_budget')
        self.launcher, self.model_factory, self.max_rounds = launcher, model_factory, max_rounds

    def _view(self, entry, *, refresh=True):
        with entry['lock'], entry['session']._lock:
            try:
                if refresh:
                    entry['capabilities'] = entry['session'].refresh()
                else:
                    entry['session']._validate()
            except PlanError as exc:
                raise SkillSessionError('session_expired') from exc
            return VerifiedSnapshot.from_state(entry['session'].state, entry['runtime'].registry.ports,
                    context_valid=entry['context_valid']).export()

    def chat(self, request: str, *, session_id=None):
        if type(request) is not str or not 1 <= len(request.strip()) <= 2000:
            raise ValueError('invalid_chat_request')
        request=request.strip()
        created = session_id is None
        if created:
            session_id=self.launcher.create_session('live')['session_id']
        entry=self.launcher._get(session_id)
        if entry['mode'] != 'live':
            raise ValueError('chat_requires_live_session')
        with self.launcher._lock:
            lock=entry.setdefault('chat_lock',threading.Lock())
        # Serialise conversation turns without holding the manager/measurement lock during inference.
        with lock:
            try:
                return self._turn(request,session_id,entry)
            except Exception:
                if created:
                    try:self.launcher.close(session_id)
                    except SkillSessionError:pass
                raise

    def _turn(self, request, sid, entry):
        runtime, session = entry['runtime'], entry['session']
        calls_before=session.runner.calls
        plans_before=len(session.runner.plans)
        entry['capabilities']=runtime.probe()
        catalog=self.launcher.catalog('live',entry=entry)
        rows={r['skill_id']:r for r in catalog['rows']}
        docs=[[r['skill_id'],r['name'],r['availability'],r['runtime_scope']] for r in catalog['rows']]
        attempted, runs, advice, unavailable, selected = [], [], [], [], []
        normalized=normalize(request)
        unavailable=[skill for skill, phrases in runtime.registry.required_skill_phrases.items()
                     if rows[skill]['availability']=='UNAVAILABLE' and any(
                         re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',normalized) for phrase in phrases)]
        assessments=[]; reason='round_budget_exhausted'; ready=False
        if TaskDecomposer(runtime.registry).is_write_intent(request):
            reason='write_intent_requires_approval'
        # No custom targets: every action is pinned to this laptop. A named/addressed remote target needs another backend.
        elif re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b|(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',request):
            reason='custom_target_not_supported'
        else:
            try:
                model=self.model_factory()
                if getattr(model,'local_only',None) is not True or not callable(getattr(model,'choose_skills',None)):
                    raise ValueError('local_skill_model_required')
                ready=True
                agent=RCAAgent(runtime.registry,method='bm25')
                for round_index in range(self.max_rounds):
                    view=self._view(entry)
                    current=findings(view)
                    context={'required_unavailable':unavailable,'attempted':attempted,'findings':[{'id':f['id'],'text':f['text']} for f in current.values()],
                             'rca':[{'workflow':a['workflow'],'decision':a['decision'],
                                     'candidate_goals':a['candidate_goals'],
                                     'verified_claims':[r['diagnosis'] for r in a['claim_results'] if r['truth']=='TRUE']} for a in assessments],
                             'remaining_tool_calls':max(0,session.runner.max_calls-session.runner.calls),
                             'last_round':round_index==self.max_rounds-1,
                             'selected_measurements_complete':bool(runs) and all(r['status']=='MEASURED' for r in runs)
                                 and all(a['decision']!='INCONCLUSIVE' for a in assessments),
                             'previous_question':entry.get('previous_question',''),
                             'scope':'Only this local Linux laptop; never router/client inventory'}
                    raw=model.choose_skills(request,docs,context)
                    # Inference may outlast TTL or the session: validate again before admitting the decision.
                    fresh=self._view(entry)
                    choice=validate_choice(raw,rows,findings(fresh),attempted)
                    advice.append({'model':getattr(model,'model','local-test'), 'accepted':True,
                                   'selected':', '.join(choice['skill_ids']) or choice['decision'],
                                   'decision':choice['decision'],'finding_ids':choice['finding_ids'],
                                   'evidence_ids':[eid for f in current.values() for eid in f['evidence_ids']]})
                    unavailable=list(dict.fromkeys(unavailable+choice['unavailable_ids']))
                    if choice['decision']!='measure':
                        selected=choice['finding_ids']
                        reason='model_answer' if selected else 'needs_clarification'
                        break
                    if round_index==self.max_rounds-1:
                        reason='round_budget_exhausted';break
                    for skill in choice['skill_ids']:
                        result=self.launcher.run(sid,skill)
                        attempted.append(skill);runs.append(result)
                    # Workflows relevant to actually requested ports only; no global unrelated RCA conclusions.
                    workflows=list(dict.fromkeys(w for skill in attempted
                                                 for w in runtime.registry.skill_workflows[skill]))
                    assessments=agent.assess_session(session,workflows=workflows)
                    if session.runner.calls>=session.runner.max_calls:
                        reason='tool_budget_exhausted';break
            except SkillSessionError:
                raise
            except (OSError,TimeoutError):
                ready=False
                reason='model_unavailable'
            except (RuntimeError,ValueError,TypeError,PlanError):
                if session.closed:raise SkillSessionError('session_expired')
                reason='invalid_model_proposal' if ready else 'model_unavailable'
        with entry['lock']:
            # Refresh RCA after inference so no expired claim proof survives into the response.
            if assessments:
                assessments=RCAAgent(runtime.registry,method='bm25').assess_session(session,
                    workflows=[r['workflow'] for r in assessments])
            # Rebuild from current facts rather than exporting earlier model-visible copies.
            view=self._view(entry,refresh=not bool(assessments))
            current=findings(view)
            if set(selected)-set(current):
                reason='evidence_expired_during_answer'
            selected=[p for p in selected if p in current]
            # A bounded or failed model may still leave verified measurements; report those with an explicit stop reason.
            if not selected and runs:
                selected=list(dict.fromkeys(p for r in runs for p in r['snapshot']['facts'] if p in current))[:4]
            chosen={p:view['facts'][p] for p in selected}
            evidence_ids=[f['evidence_id'] for f in chosen.values()]
            answer='\n'.join(current[p]['text'] for p in selected)
            if unavailable:
                answer+='\n'+ '\n'.join(f"{rows[s]['name']}: chưa chạy được trên laptop ({rows[s]['reason']})." for s in unavailable)
            if reason=='write_intent_requires_approval':
                status='BLOCKED';answer='Ứng dụng chỉ đọc; không tự thay đổi cấu hình hoặc khởi động lại thiết bị.'
            elif reason=='custom_target_not_supported':
                status='NEEDS_INPUT';answer='Phiên này chỉ đo chính laptop đang chạy ứng dụng; chưa hỗ trợ target/IP/MAC tùy ý.'
            elif not chosen:
                status='UNAVAILABLE' if unavailable else 'NEEDS_INPUT'
                answer=answer.strip() or ('Chưa có evidence còn hiệu lực sau lúc suy luận; hãy đo lại.' if runs else
                                         'LLM local chưa sẵn sàng; chưa chạy phép đo. Hãy kiểm tra Ollama và thử lại.' if not ready else
                                         'Chưa đủ dữ liệu để trả lời. Hãy nêu vấn đề mạng trên chính laptop này; các Skill router chưa có backend live.')
            else:
                status='PARTIAL' if unavailable or reason!='model_answer' or any(r['missing_ports'] for r in runs) else 'MEASURED'
                wifi=view['facts'].get('laptop.wifi',{}).get('value',{})
                route=view['facts'].get('laptop.route',{}).get('value',{})
                if wifi and route.get('has_route') and route['interface'] != wifi['interface']:
                    answer+=f"\nĐường đo mạng qua {route['interface']}, khác Wi-Fi {wifi['interface']}; chưa chứng minh Internet qua Wi-Fi."
                if any(p in chosen for p in ('laptop.internet_probe','laptop.dns')):
                    answer+='\nICMP/DNS phản hồi chưa chứng minh truy cập web hoặc xác định nguyên nhân gốc.'
                if reason!='model_answer':answer+='\nĐã dừng chọn Skill: '+reason+'.'
            entry['previous_question']=request
            timeline=[]
            for plan in session.runner.plans[plans_before:]:
                for node in plan.nodes.values():
                    fact=next((f for f in view['facts'].values() if f['function_id']==node.function_id),None)
                    timeline.append({'index':len(timeline)+1,'function_id':node.function_id,
                                     'node_state':node.state,'status':'OK' if fact and node.state=='SUCCEEDED' else 'UNVERIFIED',
                                     'evidence_id':fact['evidence_id'] if fact else None,
                                     'value':fact['value'] if fact else None,'reason':node.reason})
            evidence=[{'id':f['evidence_id'],'port':p,'status':'OK',**f} for p,f in view['facts'].items()]
            return {'answer':answer.strip(),'request':request,'mode':'linux_live','fixture':'LLM + Skill catalog · laptop Linux',
                    'fixture_id':'LINUX-SKILL-CHAT','session_id':sid,'case_status':status,'action':'REPORT',
                    'workflow':'LAPTOP-SKILL-CHAT','workflow_id':None,'method':'core','policy':'dynamic','diagnosis':None,
                    'target':{'scope':'client','selector':'Laptop Linux này'},'calls':session.runner.calls-calls_before,
                    'calls_total':session.runner.calls,'repairs':session.runner.repairs,'evidence':evidence,
                    'evidence_ids':evidence_ids,'status_ok_evidence_ids':[r['id'] for r in evidence],
                    'snapshot':view,'plans':[p.export() for p in session.runner.plans[plans_before:]],
                    'timeline':timeline,'events':[],'contracts':{'a':[],'b':[]},'errors':[],
                    'advice':advice,'intake':{'source':'llm','accepted':bool(advice),
                          'model':advice[0]['model'] if advice else 'LLM local','shared_with_selection':True},'skill_runs':[
                        {k:r[k] for k in ('skill_id','status','calls_this_run','reused_ports','missing_ports')} for r in runs],
                    'rca_assessments':assessments,'stop_reason':reason,'unavailable_skills':unavailable,
                    'catalog_total':catalog['design_total'],'llm_advisor_requested':True,'llm_advisor_ready':ready,
                    'llm_advisor_used':bool(advice),'runbooks':[],'warnings':[],
                    'notice':'READ trên laptop; catalog không tạo capability. RCA xác minh predicate, không chứng minh nguyên nhân/khôi phục.'}


CHAT=SkillChat()
