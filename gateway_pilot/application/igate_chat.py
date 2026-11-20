"""iGate replay chat routes. Device and router facts come from verified READs."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from ..skill_expansion.igate_data import function_id
from ..skill_expansion.igate_snapshot import APPLICATIONS, device_name
from ..skill_expansion.replay_sim import MODE, NOTICE
from . import igate_proposal
from .claim_guidance import next_steps_text, single_result_guidance
from .igate_knowledge import knowledge
from .igate_proposal import APP, Proposal, fold, parse_proposal, resolve_device
from .replay_sim_run import current_replay_result


@dataclass(frozen=True)
class ReadQuestion:
    skill: str
    focus: str = ''
    selector: str | None = None
    instant: bool = False


QUICK = (
    (r'(?:co )?bao nhieu thiet bi(?: dang)? (?:online|ket noi)|so thiet bi (?:online|dang ket noi)|'
     r'how many (?:devices|clients) (?:are )?(?:online|connected)(?: right now)?', 'IG01', 'count'),
    (r'(?:cpu(?:[,/ ]+ram)?(?:[,/ ]+(?:va )?nhiet do)?|ram)(?: (?:cua )?router)?(?: bao nhieu)?|'
     r'nhiet do(?: (?:cua )?router)?|nhiet do bao nhieu|'
     r'router (?:cpu|ram|temperature)|cpu (?:usage|load)|ram usage', 'IG03', 'system'),
    (r'(?:ping|do tre)(?: (?:internet|wan|router))?(?: bao nhieu)?|what is (?:the )?(?:wan )?ping', 'IG03', 'ping'),
    (r'(?:router )?(?:co|mat) internet khong|internet (?:co khong|dang hoat dong khong)|'
     r'is (?:the )?internet (?:up|online|working)|do we have internet', 'IG03', 'internet'),
    (r'wifi khach (?:dang )?(?:bat|mo)(?: hay tat)? khong|wifi khach (?:bat hay tat|dang bat hay tat)|'
     r'is guest wifi (?:on|enabled|off)', 'IG03', 'guest'),
    (r'ai (?:dang )?choi game|who(?: is|\'s) gaming', 'IG04', 'GAMING'),
)

READS = (
    (r'(?:ai|thiet bi nao) (?:dang )?(?:online|ket noi)|(?:danh sach|liet ke) (?:cac )?'
     r'thiet bi(?: dang)? (?:online|ket noi)|who(?: is|\'s) online|list online (?:devices|clients)', 'IG01', 'list'),
    (r'(?:kiem tra )?(?:suc khoe|trang thai|chi so) router igate|kiem tra suc khoe router|'
     r'router (?:telemetry|status)|how (?:is|healthy is) (?:the )?router', 'IG03', 'system'),
    (r'(?:kiem tra )?chat luong (?:ket noi|mang)(?: (?:cua )?router)?|(?:check )?connection quality',
     'IG03', 'connection'),
    (r'(?:xem )?(?:ket qua (?:do toc do|speedtest|speed test)|speedtest (?:gan nhat|da co))|'
     r'(?:show )?(?:last|latest) (?:speedtest|speed test)(?: result)?', 'IG03', 'speedtest'),
    (r'(?:danh sach|liet ke|xem) lich(?: da dat)?|list schedules|show schedules', 'IG05', ''),
)
NAMED = (
    (r'(?:tim(?: thiet bi)?|chi tiet(?: thiet bi)?|thong tin(?: thiet bi)?|find(?: device)?|'
     r'(?:show )?(?:device details|details (?:for|of))) (?:cua |cho )?(.+)', 'IG01'),
    (r'(?:kiem tra )?(?:tin hieu(?: va toc do)?|toc do|rssi|snr|song wifi|signal(?: and speed)?|speed)'
     r' (?:(?:cua|cho|for|of|on) (?:thiet bi |device )?|(?:thiet bi|device) )(.+)', 'IG02'),
)

APP_NAMES = {'GAMING': 'chơi game', 'VSTREAM': 'xem video', 'VOICE': 'gọi thoại', 'VIDEOCALL': 'gọi video'}
METRIC_LABELS = {
    'cpu_pct': ('CPU', '%'), 'mem_pct': ('RAM', '%'), 'temp_c': ('Nhiệt độ', ' °C'),
    'ping_ms': ('Ping', ' ms'), 'link_mbps': ('Tốc độ liên kết', ' Mbps'),
    'rx_mbps': ('Nhận', ' Mbps'), 'tx_mbps': ('Gửi', ' Mbps'),
    'rssi_dbm': ('RSSI', ' dBm'), 'snr_db': ('SNR', ' dB'),
    'dl_mbps': ('Tải xuống', ' Mbps'), 'ul_mbps': ('Tải lên', ' Mbps'), 'jitter_ms': ('Jitter', ' ms'),
}

CLARIFY = ('Hãy cho biết tên thiết bị khớp duy nhất trong danh sách mô phỏng hoặc MAC của thiết bị.')
UNKNOWN = 'Không biết từ snapshot mô phỏng.'


def route(request: str, vendor: dict[str, bytes]) -> ReadQuestion | Proposal | str | dict | None:
    text = re.sub(r'\bwi[ -]fi\b', 'wifi', fold(request))
    text = re.sub(r'^(?:hay |vui long |please |cho toi biet )', '', text)
    if re.search(r'\b(?:mat khau wifi|wifi password)\b', text) and not re.search(r'\b(?:cach|how to)\b', text):
        return 'Mật khẩu Wi-Fi được giữ kín.'
    if re.search(r'[;\n]|[<>]', request):
        return None
    for patterns, instant in ((QUICK, True), (READS, False)):
        for pattern, sid, focus in patterns:
            if re.fullmatch(pattern, text):
                return ReadQuestion(sid, focus, instant=instant)
    if re.fullmatch(r'(?:kiem tra )?ig0[1-5]', text):
        sid = text[-4:].upper()
        return ReadQuestion(sid, {'IG01': 'list', 'IG03': 'all'}.get(sid, ''))
    if re.fullmatch(r'(?:ai|thiet bi nao) (?:dang )?goi|who(?: is|\'s) calling', text):
        return ReadQuestion('IG04', 'calls')
    if match := re.fullmatch(rf'(?:ai|thiet bi nao|who is|who\'s) (?:dang )?({APP})', text):
        return ReadQuestion('IG04', igate_proposal._app(match[1]))
    for pattern, sid in NAMED:
        if match := re.fullmatch(pattern, text):
            return ReadQuestion(sid, selector=match[1])
    if re.fullmatch(r'(?:chay|bat dau|run|start) (?:speedtest|speed test|do toc do)(?: ngay| now)?', text):
        return 'Replay chỉ đọc kết quả speedtest đã lưu trong snapshot mô phỏng.'
    # Accent folding conflates "chẩn đoán" with the command verb "chặn".
    if re.match(r'^(?:chan doan|co nen|why|what happens|how|cach)\b', text):
        return knowledge(text, vendor)
    proposal = parse_proposal(text)
    return proposal if proposal is not None else knowledge(text, vendor)


def _device(values: dict, question: ReadQuestion) -> tuple[str, str]:
    if question.focus == 'count':
        count = values.get('online_count')
        return (f'Có {count} thiết bị đang online.' if count is not None else UNKNOWN,
                'MEASURED' if count is not None else 'UNAVAILABLE')
    if question.focus == 'list':
        clients = values.get('clients')
        if clients is None:
            return UNKNOWN, 'UNAVAILABLE'
        names = ', '.join(device_name(row) for row in clients)
        if values.get('complete') is not True:
            return (f'Thiết bị thấy trong snapshot: {names}. Danh sách chưa đầy đủ.' if names else UNKNOWN,
                    'PARTIAL' if names else 'UNAVAILABLE')
        return (f'Thiết bị đang online: {names}.' if names else 'Không có thiết bị online.'), 'MEASURED'
    if question.selector is None and question.skill == 'IG02':
        if not (clients := values.get('clients')):
            return UNKNOWN, 'UNAVAILABLE'
        lines = [f'{device_name(client)}: {metrics}' for client in clients
                 if (metrics := _metrics(client, ('rssi_dbm', 'snr_db', 'link_mbps', 'rx_mbps', 'tx_mbps')))]
        if lines:
            return '\n'.join(lines), 'MEASURED' if values.get('complete') else 'PARTIAL'
        return UNKNOWN, 'UNAVAILABLE'
    row = resolve_device(values, question.selector or '')
    if row is None:
        return CLARIFY, 'NEEDS_INPUT'
    name = device_name(row)
    if question.skill == 'IG02':
        fields = ('rssi_dbm', 'snr_db', 'link_mbps', 'rx_mbps', 'tx_mbps')
        metrics = _metrics(row, fields, show_missing=True) if any(field in row for field in fields) else ''
        return (f'{name} ({row["mac"]}): {metrics}.' if metrics else f'{name}: {UNKNOWN}',
                'MEASURED' if all(field in row for field in fields) else 'PARTIAL' if metrics else 'UNAVAILABLE')
    details = ', '.join(filter(None, (row.get('ip'), row.get('band'))))
    return (f'{name} đang online. MAC {row["mac"]}' + (f', {details}.' if details else '.'), 'MEASURED')


def _metrics(row: dict, fields: tuple[str, ...], *, show_missing=False) -> str:
    return ', '.join(f'{key}: {row[field]:g}{unit}' if field in row else f'{key}: không biết'
                     for field in fields if field in row or show_missing
                     for key, unit in (METRIC_LABELS[field],))


def _router(values: dict, question: ReadQuestion) -> tuple[str, str]:
    focus = question.focus
    if focus == 'guest':
        state = values.get('guest_enabled')
        return ('Wi-Fi khách đang bật.' if state else 'Wi-Fi khách đang tắt.') if state is not None else UNKNOWN, (
            'MEASURED' if state is not None else 'UNAVAILABLE')
    if focus == 'internet':
        state = values.get('internet')
        return ('Router có Internet.' if state else 'Router mất kết nối Internet.') if state is not None else UNKNOWN, (
            'MEASURED' if state is not None else 'UNAVAILABLE')
    fields = {'system': ('cpu_pct', 'mem_pct', 'temp_c'), 'ping': ('ping_ms',),
              'connection': ('ping_ms', 'rx_mbps', 'tx_mbps', 'link_mbps'),
              'all': ('cpu_pct', 'mem_pct', 'temp_c', 'ping_ms', 'rx_mbps', 'tx_mbps', 'link_mbps')}.get(focus, ())
    count = sum(field in values for field in fields)
    lines = [_metrics(values, fields, show_missing=focus == 'system') + '.'] if count else []
    if focus in ('connection', 'all') and 'internet' in values:
        lines.append('Router có Internet.' if values['internet'] else 'Router mất kết nối Internet.')
    if focus in ('speedtest', 'all'):
        if row := values.get('speedtest'):
            if not row['ok']:
                lines.append(f'Lần speedtest lưu lúc {row["last_ts"]} thất bại.')
            else:
                metrics = _metrics(row, ('dl_mbps', 'ul_mbps', 'ping_ms', 'jitter_ms'))
                lines.append(f'Speedtest lưu lúc {row["last_ts"]}: {metrics}.' if metrics else
                             f'Speedtest lưu lúc {row["last_ts"]}; không biết các chỉ số.')
        else:
            lines.append('Không biết kết quả speedtest đã lưu.')
    status = ('MEASURED' if count == len(fields) else 'PARTIAL') if lines else 'UNAVAILABLE'
    if focus == 'speedtest' and 'speedtest' not in values:
        status = 'UNAVAILABLE'
    return ' '.join(lines) if lines else UNKNOWN, status


def _traffic(values: dict, focus: str) -> tuple[str, str]:
    if values.get('qos_available') is not True or 'sessions' not in values:
        return 'Không biết ai đang sử dụng ứng dụng. Snapshot chưa có dữ liệu phân loại QoS dùng được.', 'UNAVAILABLE'
    classes = ('VOICE', 'VIDEOCALL') if focus == 'calls' else (focus,) if focus else APPLICATIONS
    matches = [row for row in values['sessions'] if row['class'] in classes]
    complete = values.get('sessions_complete') is True
    if not matches:
        if not complete:
            return UNKNOWN, 'UNAVAILABLE'
        activity = APP_NAMES[focus] if focus in APP_NAMES else 'gọi' if focus == 'calls' else 'sử dụng ứng dụng được theo dõi'
        return f'Feed QoS đang hoạt động và không ghi nhận thiết bị {activity}.', 'MEASURED'
    lines = list(dict.fromkeys(f'{row["name"]}: {APP_NAMES[row["class"]]}' for row in matches))
    if not complete:
        lines.append('Dữ liệu phiên chưa đầy đủ.')
    return '; '.join(lines), 'MEASURED' if complete else 'PARTIAL'


def _schedules(values: dict) -> tuple[str, str]:
    if 'total' not in values and not values.get('devices'):
        return UNKNOWN, 'UNAVAILABLE'
    if values.get('total') == 0:
        return 'Snapshot ghi nhận 0 lịch.', 'MEASURED'
    lines = ', '.join(f'{device_name(row)}: {row["count"]} lịch' for row in values['devices'] if row['count'])
    suffix = ' Snapshot chỉ cung cấp số lịch theo thiết bị.'
    if 'total' not in values:
        return (f'{lines}. Danh sách chưa đầy đủ.' if lines else UNKNOWN) + suffix, 'PARTIAL'
    return f'Có {values["total"]} lịch. {lines}.' + suffix, 'MEASURED'


def _render(question: ReadQuestion, values: dict) -> tuple[str, str]:
    if question.skill in ('IG01', 'IG02'):
        return _device(values, question)
    if question.skill == 'IG03':
        return _router(values, question)
    if question.skill == 'IG04':
        return _traffic(values, question.focus)
    return _schedules(values)


def answer(route_result: ReadQuestion | Proposal | str | dict, launcher, sid: str, entry: dict,
           *, started: float, clock, max_elapsed_s: float) -> dict:
    replay = entry['session']
    read_id = (route_result.skill if isinstance(route_result, ReadQuestion) else 'IG01'
               if isinstance(route_result, Proposal) and route_result.device else None)
    execution_started = clock()
    measured = {}
    if read_id is not None:
        remaining = max(0., started + max_elapsed_s - clock())
        measured = launcher.run(sid, read_id, deadline=replay.clock() + remaining)
        measured = current_replay_result(replay, measured, replay.clock())
    elapsed_ms = (clock() - execution_started) * 1000
    evidence = measured.get('evidence', [])
    values = next((row['value'] for row in evidence if row['port'] == function_id(read_id)), {}) if read_id else {}
    details = {}
    if isinstance(route_result, ReadQuestion):
        message, status = _render(route_result, values)
        kind = 'instant' if route_result.instant else 'evidence' if evidence else None
        reason = ('igate_measured' if status == 'MEASURED' else 'igate_needs_device' if status == 'NEEDS_INPUT'
                  else 'igate_data_unknown')
        method = 'igate_quick' if route_result.instant else 'igate_read'
    elif isinstance(route_result, Proposal):
        row = resolve_device(values, route_result.device) if route_result.device else None
        sequence = entry.get('igate_proposal_sequence', 0) + 1
        schema = json.loads(replay.profile.igate_vendor['contracts/firmware-command-v1.schema.json'])
        envelope = route_result.envelope(sequence, schema, row['mac'] if row else None)
        kind, method = None, 'igate_proposal'
        reason, status = 'igate_command_needs_input', 'NEEDS_INPUT'
        if envelope is None:
            message = CLARIFY if route_result.device and not row else 'Hãy xác nhận giá trị trong giới hạn hợp đồng firmware.'
        else:
            entry['igate_proposal_sequence'] = sequence
            kind, reason, status = 'proposal', 'igate_proposal_created', 'PROPOSED'
            message = igate_proposal.NOTICE
            details['command_proposal'] = {'skill': route_result.skill, 'envelope': envelope, 'executed': False,
                                           'impact': igate_proposal.impact(route_result, device_name(row) if row else '')}
            message += '\n' + details['command_proposal']['impact']
    elif isinstance(route_result, dict):
        kind, reason, status = route_result['kind'], 'igate_knowledge', 'ANSWERED'
        message, method = route_result['answer'], route_result['method']
        details['knowledge'] = route_result['knowledge']
        message = 'kiến thức (draft)\n' + message
    else:
        kind, reason, status, method = None, 'igate_clarify', 'NEEDS_INPUT', 'igate_clarify'
        message = route_result
    assessment = measured.get('assessment', {})
    proofs = list(dict.fromkeys(eid for c in assessment.get('claims', {}).values()
                                if c['value'] == 'TRUE' for eid in c['evidence']))
    if isinstance(route_result, ReadQuestion):
        claim_lines, next_steps = single_result_guidance(replay, measured)
        message = '\n'.join([message, *claim_lines, next_steps_text(next_steps)])
        details['next_steps'] = next_steps
    return {
        'answer': f'{NOTICE}\n{message}', 'answer_kind': kind, 'mode': MODE, 'synthetic_only': True,
        'scenario': replay.scenario, 'fixture': f'Replay mô phỏng · {replay.scenario}', 'fixture_id': replay.scenario,
        'session_id': sid, 'catalog_total': len(replay.profile.actions), 'workflow': 'REPLAY-SIM-SKILL-CHAT',
        'action': 'REPORT', 'case_status': status, 'stop_reason': reason, 'policy': 'core', 'method': 'core',
        'diagnosis': None, 'verdict': measured.get('verdict', 'UNKNOWN'), 'assessment': assessment,
        'evidence': evidence, 'evidence_ids': proofs, 'status_ok_evidence_ids': [row['id'] for row in evidence],
        'calls': measured.get('calls_this_run', 0), 'calls_total': replay.calls, 'repairs': 0,
        'timeline': measured.get('timeline', []), 'plans': measured.get('plans', []),
        'skill_runs': [{key: measured[key] for key in ('skill_id', 'status', 'calls_this_run', 'reused_ports',
                                                       'missing_ports')}] if measured else [],
        'source_errors': measured.get('source_errors', {}), 'notice': NOTICE, 'model_calls': 0,
        'advice': [], 'llm_advisor_used': False, 'routing': {'method': method, 'plan': [read_id] if read_id else []},
        'user_input_required': status == 'NEEDS_INPUT', 'timings_ms': {
            'execution': round(elapsed_ms, 3) if read_id else 0, 'total': round((clock() - started) * 1000, 3)},
        **details,
    }
