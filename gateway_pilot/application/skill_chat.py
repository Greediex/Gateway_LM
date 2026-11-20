"""Connect local LLM catalog selection to existing Skill sessions and RCA assessment."""
from __future__ import annotations

import os
import re
import threading
import time
import math
from functools import lru_cache
from types import SimpleNamespace

from ..core import PlanError
from ..graph_v3.ollama_goal_model import OllamaGoalModel
from ..graph_v3.task_runtime import TaskRuntime
from ..graph_v3.llm_goals import BoundedGoalProposer
from ..graph_v3.task_decomposer import TaskDecomposer
from ..observability.snapshot import VerifiedSnapshot
from ..skill_expansion.replay_sim import MODE as REPLAY_SIM, NOTICE as SIM_NOTICE, STATES as SIM_STATES
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
             'origin':'Từ laptop','where':'trên laptop',
             'custom':'Phiên này chỉ đo chính laptop; chưa có backend cho router/AP, thiết bị khác hoặc target/IP/MAC tùy ý.',
             'unconfirmed':'Chưa xác minh đầy đủ phạm vi yêu cầu; các phép đo hiện tại chỉ đánh giá kết nối từ laptop này.',
             'empty':'Hãy nêu vấn đề mạng trên laptop này; chưa đủ dữ liệu để trả lời.',
             'notice':'READ trên laptop; coverage là phép đo được yêu cầu, không phải causal RCA hoặc khôi phục.'},
    'replay': {'mode':'synthetic_replay','fixture':'LLM + Skill catalog · gateway mô phỏng','fixture_id':'REPLAY-SKILL-CHAT',
               'workflow':'REPLAY-SKILL-CHAT','target':{'scope':'gateway','selector':'Gateway mô phỏng (synthetic)'},
               'scope':'Only the synthetic replay gateway; fixture data, never a real device',
               'origin':'Từ dữ liệu gateway mô phỏng','where':'ở chế độ replay',
               'custom':'Phiên replay chỉ có gateway mô phỏng; chưa có backend cho thiết bị khác hoặc target/IP/MAC tùy ý.',
               'unconfirmed':'Chưa xác minh đầy đủ phạm vi yêu cầu; dữ liệu chỉ là fixture mô phỏng của gateway.',
               'empty':'Hãy nêu vấn đề Wi-Fi/gateway cần kiểm tra trong dữ liệu mô phỏng.',
               'notice':'READ trên fixture mô phỏng; không phải số đo thiết bị thật, không phải causal RCA.'},
}

_LAPTOP_TOPICS = (
    ('Đường Internet từ laptop', ('wan', 'internet', 'nha mang', 'ra ngoai', 'ip cong cong'),
     ('laptop.internet_probe',)),
    ('Wi-Fi', ('wifi', 'wi fi', 'wireless', 'song', 'tin hieu', 'signal', 'ssid', 'bssid',
      'radio', 'ket noi khong day', 'kenh', 'channel', 'tan so', 'frequency'), ('laptop.wifi',)),
    ('DNS', ('dns', 'phan giai', 'ten mien', 'domain name'), ('laptop.dns',)),
    ('Gateway', ('gateway', 'router', 'modem'), ('laptop.gateway_probe', 'laptop.route')),
    ('Tuyến IPv4', ('cong mac dinh', 'default route', 'tuyen', 'dinh tuyen', 'route',
      'interface', 'giao dien'), ('laptop.route',)),
    ('IPv4 laptop', ('ipv4', 'ip', 'dia chi'), ('client.ipv4',)),
    ('Định danh laptop', ('dinh danh', 'client id', 'laptop nao', 'identity'), ('client.identity',)),
    ('AP của laptop', ('ap nao', 'diem phat nao', 'access point'), ('expansion.client_association',)),
)
_WAN_SCOPE = 'WAN của router cần quyền đọc router, hiện chưa có trong chế độ laptop.'
_DIAGNOSTIC_LIMIT = 'Chưa đủ bằng chứng để xác định nguyên nhân hoặc xác nhận toàn bộ kết nối hoạt động bình thường.'


@lru_cache(maxsize=1)
def _retriever():
    from ..skill_expansion.catalog import SkillCatalog
    from ..skill_expansion.retrieval import SkillRetriever
    return SkillRetriever(SkillCatalog.load())


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
            latency = f"độ trễ {v['latency_ms']:g} ms" if v['latency_ms'] >= 0 else 'chưa có RTT'
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


def _laptop_topics(text: str) -> dict[str, str]:
    # A compound public-IP topic must not imply an IPv4 address lookup on Wi-Fi.
    address_text = re.sub(r'\b(?:dia chi )?ip (?:cong cong|internet|wan)\b', '', text)
    return {port: title for title, terms, ports in _LAPTOP_TOPICS for port in ports
            if any(_phrase(address_text if port == 'client.ipv4' else text, term) for term in terms)}


def _replay_candidates(request: str, phrases: dict[str, list[str]]) -> tuple[str, list[str]]:
    from ..skill_expansion.retrieval import tokens

    text = normalize(re.sub(r'[,;]', ' va ', request))
    retriever = _retriever()
    design = retriever.catalog.skills
    explicit = [sid for sid in sorted(design) if _phrase(text, sid.lower())]
    if explicit:
        return 'phrase', explicit if len(explicit) == 1 else []
    conjunction = r'\b(?:va|and|cung nhu)\b'
    exact = [sid for sid, skill in design.items() if _phrase(text, normalize(skill.name_vi))]
    if len(exact) == 1 and not re.search(conjunction, text.replace(normalize(design[exact[0]].name_vi), '', 1)):
        return 'phrase', exact
    if len([part for part in re.split(conjunction, text) if part.strip()]) != 1:
        return 'compound', []
    generic = frozenset(
        'trang thai thiet bi cau hinh giam sat kiem theo doi bao cao chan doan danh gia router gateway '
        'phat hien thong tin suc khoe ket noi'.split())
    query = set(tokens(request)) - generic
    rank = {}
    for sid, skill in design.items():
        name = set(tokens(skill.name_vi)) - generic
        phrase = max((len(p.split()) for p in phrases.get(sid, ()) if _phrase(text, p)), default=0)
        overlap = len(query & name)
        if not phrase and not (overlap >= 2 or (overlap and overlap == len(name))):
            continue
        rank[sid] = (max(2 * phrase + 1 if phrase else 0, 2 * overlap), overlap / max(1, len(name)))
    if not rank:
        # No name overlap (e.g. "sức khỏe router": every word is generic). Offer the
        # retriever's nearest Skills; the caller only runs one the local model picks.
        return 'search', [hit.skill_id for hit in retriever.search(request, limit=8, include_proposed=True)]
    best = max(rank.values())
    candidates = {sid for sid, score in rank.items() if score == best}
    hits = retriever.search(request, limit=len(design), include_proposed=True)
    order = {hit.skill_id: index for index, hit in enumerate(hits)}
    return 'phrase' if best[0] % 2 else 'graph', sorted(candidates, key=lambda s: (order.get(s, len(design)), s))[:6]


def _simulation_finding(row: dict) -> str:
    port, v = row['port'], row['value']
    if port == 'expansion.upstream_probe':
        return f"Mất gói tới upstream {v['loss_pct']:g}%."
    if port == 'expansion.dns_resolvers':
        return f"{v['healthy_count']}/{v['resolver_count']} DNS resolver đạt kiểm tra."
    if port == 'expansion.wireless_signal':
        return f"RSSI {v['rssi_dbm']:g} dBm, SNR {v['snr_db']:g} dB."
    if port == 'expansion.vpn_tunnel':
        return 'Tunnel VPN đang hoạt động.' if v['tunnel_up'] else 'Tunnel VPN đang ngắt.'
    if port == 'expansion.temperature':
        return f"Nhiệt độ {v['celsius']:g} °C."
    if port == 'expansion.wan_link':
        return 'Link WAN đang lên.' if v['link_up'] else 'Link WAN đang ngắt.'
    if port in {'expansion.radio_health', 'expansion.ssid_config', 'expansion.airtime_usage'}:
        return findings({'facts': {port: row}})[port]['text']
    return ''


class SkillChat:
    def __init__(self, launcher=LAUNCHER, *, model_factory=local_model, max_rounds=4,
                 max_elapsed_s=120, clock=time.monotonic, fast=False):
        if (type(max_rounds) is not int or not 1 <= max_rounds <= 6
                or type(max_elapsed_s) not in (int,float) or not math.isfinite(max_elapsed_s)
                or not 1 <= max_elapsed_s <= 240 or not callable(clock)):
            raise ValueError('invalid_chat_round_budget')
        self.launcher, self.model_factory, self.max_rounds = launcher, model_factory, max_rounds
        self.max_elapsed_s,self.clock=max_elapsed_s,clock
        # fast: graph/phrase routing (or a symptom baseline) without LLM when
        # possible, otherwise at most one LLM selection call; no goal-proposal or
        # answer-wording calls (CPU Qwen cannot word within evidence TTL).
        if type(fast) is not bool:raise ValueError('invalid_chat_fast_flag')
        self.fast=fast

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
    def _unconfirmed_parts(cls, entry, request, *, scoped=False):
        # A recognized clause cannot prove a different, unrecognized clause answered.
        clauses=re.split(r'\b(?:va|voi|and|also|cung nhu)\b|[,;]',normalize(request))
        if len(clauses)==1:return []
        return [part.strip() for part in clauses if part.strip()
                and not (_laptop_topics(part) if scoped else cls._requested(entry,part))
                and not any(_phrase(part,phrase)
                            for phrases in entry['runtime'].registry.required_skill_phrases.values()
                            for phrase in phrases)]

    def chat(self, request: str, *, session_id=None, mode='live', scenario=None, allow_model=True):
        if type(request) is not str or not 1 <= len(request.strip()) <= 2000:
            raise ValueError('invalid_chat_request')
        if type(mode) is not str or (mode not in _MODE and mode != REPLAY_SIM):
            raise ValueError('invalid_chat_mode')
        if scenario is not None and (mode != REPLAY_SIM or type(scenario) is not str or scenario not in SIM_STATES):
            raise ValueError('invalid_chat_scenario')
        if type(allow_model) is not bool:
            raise ValueError('invalid_chat_model_flag')
        started=self.clock()
        created=session_id is None
        if created:
            options = {'scenario': scenario} if mode == REPLAY_SIM else {}
            session_id = self.launcher.create_session(mode, **options)['session_id']
        entry=self.launcher._get(session_id)
        if entry['mode']!=mode:raise ValueError(f'chat_requires_{mode}_session')
        if mode == REPLAY_SIM and scenario is not None and scenario != entry['session'].scenario:
            raise ValueError('chat_scenario_requires_new_session')
        if mode != REPLAY_SIM and not hasattr(entry['runtime'].registry,'question_intents'):
            if created:self.launcher.close(session_id)
            raise ValueError('chat_diagnostics_not_approved')
        with self.launcher._lock:lock=entry.setdefault('chat_lock',threading.Lock())
        if not lock.acquire(blocking=False):raise SkillSessionError('session_busy')
        if not _MODEL_SLOT.acquire(blocking=False):
            lock.release()
            if created:self.launcher.close(session_id)
            raise SkillSessionError('model_busy')
        try:
            if mode == REPLAY_SIM:
                return self._replay_sim_turn(request.strip(), session_id, entry, started, allow_model=allow_model)
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

    def _replay_sim_turn(self, request: str, sid: str, entry: dict, started: float, *, allow_model: bool) -> dict:
        replay = entry['session']
        deadline = started + self.max_elapsed_s
        catalog = self.launcher.catalog(REPLAY_SIM, entry=entry)
        rows = {row['skill_id']: row for row in catalog['rows']}
        routing = replay.profile.diagnostics['routing']
        text = normalize(request)
        advice, calls, method, result = [], 0, 'none', None
        requested_scopes = {
            scope for scope, names in {
                'client': r'client|laptop|may tinh|dien thoai|phone|tablet|pc',
                'gateway': r'gateway|router|modem',
            }.items() if re.search(r'\b(?:cua|tren|tu|for|on|from) (?:' + names + r')\b', text)}
        # An exact READ catalog title can mention an operation being observed
        # (e.g. reboot history). Preserve the write guard on the rest of the turn.
        title = re.sub(r'^(?:hay |vui long )?(?:kiem tra )?', '', text).removesuffix(' giup toi')
        named_read = any(title == normalize(r['name']) for r in rows.values())
        if not named_read and TaskDecomposer(SimpleNamespace(ports={})).is_write_intent(request):
            reason, status = 'write_intent_requires_approval', 'BLOCKED'
            message = 'Phiên chỉ hỗ trợ thao tác đọc trong mô phỏng.'
        elif (any(_phrase(text, p) for p in routing['nonlocal_scope_phrases'])
              or re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b|(?:[0-9a-f]{0,4}:){2,}[0-9a-f]{0,4}', request, re.I)):
            reason, status = 'custom_target_not_supported', 'NEEDS_INPUT'
            message = 'Phiên dùng client và gateway cố định trong kịch bản mô phỏng.'
        else:
            method, candidates = _replay_candidates(request, routing['phrases'])
            reason, status = 'skill_not_supported', 'UNAVAILABLE'
            message = 'Chủ đề này chưa được hỗ trợ trong danh mục Replay mô phỏng.'
            if method == 'compound':
                reason, status = 'needs_clarification', 'NEEDS_INPUT'
                message = 'Hãy gửi từng phép kiểm tra mô phỏng trong một câu hỏi.'
            elif method == 'search':
                # Retrieval hits are suggestions, not matches: keep approved rows only, never auto-run one.
                candidates = [key for key in candidates if key in rows]
            if method != 'compound' and candidates and set(candidates) <= rows.keys():
                candidates = [key for key in candidates if not requested_scopes
                              or requested_scopes == {rows[key]['runtime_scope']}]
                selected = candidates[0] if len(candidates) == 1 and method != 'search' else None
                remaining = min(deadline - self.clock(), replay.expires_at - replay.clock())
                if (len(candidates) > 1 or method == 'search') and allow_model and remaining > 1:
                    eligible = {key: rows[key] for key in candidates}
                    docs = [[r['skill_id'], r['name'], r['availability'], r['runtime_scope']]
                            for r in eligible.values()]
                    try:
                        model = (self.model_factory(timeout=remaining - 1) if self.model_factory is local_model
                                 else self.model_factory())
                        if getattr(model, 'local_only', None) is not True:
                            raise ValueError('local_skill_model_required')
                        calls += 1
                        raw = model.choose_skills(request, docs, {
                            'scope': 'Approved READ Skills on a fixed synthetic scenario only.',
                            'simulation_only': True, 'inference_timeout_s': remaining - 1,
                            'last_round': False, 'runnable_outputs': {
                                key: list(entry['actions'][key]['required_ports']) for key in eligible}})
                        choice = validate_choice(raw, eligible, {}, ())
                        if len(choice['skill_ids']) == 1:
                            selected = choice['skill_ids'][0]
                            advice.append({'model': getattr(model, 'model', 'local-test'), 'accepted': True,
                                           'selected': selected, 'decision': 'measure',
                                           'catalog_retrieval': getattr(model, 'last_catalog', None)})
                            method = 'model'
                    except (AttributeError, OSError, TypeError, ValueError, RuntimeError):
                        pass
                remaining = min(deadline - self.clock(), replay.expires_at - replay.clock())
                if not candidates:
                    reason, status = 'scope_not_supported', 'NEEDS_INPUT'
                    message = 'Skill phù hợp với chủ đề này dùng phạm vi khác với thiết bị được hỏi.'
                elif remaining <= 0:
                    reason, status, message = 'turn_deadline_exhausted', 'UNAVAILABLE', 'Đã hết thời gian xử lý.'
                elif selected is not None:
                    result = self.launcher.run(sid, selected, deadline=replay.clock() + remaining)
                    reason = 'simulation_data_missing' if result['missing_ports'] else 'simulation_assessed'
                    status = result['status']
                    verdict = {'HEALTHY': 'Bình thường trong phạm vi đã kiểm tra.',
                               'FAULT': 'Có dấu hiệu bất thường trong phép kiểm tra.',
                               'UNKNOWN': 'Chưa đủ bằng chứng để kết luận.'}[result['verdict']]
                    message = f"{rows[selected]['name']} · {verdict}"
                else:
                    reason, status = 'needs_clarification', 'NEEDS_INPUT'
                    message = 'Hãy nêu cụ thể phép kiểm tra cần chạy trong danh mục mô phỏng.'

        result = result or {}
        evidence = result.get('evidence', [])
        measurements = [row for row in evidence if row['port'] != 'client.identity']
        summary = ' '.join(dict.fromkeys(line for row in measurements
                                         if (line := _simulation_finding(row))))
        scope = rows[result['skill_id']]['runtime_scope'] if result else None
        return {'answer': '\n'.join(filter(None, (SIM_NOTICE, message, summary))), 'request': request,
                'mode': REPLAY_SIM, 'synthetic_only': True, 'scenario': replay.scenario,
                'fixture': f'Replay mô phỏng · {replay.scenario}', 'fixture_id': replay.scenario,
                'session_id': sid, 'catalog_total': catalog['design_total'], 'workflow': 'REPLAY-SIM-SKILL-CHAT',
                'action': 'REPORT', 'case_status': status, 'stop_reason': reason, 'policy': 'core', 'method': 'core',
                'diagnosis': None, 'verdict': result.get('verdict', 'UNKNOWN'),
                'assessment': result.get('assessment', {}), 'evidence': evidence,
                'evidence_ids': result.get('evidence_ids', []), 'status_ok_evidence_ids': [r['id'] for r in evidence],
                'calls': result.get('calls_this_run', 0), 'calls_total': replay.calls, 'repairs': 0,
                'timeline': result.get('timeline', []), 'plans': result.get('plans', []),
                'skill_runs': [{k: result[k] for k in ('skill_id', 'status', 'calls_this_run', 'reused_ports',
                                                      'missing_ports')}] if result else [],
                'source_errors': result.get('source_errors', {}),
                'measurement_details': [f"{r['sample']} · {r['port']} · {r['value']}" for r in measurements],
                'claim_details': [result['assessment']['limitation']]
                if 'limitation' in result.get('assessment', {}) else [],
                'target': {'scope': scope, 'selector': {'gateway': 'Gateway mô phỏng',
                                                       'client': 'Client mô phỏng'}.get(scope)},
                'notice': SIM_NOTICE, 'model_calls': calls, 'advice': advice, 'llm_advisor_used': bool(advice),
                'routing': {'method': method, 'plan': [result['skill_id']] if result else []},
                'user_input_required': status == 'NEEDS_INPUT'}

    def _turn(self, request, sid, entry, started):
        runtime,session=entry['runtime'],entry['session']
        normalized=normalize(request)
        live=entry['mode']=='live'
        wan=live and _phrase(normalized,'wan')
        topic_text=re.sub(r'\bwan (?:cua )?(?:router|modem)\b','wan',normalized) if wan else normalized
        topics=_laptop_topics(topic_text) if live else {}
        scoped=bool(topics) and (self.fast or wan)
        diagnostic=diagnostic_request(request) or wan
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
            limit=runtime._clock()+max(0,deadline-self.clock())
            if not scoped:
                return timed('execution',self.launcher.run,sid,skill,deadline=limit)
            return timed('execution',run_scoped_skill,skill,limit)

        def run_scoped_skill(skill: str, limit: float) -> dict:
            # Approved completion/optional ports narrow the goal set. ReadSession
            # compiles mandatory dependencies and executes through the READY kernel.
            ports=[p for p in scoped_outputs().get(skill, ()) if p in goals]
            with entry['lock'], self.launcher._measure_lock:
                runner=session.runner
                before=view(refresh=False)['facts']
                calls=runner.calls
                original_deadline=runner.deadline_s
                runner.deadline_s=min(original_deadline,limit-runner.started)
                try:
                    if ports:
                        session.execute(ports,request='READ scoped laptop measurements')
                except PlanError as exc:
                    if session.closed:raise SkillSessionError('session_expired') from exc
                finally:
                    runner.deadline_s=original_deadline
                snapshot=view()
                facts=snapshot['facts']
                missing=[p for p in ports if p not in facts]
                return {'skill_id':skill, 'snapshot':snapshot, 'missing_ports':missing,
                        'calls_this_run':runner.calls-calls,
                        'reused_ports':[p for p in ports if p in facts and p in before
                                        and facts[p]['evidence_id']==before[p]['evidence_id']],
                        'status':'MEASURED' if ports and not missing else 'PARTIAL'}
        task_trace=[]
        def assess(workflows, *, adaptive=False):
            allowed=set(goals) if goals else set(p for skill in attempted
                    for p in {**entry['actions'][skill]['required_ports'],**entry['actions'][skill]['optional_ports']})
            result=timed('rca',TaskRuntime.run_session,session,request=request,
                         workflows=workflows,allowed_ports=sorted(allowed),
                         diagnostic=adaptive and diagnostic and not scoped,max_steps=2,
                         deadline=runtime._clock()+max(0,deadline-self.clock()))
            task_trace.append({k:result[k] for k in ('mode','status','reason','steps','calls_added')})
            return result['assessments']
        def check_deadline():return self.clock()<deadline and runtime._clock()<session.expires_at
        view()
        prof=_MODE[entry['mode']]
        catalog=timed('catalog',self.launcher.catalog,entry['mode'],entry=entry)
        rows={r['skill_id']:r for r in catalog['rows']}
        docs=[[r['skill_id'],r['name'],r['availability'],r['runtime_scope']] for r in catalog['rows']]
        goals=topics.copy() if scoped else self._requested(entry,request)
        unconfirmed=self._unconfirmed_parts(entry,topic_text,scoped=scoped)
        unavailable=[skill for skill,phrases in runtime.registry.required_skill_phrases.items()
                     if rows[skill]['availability']=='UNAVAILABLE' and any(_phrase(normalized,p) for p in phrases)]
        # The model only sees what can run now; phrase rules (not the model)
        # decide which unavailable Skills to report.
        model_docs=[d for d in docs if rows[d[0]]['availability'] in {'READY','DEGRADED'} or d[0] in unavailable]
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
            outputs=scoped_outputs() if scoped else {
                skill:list(a['required_ports'])+list(a['optional_ports']) for skill,a in entry['actions'].items()}
            for port in ports:
                if not any(f.id in supported and port in f.outputs for f in runtime.registry.functions.values()):
                    continue
                options=[(len(ports),skill) for skill,ports in outputs.items() if port in ports]
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
        scope_text=topic_text if wan and set(topics)=={'laptop.internet_probe'} else normalized
        local_gateway=scoped and set(topics)=={'laptop.gateway_probe','laptop.route'} and not unavailable
        nonlocal_phrases=runtime.registry.nonlocal_scope_phrases
        if live:
            nonlocal_phrases=(*nonlocal_phrases,'modem','cua modem','tren modem','on modem')
        custom_target=bool(re.search(r'\b(?:\d{1,3}\.){3}\d{1,3}\b|(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}',request)) or any(
            _phrase(scope_text,p) for p in nonlocal_phrases
            if not local_gateway or p not in {'router','modem'})
        def runnable_outputs():
            supported={f.function_id for f in entry['capabilities'].functions if f.status=='AVAILABLE'}
            producible={port for f in runtime.registry.functions.values() if f.id in supported for port in f.outputs}
            return {skill:[p for p in {**a['required_ports'],**a['optional_ports']} if p in producible]
                    for skill,a in entry['actions'].items() if rows[skill]['availability'] in {'READY','DEGRADED'}}

        def scoped_outputs() -> dict[str, list[str]]:
            outputs=runnable_outputs()
            # Registry READ skills may expose an approved port without a launcher
            # action of their own (the internal Internet probe is one).
            available={cap.function_id for cap in entry['capabilities'].functions if cap.status=='AVAILABLE'}
            for skill, meta in runtime.registry.skills.items():
                if skill in outputs or not meta['completion_ports']:continue
                ports={p for f in runtime.registry.functions.values() if f.id in available and skill in f.skills
                       for p in f.outputs}
                eligible=sorted(ports.intersection(meta['completion_ports'],goals))
                if eligible:outputs[skill]=eligible
            return outputs

        def direct_route():
            """Deterministic plan from phrase intents or graph retrieval; None if ambiguous."""
            if unconfirmed or unavailable:return None
            outputs=scoped_outputs() if scoped else runnable_outputs()
            if not goals:
                if diagnostic:
                    # Vague symptom ("chậm", "do đâu"): measure every question-intent
                    # port a runnable action can produce, before any model call.
                    producible={p for ports in outputs.values() for p in ports}
                    baseline={p for meta in runtime.registry.question_intents.values()
                              for p in meta['ports'] if p in producible}
                    if not baseline:return None
                    goals.update({p:p for p in sorted(baseline)})
                    route_meta['method']='symptom_baseline'
                else:
                    # A catalog hit can rank an approved action, never grant execution.
                    hits=_retriever().search(request,limit=3,include_proposed=True,graph_weight=.30)
                    top=hits[0].skill_id if hits else None
                    if top not in outputs or not outputs[top]:return None
                    goals.update({p:p for p in entry['actions'][top]['required_ports'] if p in outputs[top]})
                    route_meta['method']='graph'
            need=set(goals)-set(view(refresh=False)['facts'])
            plan=[]
            while need:
                best=max(((len(need&set(ports)),-len(ports),skill) for skill,ports in outputs.items()
                          if skill not in plan),default=(0,0,None))
                if best[0]==0:return plan if scoped else None
                plan.append(best[2]);need-=set(outputs[best[2]])
            return plan
        route_meta={'method':'phrase','plan':None}
        direct_plan=None
        if blocked:reason='write_intent_requires_approval'
        elif custom_target:reason='custom_target_not_supported'
        elif not check_deadline():reason='turn_deadline_exhausted'
        elif (self.fast or wan) and (direct_plan:=direct_route()) is not None:
            route_meta['plan']=list(direct_plan)
            for skill in direct_plan:
                if not check_deadline():reason='turn_deadline_exhausted';break
                attempted.append(skill);runs.append(run_skill(skill))
            else:
                if scoped:
                    workflows=list(runtime.registry.workflows)
                    if workflows:assessments=assess(workflows)
                elif attempted:
                    workflows=list(dict.fromkeys(w for skill in attempted for w in runtime.registry.skill_workflows.get(skill,[])))
                    if workflows:assessments=assess(workflows,adaptive=True)
                selected=[p for p in goals if p in view(refresh=False)['facts']]
                reason='direct_route' if selected else 'read_execution_unavailable' if scoped else 'needs_clarification'
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
                if not scoped and not self.fast and (not goals or unconfirmed) and callable(getattr(model,'propose_goals',None)):
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
                        raw=timed('inference',model.choose_skills,request,model_docs,context)
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
                    if round_index==self.max_rounds-1 and not self.fast:reason='round_budget_exhausted';break
                    for skill in choice['skill_ids']:
                        if not check_deadline():reason='turn_deadline_exhausted';break
                        result=run_skill(skill)
                        attempted.append(skill);runs.append(result)
                    workflows=list(dict.fromkeys(w for skill in attempted for w in runtime.registry.skill_workflows[skill]))
                    assessments=assess(workflows,adaptive=True)
                    feedback={'failed_skills':[r['skill_id'] for r in runs if r['status']!='MEASURED'],
                              'missing_goals':coverage(view(refresh=False)['facts'])['missing_ports']}
                    if session.runner.calls>=session.runner.max_calls:reason='tool_budget_exhausted';break
                    if self.fast:
                        facts=view(refresh=False)['facts']
                        selected=[p for p in facts if not goals or p in goals]
                        reason='model_answer' if selected else 'needs_clarification'
                        break
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
        if (reason=='model_answer' and not self.fast and not diagnostic and check_deadline()
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
            if not cov['complete'] and reason in {'model_answer','direct_route'}:reason='incomplete_coverage' if goals else 'intent_scope_unconfirmed'
            chosen={p:final['facts'][p] for p in selected}
            main_ports=selected
            if diagnostic and live and not topics:
                main_ports=[p for p in ('laptop.wifi','laptop.gateway_probe','laptop.internet_probe','laptop.dns','laptop.route')
                            if p in chosen and (p!='laptop.route' or 'laptop.gateway_probe' not in chosen)]
            answer=compose_answer(request,main_ports,final['facts'],current,compact=diagnostic or scoped)
            if draft:
                final_proofs={p:final['facts'][p]['evidence_id'] for p in selected}
                if (draft_proofs==final_proofs and check_deadline()
                        and set(draft.evidence_ids)=={f['evidence_id'] for f in chosen.values()}):
                    answer=draft.answer
                else:
                    synthesis.update(used_llm=False,reason='evidence_changed_or_deadline')
            limitations=[f"{rows[s]['name']}: chưa chạy được {prof['where']} ({rows[s]['reason']})." for s in unavailable]
            if cov['missing_ports'] and not blocked and not custom_target:
                limitations.append('Chưa xác minh: '+', '.join(dict.fromkeys(goals[p] for p in cov['missing_ports']))+'.')
            if unconfirmed and not blocked and not custom_target:
                limitations.append(prof['unconfirmed'])
            caveats=[]
            claim_details=[]
            measurement_details=[]
            if blocked:
                status='BLOCKED';answer='Ứng dụng chỉ đọc; không tự thay đổi cấu hình hoặc khởi động lại thiết bị.'
            elif custom_target:
                status='NEEDS_INPUT';answer=prof['custom']
            elif not chosen:
                status='UNAVAILABLE' if unavailable else 'NEEDS_INPUT'
                answer='\n'.join(limitations)
                if reason=='turn_deadline_exhausted':answer+='\nĐã hết thời gian xử lý; số đo trước đó không còn hiệu lực để kết luận hiện tại.'
                elif reason in {'model_timeout','finalization_budget_reserved'}:answer+='\nLLM chưa hoàn tất trong thời gian cho phép; chưa có số đo còn hiệu lực để kết luận.'
                elif reason=='read_execution_unavailable':answer+='\nChưa có số đo từ laptop cho chủ đề này.'
                elif not ready:answer+='\nKhông kết nối được LLM local; hãy kiểm tra dịch vụ Ollama.'
                elif runs:answer+='\nChưa có evidence còn hiệu lực sau lúc suy luận; hãy đo lại.'
                elif not answer.strip():answer=prof['empty']
            else:
                status='MEASURED' if cov['complete'] and reason in {'model_answer','direct_route'} else 'PARTIAL'
                wifi=final['facts'].get('laptop.wifi',{}).get('value',{})
                route=final['facts'].get('laptop.route',{}).get('value',{})
                if diagnostic and 'laptop.wifi' in chosen and wifi and route.get('has_route') and route['interface']!=wifi['interface']:
                    caveats.append(f"Đường đo mạng qua {route['interface']}, khác Wi-Fi {wifi['interface']}; chưa chứng minh Internet qua Wi-Fi.")
                if reason not in {'model_answer','direct_route'}:
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
                    limitations.append(messages.get(reason,'Chưa đủ bằng chứng để kết thúc yêu cầu')+'.')
                if diagnostic:
                    assessment=assessment_summary(chosen,assessments)
                    head, *claim_details=assessment.splitlines() or ['']
                    if not head:
                        head='Chưa đủ bằng chứng để đánh giá tình trạng trong phạm vi đã đo.'
                    elif head.startswith('Có dấu hiệu bất thường') and not wan:
                        head+=' Chưa xác định được nguyên nhân.'
                    if status=='PARTIAL':
                        head+=' Kết quả mới bao phủ một phần yêu cầu.'
                    lines=answer.splitlines()
                    budget=3 if wan else 4
                    answer='\n'.join([f"{prof['origin']}: {head}",*lines[:budget]])
                    measurement_details=lines[budget:]
                    if any(p in chosen for p in ('laptop.internet_probe','laptop.dns')):
                        caveats.append('ICMP/DNS phản hồi chưa chứng minh truy cập web hoặc nguyên nhân gốc.')
                    caveats.extend([_DIAGNOSTIC_LIMIT,
                        'Bước tiếp theo: xác định thiết bị/ứng dụng bị ảnh hưởng và kiểm tra đúng lúc gặp lỗi; chưa có cơ sở chọn thay đổi cấu hình cụ thể.',
                        *limitations])
                elif limitations:
                    answer='\n'.join([answer,*limitations])
            if wan and not blocked:
                answer=_WAN_SCOPE+'\n'+answer.strip()
            lines=answer.strip().splitlines()
            if len(lines)>5:
                answer='\n'.join(lines[:5])
                measurement_details.extend(lines[5:])
            if scoped:
                # Mixed-workflow verdicts can incorporate facts cached by another
                # turn. Keep only fully in-scope verdicts in the trace.
                claims=runtime.registry.claim_book.claims
                assessments=[a for a in assessments if all(
                    req.port in goals for row in a['claim_results']
                    for req in (*claims[row['claim_id']].requires,*claims[row['claim_id']].excludes))]
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
            return {'answer':answer.strip(),'caveats':caveats,'claim_details':claim_details,
                    'measurement_details':measurement_details,'request':request,'mode':prof['mode'],'fixture':prof['fixture'],
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
                    'routing':{'fast':self.fast,'direct':direct_plan is not None,**route_meta},
                    'answer_synthesis':synthesis,
                    'answer_kind':'diagnostic' if diagnostic else 'lookup',
                    'user_input_required':reason=='needs_clarification' and not bool(runs),
                    'diagnostic_status':'INCONCLUSIVE' if diagnostic else None,
                    'catalog_total':catalog['design_total'],'llm_advisor_requested':True,'llm_advisor_ready':ready,
                    'llm_advisor_used':bool(advice),'warnings':[],
                    'notice':prof['notice']}


# Trusted startup env only. Default fast: graph/phrase routing, <=1 LLM call.
CHAT=SkillChat(max_elapsed_s=240,
               fast=os.environ.get('GATEWAY_LM_CHAT_FAST','1').lower() not in {'0','off','false','no'})
