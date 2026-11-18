"""Connect local LLM catalog selection to existing Skill sessions and RCA assessment."""
from __future__ import annotations

import os
import re
import threading
import time
import math
from functools import lru_cache

from ..core import PlanError
from ..graph_v3.ollama_goal_model import OllamaGoalModel
from ..graph_v3.task_runtime import TaskRuntime
from ..graph_v3.llm_goals import BoundedGoalProposer
from ..graph_v3.task_decomposer import TaskDecomposer
from ..observability.snapshot import VerifiedSnapshot
from ..workflow import normalize
from .skill_launcher import LAUNCHER, SkillSessionError
from .grounded_answer import compose_answer, diagnostic_request, produce_grounded_answer, assessment_summary


@lru_cache(maxsize=1)
def _chat_context():
    from .chat_context import trusted_context
    return trusted_context()


def local_model(*, timeout=60):
    # Trusted startup environment only; HTTP/model text cannot set endpoint/model.
    name = os.environ.get('GATEWAY_LM_CHAT_MODEL', 'qwen3:4b')
    limit = 4_500_000_000 if name == 'qwen3:4b' else 3_000_000_000
    return OllamaGoalModel(name, timeout=timeout, max_parameters=limit, chat_context=_chat_context())


_MODE = {
    'live': {'mode':'linux_live','fixture':'LLM + Skill catalog · laptop Linux','fixture_id':'LINUX-SKILL-CHAT',
             'workflow':'LAPTOP-SKILL-CHAT','target':{'scope':'client','selector':'Laptop Linux này'},
             'scope':'Only this local Linux laptop; never router/client inventory',
             'prefix':'Trong phạm vi laptop này:','where':'trên laptop',
             'custom':'Phiên này chỉ đo chính laptop; chưa có backend cho router/AP, thiết bị khác hoặc target/IP/MAC tùy ý.',
             'unconfirmed':'Chưa xác minh đầy đủ phạm vi yêu cầu; các phép đo hiện tại chỉ đánh giá kết nối từ laptop này.',
             'empty':'Hãy nêu vấn đề mạng trên laptop này; chưa đủ dữ liệu để trả lời.',
             'notice':'READ trên laptop; coverage là phép đo được yêu cầu, không phải causal RCA hoặc khôi phục.'},
    'replay': {'mode':'synthetic_replay','fixture':'LLM + Skill catalog · gateway mô phỏng','fixture_id':'REPLAY-SKILL-CHAT',
               'workflow':'REPLAY-SKILL-CHAT','target':{'scope':'gateway','selector':'Gateway mô phỏng (synthetic)'},
               'scope':'Only the synthetic replay gateway; fixture data, never a real device',
               'prefix':'Trong phạm vi gateway mô phỏng (dữ liệu synthetic, không phải thiết bị thật):','where':'ở chế độ replay',
               'custom':'Phiên replay chỉ có gateway mô phỏng; chưa có backend cho thiết bị khác hoặc target/IP/MAC tùy ý.',
               'unconfirmed':'Chưa xác minh đầy đủ phạm vi yêu cầu; dữ liệu chỉ là fixture mô phỏng của gateway.',
               'empty':'Hãy nêu vấn đề Wi-Fi/gateway cần kiểm tra trong dữ liệu mô phỏng.',
               'notice':'READ trên fixture mô phỏng; không phải số đo thiết bị thật, không phải causal RCA.'},
}


def _model_error(exc):
    return 'model_timeout' if isinstance(exc,TimeoutError) or isinstance(getattr(exc,'reason',None),TimeoutError) else 'model_unavailable'


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
            frequency = f"{v['frequency_mhz']:g} MHz" if v['frequency_mhz'] >= 0 else 'chưa đọc được'
            text = (f"Wi-Fi {v['interface']}: {'đã associated' if v['associated'] else 'chưa associated'}; "
                    f"SSID {v['ssid'] or 'chưa đọc được'}; BSSID {v['bssid'] or 'chưa đọc được'}; "
                    f"kênh {v['channel'] if v['channel'] >= 0 else 'chưa đọc được'}; "
                    f"tần số {frequency}; signal {signal} (không phải RSSI dBm/SNR).")
        elif port == 'client.ipv4':
            text = f"IPv4 của Wi-Fi laptop: {v['address'] if v['configured'] else 'chưa được cấu hình'}."
        elif port == 'client.identity':
            text = 'Đã xác minh định danh của chính laptop đang chạy ứng dụng.'
        elif port == 'expansion.radio_health':
            text = f"Radio gateway (mô phỏng): {'đang bật' if v['radio_up'] else 'đang tắt'}; kênh {v['channel']}; băng tần {v['band']}."
        elif port == 'expansion.ssid_config':
            text = f"SSID gateway (mô phỏng): {('đang phát ' + repr(v['ssid'])) if v['ssid_present'] else 'không phát SSID'}."
        elif port == 'expansion.airtime_usage':
            text = f"Mức dùng kênh (mô phỏng): {v['channel_utilization_pct']:g}%."
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


# One local CPU model request at a time; busy clients get a bounded response instead of queuing threads.
_MODEL_SLOT = threading.BoundedSemaphore(1)


def _phrase(text, phrase):
    return re.search(r'(?<!\w)'+re.escape(phrase)+r'(?!\w)',text) is not None


class SkillChat:
    def __init__(self, launcher=LAUNCHER, *, model_factory=local_model, max_rounds=4,
                 max_elapsed_s=120, clock=time.monotonic):
        if (type(max_rounds) is not int or not 1 <= max_rounds <= 6
                or type(max_elapsed_s) not in (int,float) or not math.isfinite(max_elapsed_s)
                or not 1 <= max_elapsed_s <= 240 or not callable(clock)):
            raise ValueError('invalid_chat_round_budget')
        self.launcher, self.model_factory, self.max_rounds = launcher, model_factory, max_rounds
        self.max_elapsed_s,self.clock=max_elapsed_s,clock

    def _view(self, entry, *, refresh=True):
        with entry['lock'], entry['session']._lock:
            try:
                if refresh:entry['capabilities']=entry['session'].refresh()
                else:entry['session']._validate()
            except PlanError as exc:
                raise SkillSessionError('session_expired') from exc
            return VerifiedSnapshot.from_state(entry['session'].state,entry['runtime'].registry.ports,
                    context_valid=entry['context_valid'],allow_replay=entry['mode']=='replay').export()

    @staticmethod
    def _requested(entry, request):
        text=normalize(request)
        goals={port:meta['title'] for meta in entry['runtime'].registry.question_intents.values()
               if any(_phrase(text,p) for p in meta['phrases']) for port in meta['ports']}
        # An explicit gateway ICMP question does not imply a public Internet measurement.
        if 'gateway' in text and 'internet' not in text and 'chat luong mang' not in text:
            goals.pop('laptop.internet_probe',None)
        return goals

    @classmethod
    def _unconfirmed_parts(cls, entry, request):
        # A recognized clause cannot prove a different, unrecognized clause answered.
        clauses=re.split(r'\b(?:va|voi|and|also|cung nhu)\b|[,;]',normalize(request))
        if len(clauses)==1:return []
        return [part.strip() for part in clauses if part.strip()
                and not cls._requested(entry,part)
                and not any(_phrase(part,phrase)
                            for phrases in entry['runtime'].registry.required_skill_phrases.values()
                            for phrase in phrases)]

    def chat(self, request: str, *, session_id=None, mode='live'):
        if type(request) is not str or not 1 <= len(request.strip()) <= 2000:
            raise ValueError('invalid_chat_request')
        if type(mode) is not str or mode not in _MODE:
            raise ValueError('invalid_chat_mode')
        started=self.clock()
        created=session_id is None
        if created:session_id=self.launcher.create_session(mode)['session_id']
        entry=self.launcher._get(session_id)
        if entry['mode']!=mode:raise ValueError(f'chat_requires_{mode}_session')
        if not hasattr(entry['runtime'].registry,'question_intents'):
            if created:self.launcher.close(session_id)
            raise ValueError('chat_diagnostics_not_approved')
        with self.launcher._lock:lock=entry.setdefault('chat_lock',threading.Lock())
        if not lock.acquire(blocking=False):raise SkillSessionError('session_busy')
        if not _MODEL_SLOT.acquire(blocking=False):
            lock.release()
            if created:self.launcher.close(session_id)
            raise SkillSessionError('model_busy')
        try:
            result=self._turn(request.strip(),session_id,entry,started)
            saved=self.launcher.checkpoint(session_id)
            result['persistence']={'enabled':self.launcher.storage is not None,'checkpoint_facts':saved,'restored_facts':entry.get('restored_facts',0)}
            return result
        except Exception:
            if created:
                try:self.launcher.close(session_id)
                except SkillSessionError:pass
            raise
        finally:
            _MODEL_SLOT.release();lock.release()

    def _turn(self, request, sid, entry, started):
        runtime,session=entry['runtime'],entry['session']
        deadline=started+self.max_elapsed_s
        calls_before=session.runner.calls;plans_before=len(session.runner.plans)
        timings={k:0.0 for k in ('setup','catalog','inference','probe','execution','rca')}
        timings['setup']=(self.clock()-started)*1000
        def timed(stage, method, *args, **kwargs):
            start=self.clock()
            try:return method(*args,**kwargs)
            finally:timings[stage]+=(self.clock()-start)*1000
        def view(refresh=True):return timed('probe',self._view,entry,refresh=refresh)
        def run_skill(skill):
            return timed('execution',self.launcher.run,sid,skill,
                         deadline=runtime._clock()+max(0,deadline-self.clock()))
        task_trace=[]
        def assess(workflows, *, adaptive=False):
            allowed=set(goals) if goals else set(p for skill in attempted
                    for p in {**entry['actions'][skill]['required_ports'],**entry['actions'][skill]['optional_ports']})
            result=timed('rca',TaskRuntime.run_session,session,request=request,
                         workflows=workflows,allowed_ports=sorted(allowed),
                         diagnostic=adaptive and diagnostic_request(request),max_steps=2,
                         deadline=runtime._clock()+max(0,deadline-self.clock()))
            task_trace.append({k:result[k] for k in ('mode','status','reason','steps','calls_added')})
            return result['assessments']
        def check_deadline():return self.clock()<deadline and runtime._clock()<session.expires_at
        view()
        prof=_MODE[entry['mode']]
        catalog=timed('catalog',self.launcher.catalog,entry['mode'],entry=entry)
        rows={r['skill_id']:r for r in catalog['rows']}
        docs=[[r['skill_id'],r['name'],r['availability'],r['runtime_scope']] for r in catalog['rows']]
        goals=self._requested(entry,request)
        unconfirmed=self._unconfirmed_parts(entry,request)
        normalized=normalize(request)
        unavailable=[skill for skill,phrases in runtime.registry.required_skill_phrases.items()
                     if rows[skill]['availability']=='UNAVAILABLE' and any(_phrase(normalized,p) for p in phrases)]
        attempted,runs,advice,selected,assessments=[],[],[],[],[]
        rejections,recovery_attempts,model_calls=0,0,0
        model=None
        goal_proposal={'status':'NOT_NEEDED','goals':[]}
        recovery_runs=[];feedback=None;seen=set();reason='round_budget_exhausted';ready=False
        def coverage(facts):
            missing=sorted(set(goals)-set(facts))
            return {'requested_ports':list(goals),'satisfied_ports':sorted(set(goals)&set(facts)),
                    'missing_ports':missing,'unsupported_skills':list(unavailable),
                    'unconfirmed_parts':unconfirmed,
                    'complete':bool(goals) and not missing and not unavailable and not custom_target and not blocked and not unconfirmed,
                    'scope_confirmed':bool(goals) and not custom_target and not blocked and not unconfirmed}
        def inference_budget():
            # Re-read remaining TTL locally; catalog/setup may have consumed time.
            snapshot=view(refresh=False)
            reserve=min(5,self.max_elapsed_s*.1)
            remaining=min(deadline-self.clock(),session.expires_at-runtime._clock())-reserve
            relevant=set(snapshot['facts'])&(set(goals) if goals else set(snapshot['facts']))
            if relevant:
                remaining=min(remaining,min(snapshot['facts'][p]['expires_in_s'] for p in relevant)-reserve)
            return remaining
        def recover(ports):
            nonlocal recovery_attempts,reason
            if recovery_attempts or not ports or not check_deadline():return False
            supported={r.function_id for r in entry['capabilities'].functions if r.status=='AVAILABLE'}
            # Only expired registered ports with still-supported producers can be reread.
            owners=[]
            for port in ports:
                options=[(len(a['required_ports'])+len(a['optional_ports']),key) for key,a in entry['actions'].items()
                         if port in {**a['required_ports'],**a['optional_ports']}
                         and any(f.id in supported and port in f.outputs for f in runtime.registry.functions.values())]
                if options:owners.append(min(options)[1])
            owners=list(dict.fromkeys(owners))
            if not owners:return False
            recovery_attempts+=1
            for skill in owners:
                if not check_deadline() or session.runner.calls>=session.runner.max_calls:break
                result=run_skill(skill)
                runs.append(result)
                recovery_runs.append({'skill_id':skill,'reason':'expired_evidence',
                                      'calls':result['calls_this_run'],'missing_ports':result['missing_ports']})
            return True
        blocked=TaskDecomposer(runtime.registry).is_write_intent(request)
        custom_target=bool(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b|(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',request)) or any(
            _phrase(normalized,p) for p in runtime.registry.nonlocal_scope_phrases)
        if blocked:reason='write_intent_requires_approval'
        elif custom_target:reason='custom_target_not_supported'
        elif not check_deadline():reason='turn_deadline_exhausted'
        elif inference_budget()<=0:reason='finalization_budget_reserved'
        else:
            try:
                if self.model_factory is local_model:
                    model=timed('inference',self.model_factory,
                                timeout=min(240 if os.environ.get('GATEWAY_LM_CHAT_MODEL','qwen3:4b')=='qwen3:4b' else 60,max(.001,inference_budget())))
                else:
                    model=timed('inference',self.model_factory)
                if getattr(model,'local_only',None) is not True or not callable(getattr(model,'choose_skills',None)):
                    raise ValueError('local_skill_model_required')
                ready=True
                if (not goals or unconfirmed) and callable(getattr(model,'propose_goals',None)):
                    view()
                    if check_deadline() and inference_budget()>0:
                        model_calls+=1
                        original_timeout=getattr(model,'timeout',None)
                        if original_timeout is not None:model.timeout=min(original_timeout,max(.001,inference_budget()))
                        try:
                            proposal=timed('inference',BoundedGoalProposer(model).propose,
                                request,runtime.registry,session.state,TaskDecomposer(runtime.registry))
                        finally:
                            if original_timeout is not None:model.timeout=original_timeout
                        goal_proposal={'status':proposal.decision,'reason':proposal.reason,'goals':list(proposal.goals)}
                        if proposal.decision=='READY':
                            goals.update({port:port for port in proposal.goals})
                for round_index in range(self.max_rounds):
                    if not check_deadline():reason='turn_deadline_exhausted';break
                    current_view=view();current=findings(current_view)
                    cov=coverage(current)
                    supported={f.function_id for f in entry['capabilities'].functions if f.status=='AVAILABLE'}
                    producible={port for f in runtime.registry.functions.values() if f.id in supported for port in f.outputs}
                    outputs={skill:[p for p in {**action['required_ports'],**action['optional_ports']} if p in producible]
                             for skill,action in entry['actions'].items()
                             if rows[skill]['availability'] in {'READY','DEGRADED'} and skill not in attempted}
                    missing_actions={port:sorted((skill for skill,ports in outputs.items() if port in ports),
                                                key=lambda skill:len(outputs[skill])) for port in cov['missing_ports']}
                    # Leave a rendering/probe window and never spend a fresh
                    # measurement's remaining lifetime waiting for another RPC.
                    remaining=inference_budget()
                    if remaining<=0:
                        selected=[p for p in current if not goals or p in goals]
                        reason='finalization_budget_reserved'
                        break
                    context={'required_unavailable':unavailable,'attempted':attempted,
                             'runnable_outputs':outputs if cov['missing_ports'] or not goals else {},
                             'missing_goal_actions':missing_actions,
                             'findings':[{'id':f['id'],'text':f['text']} for f in current.values()],
                             'requested_goals':[{'port':p,'description':title} for p,title in goals.items()],
                             'missing_goals':cov['missing_ports'],'feedback':feedback,
                             'unconfirmed_parts':unconfirmed,
                             'rca':[{'workflow':a['workflow'],'decision':a['decision'],
                                     'candidate_goals':a['candidate_goals'],
                                     'verified_claims':[r['diagnosis'] for r in a['claim_results'] if r['truth']=='TRUE']} for a in assessments],
                             'remaining_tool_calls':max(0,session.runner.max_calls-session.runner.calls),
                             'last_round':round_index==self.max_rounds-1,
                             'previous_question':entry.get('previous_question',''),
                             'inference_timeout_s':min(getattr(model,'timeout',60),remaining),
                             'scope':prof['scope']}
                    try:
                        model_calls+=1
                        raw=timed('inference',model.choose_skills,request,docs,context)
                        choice=validate_choice(raw,rows,current,attempted)
                    except (OSError,TimeoutError) as exc:
                        reason=_model_error(exc)
                        if reason=='model_unavailable':ready=False
                        break
                    except Exception:
                        rejections+=1;reason='invalid_model_proposal'
                        feedback={'reason':reason,'instruction':'Return only allowed Skill/finding IDs; no commands or arguments.'}
                        if rejections>=2:break
                        continue
                    # Never execute a post-timeout or post-close proposal.
                    fresh=view()
                    if not check_deadline():reason='turn_deadline_exhausted';break
                    stale=set(choice['finding_ids'])-set(fresh['facts'])
                    if stale:
                        recover(stale);fresh=view()
                        if stale-set(fresh['facts']):reason='evidence_refresh_unavailable';selected=choice['finding_ids'];break
                    signature=(choice['decision'],tuple(choice['skill_ids']),tuple(choice['finding_ids']),
                               tuple(choice['unavailable_ids']),tuple(sorted(f['evidence_id'] for f in fresh['facts'].values())))
                    if signature in seen:reason='no_progress';break
                    seen.add(signature)
                    advice.append({'model':getattr(model,'model','local-test'),'accepted':True,
                                   'selected':', '.join(choice['skill_ids']) or choice['decision'],
                                   'decision':choice['decision'],'finding_ids':choice['finding_ids'],
                                   'evidence_ids':[f['evidence_id'] for f in fresh['facts'].values()],
                                   'catalog_retrieval':getattr(model,'last_catalog',None)})
                    unavailable=list(dict.fromkeys(unavailable+choice['unavailable_ids']))
                    if choice['decision']!='measure':
                        selected=choice['finding_ids']
                        cov=coverage(fresh['facts'])
                        if choice['decision']=='answer' and cov['missing_ports'] and round_index<self.max_rounds-1:
                            reason='incomplete_coverage'
                            feedback={'reason':reason,'missing_goals':cov['missing_ports'],
                                      'instruction':'Measure an approved action from missing_goal_actions before answering; selected Skill completion is not whole-request completion.'}
                            advice[-1].update(accepted=False,reason=reason)
                            continue
                        reason='model_answer' if selected else 'needs_clarification'
                        break
                    if round_index==self.max_rounds-1:reason='round_budget_exhausted';break
                    for skill in choice['skill_ids']:
                        if not check_deadline():reason='turn_deadline_exhausted';break
                        result=run_skill(skill)
                        attempted.append(skill);runs.append(result)
                    workflows=list(dict.fromkeys(w for skill in attempted for w in runtime.registry.skill_workflows[skill]))
                    assessments=assess(workflows,adaptive=True)
                    feedback={'failed_skills':[r['skill_id'] for r in runs if r['status']!='MEASURED'],
                              'missing_goals':coverage(view(refresh=False)['facts'])['missing_ports']}
                    if session.runner.calls>=session.runner.max_calls:reason='tool_budget_exhausted';break
            except SkillSessionError:raise
            except (OSError,TimeoutError) as exc:
                reason=_model_error(exc)
                if reason=='model_unavailable':ready=False
            except (RuntimeError,ValueError,TypeError,PlanError):
                if session.closed:raise SkillSessionError('session_expired')
                reason='read_execution_unavailable' if ready else 'model_unavailable'
        def answer_ports(snapshot, proposed):
            current=findings(snapshot)
            ports=[p for p in proposed if p in current]
            if not blocked and not custom_target and (ports or runs or reason in {'model_timeout','finalization_budget_reserved'}):
                ports=list(dict.fromkeys([*ports,*(p for p in goals if p in current)]))
            if not ports and runs:
                ports=list(dict.fromkeys(p for r in runs for p in r['snapshot']['facts'] if p in current))
            return [p for p in ports if p in goals] if goals else ports

        draft=None
        draft_proofs={}
        answer_calls=0
        synthesis={'used_llm':False,'reason':'renderer','calls':0}
        if (reason=='model_answer' and check_deadline()
                and os.environ.get('GATEWAY_LM_ANSWER_SYNTHESIS','1').lower() not in {'0','off','false','no'}
                and callable(getattr(model,'complete_answer',None))):
            before_answer=view()
            ports=answer_ports(before_answer,selected)
            answer_budget=min(24,deadline-self.clock(),session.expires_at-runtime._clock())
            if ports and min(before_answer['facts'][p]['expires_in_s'] for p in ports)>answer_budget+1:
                draft_proofs={p:before_answer['facts'][p]['evidence_id'] for p in ports}
                def completion(payload):
                    nonlocal model_calls,answer_calls
                    fresh=view(refresh=False)
                    if any(fresh['facts'].get(p,{}).get('evidence_id')!=eid for p,eid in draft_proofs.items()):
                        raise RuntimeError('answer_evidence_changed')
                    remaining=min(deadline-self.clock(),session.expires_at-runtime._clock())
                    if remaining<=0:raise TimeoutError('answer_deadline_exhausted')
                    model_calls+=1
                    answer_calls+=1
                    return timed('inference',model.complete_answer,payload,timeout=min(12,remaining))
                # Deliberately outside the entry lock: close/context invalidation
                # must remain possible while an untrusted model is running.
                draft=produce_grounded_answer(request,ports,before_answer['facts'],
                                               findings(before_answer),completion)
                synthesis.update(used_llm=draft.used_llm,reason=draft.reason,
                                 draft_reason=draft.reason,calls=answer_calls)
            elif ports:
                synthesis['reason']='insufficient_freshness_window'

        with entry['lock']:
            view(refresh=False)
            if assessments:assessments=assess([a['workflow'] for a in assessments])
            final=view(refresh=not bool(assessments))
            expired=(set(selected)|set(draft_proofs))-set(final['facts'])
            if expired and not recovery_attempts and not blocked and not custom_target:
                recover(expired)
                if assessments:assessments=assess([a['workflow'] for a in assessments])
                final=view(refresh=not bool(assessments))
            if set(selected)-set(final['facts']):reason='evidence_expired_during_answer'
            current=findings(final)
            selected=answer_ports(final,selected)
            if not check_deadline():reason='turn_deadline_exhausted'
            cov=coverage(final['facts'])
            if not cov['complete'] and reason=='model_answer':reason='incomplete_coverage' if goals else 'intent_scope_unconfirmed'
            chosen={p:final['facts'][p] for p in selected}
            answer=compose_answer(request,selected,final['facts'],current)
            if draft:
                final_proofs={p:final['facts'][p]['evidence_id'] for p in selected}
                if (draft_proofs==final_proofs and check_deadline()
                        and set(draft.evidence_ids)=={f['evidence_id'] for f in chosen.values()}):
                    answer=draft.answer
                else:
                    synthesis.update(used_llm=False,reason='evidence_changed_or_deadline')
            if unavailable:answer+='\n'+'\n'.join(f"{rows[s]['name']}: chưa chạy được {prof['where']} ({rows[s]['reason']})." for s in unavailable)
            if cov['missing_ports'] and not blocked and not custom_target:
                answer+='\nChưa xác minh: '+', '.join(dict.fromkeys(goals[p] for p in cov['missing_ports']))+'.'
            if unconfirmed and not blocked and not custom_target:
                answer+='\n'+prof['unconfirmed']
            if blocked:
                status='BLOCKED';answer='Ứng dụng chỉ đọc; không tự thay đổi cấu hình hoặc khởi động lại thiết bị.'
            elif custom_target:
                status='NEEDS_INPUT';answer=prof['custom']
            elif not chosen:
                status='UNAVAILABLE' if unavailable else 'NEEDS_INPUT'
                if reason=='turn_deadline_exhausted':answer+='\nĐã hết thời gian xử lý; số đo trước đó không còn hiệu lực để kết luận hiện tại.'
                elif reason in {'model_timeout','finalization_budget_reserved'}:answer+='\nLLM chưa hoàn tất trong thời gian cho phép; chưa có số đo còn hiệu lực để kết luận.'
                elif not ready:answer+='\nKhông kết nối được LLM local; hãy kiểm tra dịch vụ Ollama.'
                elif runs:answer+='\nChưa có evidence còn hiệu lực sau lúc suy luận; hãy đo lại.'
                elif not answer.strip():answer=prof['empty']
            else:
                status='MEASURED' if cov['complete'] and reason=='model_answer' else 'PARTIAL'
                wifi=final['facts'].get('laptop.wifi',{}).get('value',{})
                route=final['facts'].get('laptop.route',{}).get('value',{})
                diagnostic=diagnostic_request(request)
                if diagnostic and 'laptop.wifi' in chosen and wifi and route.get('has_route') and route['interface']!=wifi['interface']:
                    answer+=f"\nĐường đo mạng qua {route['interface']}, khác Wi-Fi {wifi['interface']}; chưa chứng minh Internet qua Wi-Fi."
                    chosen['laptop.route']=final['facts']['laptop.route']
                if diagnostic and any(p in chosen for p in ('laptop.internet_probe','laptop.dns')):
                    answer+='\nICMP/DNS phản hồi chưa chứng minh truy cập web hoặc nguyên nhân gốc.'
                if diagnostic:
                    assessment=assessment_summary(chosen,assessments)
                    if assessment:answer=assessment+'\n'+answer
                    answer=prof['prefix']+'\n'+answer
                    answer+='\nChưa đủ bằng chứng để xác định nguyên nhân hoặc xác nhận toàn bộ kết nối hoạt động bình thường.'
                    answer+='\nBước tiếp theo: xác định thiết bị/ứng dụng bị ảnh hưởng và kiểm tra đúng lúc gặp lỗi; chưa có cơ sở chọn thay đổi cấu hình cụ thể.'
                if reason!='model_answer':
                    messages={'incomplete_coverage':'Còn phần yêu cầu chưa đủ bằng chứng',
                              'intent_scope_unconfirmed':'Chưa xác định đủ phạm vi câu hỏi',
                              'invalid_model_proposal':'LLM chưa đưa được lựa chọn hợp lệ sau các lượt sửa',
                              'no_progress':'Các lựa chọn tiếp theo không tạo thêm tiến triển',
                              'model_unavailable':'Mất kết nối LLM; dưới đây chỉ dùng các phép đo còn hiệu lực',
                              'model_timeout':'LLM chưa kịp hoàn tất; kết quả trên được tổng hợp từ các số đo còn hiệu lực',
                              'finalization_budget_reserved':'Đã dừng suy luận để trả kết quả khi bằng chứng còn hiệu lực',
                              'tool_budget_exhausted':'Đã hết số phép đo được phép trong phiên',
                              'round_budget_exhausted':'Đã hết số vòng lựa chọn trong lượt hỏi',
                              'turn_deadline_exhausted':'Đã hết thời gian xử lý lượt hỏi',
                              'evidence_expired_during_answer':'Evidence hết hạn; cần đo lại',
                              'evidence_refresh_unavailable':'Chưa thể làm mới evidence hết hạn',
                              'read_execution_unavailable':'Một số phép đo READ chưa thực hiện được'}
                    answer+='\n'+messages.get(reason,'Chưa đủ bằng chứng để kết thúc yêu cầu')+'.'
            # Every exported RCA proof must still appear in the final fresh snapshot.
            valid_ids={f['evidence_id'] for f in final['facts'].values()}
            for a in assessments:
                stale_claim=False
                for claim in a['claim_results']:
                    if claim['truth']=='TRUE' and not set(claim['evidence_ids'])<=valid_ids:
                        claim.update(truth='UNKNOWN',evidence_ids=[]);stale_claim=True
                if stale_claim:a.update(decision='INCONCLUSIVE',diagnosis=None,evidence_ids=[])
            entry['previous_question']=request
            timeline=[]
            for plan in session.runner.plans[plans_before:]:
                for node in plan.nodes.values():
                    fact=next((f for f in final['facts'].values() if f['function_id']==node.function_id),None)
                    timeline.append({'index':len(timeline)+1,'function_id':node.function_id,'node_state':node.state,
                                     'status':'OK' if fact and node.state=='SUCCEEDED' else 'NO_LONGER_VALID' if node.state=='SUCCEEDED' else 'UNVERIFIED',
                                     'verified_at_execution':node.state=='SUCCEEDED',
                                     'evidence_id':fact['evidence_id'] if fact else None,
                                     'historical_evidence_ids':list(node.output_evidence.values()),
                                     'value':fact['value'] if fact else None,'reason':node.reason})
            evidence=[{'id':f['evidence_id'],'port':p,'status':'OK',**f} for p,f in final['facts'].items()]
            timings['total']=(self.clock()-started)*1000
            return {'answer':answer.strip(),'request':request,'mode':prof['mode'],'fixture':prof['fixture'],
                    'fixture_id':prof['fixture_id'],'session_id':sid,'case_status':status,'action':'REPORT',
                    'workflow':prof['workflow'],'workflow_id':None,'method':'core','policy':'dynamic','diagnosis':None,
                    'target':dict(prof['target']),'synthetic_only':entry['mode']=='replay','calls':session.runner.calls-calls_before,
                    'calls_total':session.runner.calls,'repairs':session.runner.repairs,'evidence':evidence,
                    'evidence_ids':[f['evidence_id'] for f in chosen.values()],
                    'status_ok_evidence_ids':[r['id'] for r in evidence],
                    'snapshot':final,'plans':[p.export() for p in session.runner.plans[plans_before:]],
                    'timeline':timeline,'events':[],'contracts':{'a':[],'b':[]},'errors':[],
                    'advice':advice,'intake':{'source':'llm','accepted':bool(advice),
                          'model':advice[0]['model'] if advice else 'LLM local','shared_with_selection':True},
                    'skill_runs':[{k:r[k] for k in ('skill_id','status','calls_this_run','reused_ports','missing_ports')} for r in runs],
                    'goal_proposal':goal_proposal,'task_trace':task_trace,'function_retrievals':session.retrievals,
                    'runbooks':((getattr(model,'last_catalog',{}).get('runbooks') or {}).get('documents',[])),
                    'runtime_features':{'task_runtime':'USED' if task_trace else 'READY',
                        'adaptive_rca':'USED' if any(t['mode']=='DIAGNOSE' for t in task_trace) else 'LOOKUP' if task_trace else 'NOT_RUN',
                        'repair_budget':session.runner.max_repairs,'ready_selection':session.method,
                        'checkpoint_journal':'ACTIVE' if self.launcher.storage else 'NOT_CONFIGURED',
                        'catalog_semantic':getattr(model,'last_catalog',{}).get('semantic',{'status':'NOT_CONFIGURED'}),
                        'function_semantic':{'method':session.method,'used':any(r.get('selected_ready') for r in session.retrievals),'fallbacks':[r for r in session.retrievals if r.get('semantic_status')=='ERROR']},
                        'runbook_profile':((getattr(model,'last_catalog',{}).get('runbooks') or {}).get('firmware')),
                        'runbook_documents':len((getattr(model,'last_catalog',{}).get('runbooks') or {}).get('documents',[])),
                        'cloud':'NOT_CONFIGURED','write':'DISABLED','router_backend':'NOT_CONFIGURED',
                        'monitoring':'INSUFFICIENT_SAMPLES'},
                    'rca_assessments':assessments,'stop_reason':reason,'unavailable_skills':unavailable,'coverage':cov,
                    'recovery_attempts':recovery_attempts,'recovery_runs':recovery_runs,'proposal_rejections':rejections,
                    'model_calls':model_calls,'timings_ms':timings,
                    'answer_synthesis':synthesis,
                    'answer_kind':'diagnostic' if diagnostic_request(request) else 'lookup',
                    'user_input_required':reason=='needs_clarification' and not bool(runs),
                    'diagnostic_status':'INCONCLUSIVE' if diagnostic_request(request) else None,
                    'catalog_total':catalog['design_total'],'llm_advisor_requested':True,'llm_advisor_ready':ready,
                    'llm_advisor_used':bool(advice),'warnings':[],
                    'notice':prof['notice']}


CHAT=SkillChat(max_elapsed_s=240)
