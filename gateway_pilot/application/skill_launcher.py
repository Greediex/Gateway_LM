"""Local laptop-first Skill catalog and bounded Core session application."""
from __future__ import annotations

import threading
import time
from collections import Counter
from uuid import uuid4

from ..core import PlanError
from ..skill_expansion.catalog import SkillCatalog
from ..skill_expansion.deployment import composition,deployment
from ..skill_expansion.runtime_bridge import SkillNotReady
from ..observability.snapshot import VerifiedSnapshot
from ..features.laptop_network import diagnose_snapshot


class SkillSessionError(ValueError):
    pass


class SkillLauncher:
    def __init__(self, *, factory=composition, max_sessions=8, clock=time.monotonic):
        self._factory,self._max_sessions,self._clock=factory,max_sessions,clock
        self._sessions={}
        self._lock=threading.RLock()
        self._measure_lock=threading.RLock()
        self._design=SkillCatalog.load()

    @staticmethod
    def _mode(mode):
        if type(mode) is not str or mode not in {'live','replay'}:
            raise SkillSessionError('invalid_mode')
        return mode

    def _reason(self, sid, mode):
        if sid=='SK13':return 'WRITE_OUT_OF_SCOPE'
        if mode=='replay':return 'NOT_IN_REVIEWED_REPLAY_PROFILE'
        reasons={'B04':'REQUIRES_RSSI_AND_SNR','B07':'REQUIRES_ROAMING_HISTORY',
                 'A04':'REQUIRES_OUI_VENDOR_DATA','A06':'REQUIRES_INDEPENDENT_IDENTITY_EVIDENCE'}
        if sid in reasons:return reasons[sid]
        skill=self._design.skills[sid]
        return 'REQUIRES_ROUTER_BACKEND' if 'gateway' in skill.scope or 'network' in skill.scope else 'REQUIRES_WORKFLOW_OR_MORE_SOURCES'

    def catalog(self, mode='live', *, entry=None):
        mode=self._mode(mode)
        _,_,_,actions=deployment(mode)
        rows=[]
        for skill in self._design.skills.values():
            rows.append({'skill_id':skill.id,'name':skill.name_vi,'domain':skill.domain,'kind':'design',
                         'availability':'UNAVAILABLE','reason':self._reason(skill.id,mode),
                         'runtime_scope':actions.get(skill.id,{}).get('scope',skill.scope),'mode':mode})
        rows.extend({'skill_id':a['skill_id'],'name':a['name'],'domain':a['domain'],'kind':'laptop',
                     'availability':'UNVERIFIED','reason':'INITIALIZE_SESSION','runtime_scope':a['scope'],'mode':mode}
                    for a in actions.values() if a['kind']=='laptop')
        for row in rows:
            if row['skill_id'] not in actions:continue
            row.update(availability='UNVERIFIED',reason='INITIALIZE_SESSION')
            if entry is None:continue
            action=actions[row['skill_id']]
            try:
                entry['bridge'].plan(row['skill_id'],snapshot=entry['capabilities'])
            except (SkillNotReady,PlanError):
                row.update(availability='UNAVAILABLE',reason='REQUIRED_READ_CAPABILITY_UNAVAILABLE')
            else:
                supported={f.function_id for f in entry['capabilities'].functions if f.status=='AVAILABLE'}
                optional={pid for pid in action['optional_ports'] if any(f.id in supported and pid in f.outputs
                                  for f in entry['runtime'].registry.functions.values())}
                degraded=set(action['optional_ports'])-optional
                row.update(availability='DEGRADED' if degraded else 'READY',reason='OPTIONAL_DATA_UNAVAILABLE' if degraded else 'READ_CAPABILITY_VERIFIED')
        rows.sort(key=lambda r:(r['kind']!='laptop',r['domain'],r['skill_id']))
        return {'mode':mode,'design_total':len(self._design.skills),'native_total':sum(a['kind']=='laptop' for a in actions.values()),
                'rows':rows,'counts':dict(Counter(r['availability'] for r in rows)),
                'requires_session':entry is None}

    def _cleanup(self):
        for sid,e in list(self._sessions.items()):
            if e['session'].closed or self._clock()>=e['session'].expires_at:
                with e['lock']:
                    e['session'].close();del self._sessions[sid]

    def create_session(self, mode='live'):
        mode=self._mode(mode)
        with self._lock:
            self._cleanup()
            if len(self._sessions)>=self._max_sessions:raise SkillSessionError('session_capacity_limit')
            entry=self._factory(mode)
            entry.update(mode=mode,capabilities=entry['runtime'].probe(),lock=threading.RLock())
            sid=uuid4().hex;self._sessions[sid]=entry
            return {'session_id':sid,'mode':mode,'expires_in_s':max(0,entry['session'].expires_at-self._clock()),
                    'catalog':self.catalog(mode,entry=entry)}

    def _get(self, sid):
        if type(sid) is not str or len(sid)!=32 or any(c not in '0123456789abcdef' for c in sid):
            raise SkillSessionError('session_expired')
        with self._lock:
            self._cleanup()
            if sid not in self._sessions:raise SkillSessionError('session_expired')
            return self._sessions[sid]

    def close(self, sid):
        with self._lock:
            entry=self._get(sid)
            with entry['lock']:
                entry['session'].close();del self._sessions[sid]
        return {'closed':True}

    def run(self, session_id, skill_id):
        entry=self._get(session_id)
        if type(skill_id) is not str or len(skill_id)>100:raise SkillSessionError('invalid_skill_id')
        mode,session=entry['mode'],entry['session']
        if skill_id not in entry['actions']:
            if skill_id not in self._design.skills:raise SkillSessionError('unknown_skill')
            return {'session_id':session_id,'skill_id':skill_id,'mode':mode,'synthetic_only':mode=='replay',
                    'status':'UNAVAILABLE','summary':'Skill này chưa có đủ nguồn dữ liệu hoặc workflow trong profile đã chọn.',
                    'reason':self._reason(skill_id,mode),'missing_ports':[], 'evidence_ids':[],
                    'snapshot':{'facts':{},'missing_ports':[],'expires_in_s':0},
                    'calls_this_run':0,'calls_total':session.runner.calls,'reused_ports':[],'steps':[],
                    'limitations':['Catalog presence does not grant runtime capability.']}
        with entry['lock'],self._measure_lock:
            if session.closed:raise SkillSessionError('session_expired')
            action=entry['actions'][skill_id]
            goals=list(action['required_ports'])+list(action['optional_ports'])
            before={pid:e['id'] for pid in goals if (e:=session.state.fact(pid)) is not None}
            calls=session.runner.calls;plan_start=len(session.runner.plans)
            error=None
            try:
                entry['capabilities']=entry['runtime'].probe()
                entry['bridge'].execute(skill_id,snapshot=entry['capabilities'],session=session)
                available={r.function_id for r in entry['capabilities'].functions if r.status=='AVAILABLE'}
                optional=[pid for pid in action['optional_ports'] if any(f.id in available and pid in f.outputs
                           for f in entry['runtime'].registry.functions.values())]
                if optional:session.execute(optional,request='Optional READ telemetry for '+skill_id)
            except (PlanError,SkillNotReady) as exc:
                if isinstance(exc, SkillNotReady):
                    session.close()
                if session.closed:raise SkillSessionError('session_expired') from exc
                error='READ_EXECUTION_UNAVAILABLE'
            view=VerifiedSnapshot.from_state(session.state,goals,context_valid=entry['context_valid'],allow_replay=mode=='replay').export()
            facts=view['facts']
            if not view['context_valid']:
                session.close();raise SkillSessionError('session_expired')
            missing=set(goals)-set(facts)
            required_missing=set(action['required_ports'])-set(facts)
            status='PARTIAL' if missing else 'MEASURED'
            if required_missing and not facts:status='UNAVAILABLE'
            summary='Đã thu phép đo từ laptop.' if mode=='live' else 'Đã xác minh fixture synthetic qua Core; không phải số đo thiết bị thật.'
            if error:summary='Một số phép đo chưa hoàn thành; xem dữ liệu thiếu và evidence còn hiệu lực.'
            if mode=='live' and skill_id in {'laptop.network.inspect','laptop.wifi.inspect'}:
                d=diagnose_snapshot(view,{'network.laptop.connectivity':{'status':'READY'},'network.laptop.wifi':{'status':'READY'}})
                summary='\n'.join(r['summary'] for r in d if skill_id=='laptop.network.inspect' or r['feature_id'].endswith('wifi'))
            if skill_id=='A08' and 'expansion.client_association' in facts:
                associated=facts['expansion.client_association']['value']['associated']
                summary='Laptop đang associated với AP; xem AP ID trong evidence.' if associated else 'Laptop hiện chưa associated với AP.'
            if required_missing and status=='MEASURED':status='PARTIAL'
            if not error and required_missing:error='REQUIRED_EVIDENCE_MISSING'
            steps=[{'function_id':n.function_id,'state':n.state,'reason':n.reason,'revision':p.revision}
                   for p in session.runner.plans[plan_start:] for n in p.nodes.values()]
            return {'session_id':session_id,'skill_id':skill_id,'mode':mode,'synthetic_only':mode=='replay',
                    'status':status,'summary':summary,'reason':error or 'VERIFIED_MEASUREMENTS',
                    'missing_ports':sorted(missing),'evidence_ids':[r['evidence_id'] for r in facts.values()],
                    'snapshot':view,'calls_this_run':session.runner.calls-calls,'calls_total':session.runner.calls,
                    'reused_ports':[pid for pid,r in facts.items() if before.get(pid)==r['evidence_id']],
                    'steps':steps,'limitations':action['limitations']}


LAUNCHER=SkillLauncher()
