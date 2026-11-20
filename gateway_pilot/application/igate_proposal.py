"""Translate a bounded iGate request to a display-only firmware envelope."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from jsonschema import Draft202012Validator

from ..skill_expansion.igate_snapshot import MAC
from ..workflow import normalize

NOTICE = 'Đề xuất — chưa thực hiện; hãy áp dụng trên giao diện router'
APPS = {
    'GAMING': r'choi game|game|gaming',
    'VSTREAM': r'xem video|xem phim|video|streaming|vstream',
    'VOICE': r'goi thoai|thoai|voice(?: call)?',
    'VIDEOCALL': r'goi video|video call|videocall',
}
APP = '(?:' + '|'.join(APPS.values()) + ')'
DEVICE_PREFIX = r'(?:(?:mang|internet|thiet bi|device) )?(?:(?:cua|cho|tren|for|on) )?'
APP_LINK = r'(?:cua|cho|tren|for|on) '
RESUME = r'(?:bo chan|mo chan|mo lai|khoi phuc|unblock|resume|restore)'
BLOCK = r'(?:chan|block)'
MINUTES = r'([0-9]{1,5}) (?:phut|minutes?)'
DURATION = rf'(?:trong|for) {MINUTES}'
DELAY = rf'(?:sau|in|after) {MINUTES}'
TIME = r'(\d{2}:\d{2})'
ANCHORS = {'hom nay': ('day', 'today'), 'today': ('day', 'today'),
           'ngay mai': ('day', 'tomorrow'), 'tomorrow': ('day', 'tomorrow'),
           'moi ngay': ('recurrence', 'daily'), 'daily': ('recurrence', 'daily'),
           'ngay trong tuan': ('recurrence', 'weekdays'), 'weekdays': ('recurrence', 'weekdays'),
           'cuoi tuan': ('recurrence', 'weekends'), 'weekends': ('recurrence', 'weekends')}
ANCHOR = '(' + '|'.join(ANCHORS) + ')'


@dataclass(frozen=True)
class Proposal:
    skill: str
    command: str
    arguments: dict = field(default_factory=dict)
    device: str | None = None
    target_type: str = 'device'

    def envelope(self, request_id: int, schema: dict, mac: str | None = None) -> dict | None:
        target = {'type': self.target_type}
        if self.target_type == 'device':
            if not isinstance(mac, str) or not re.fullmatch(MAC, mac):
                return None
            target['selector'] = mac
        scheduled = 'schedule' in self.arguments or self.command == 'cancel_schedule'
        result = {'schema_version': '1.1' if scheduled else '1.0', 'request_id': request_id,
                  'command': self.command, 'target': target, 'arguments': self.arguments}
        return result if Draft202012Validator(schema).is_valid(result) else None


def fold(text: str) -> str:
    text = unicodedata.normalize('NFKD', text.casefold().replace('đ', 'd'))
    return ' '.join(''.join(c for c in text if not unicodedata.combining(c)).strip(' ?!.').split())


def resolve_device(values: dict, selector: str) -> dict | None:
    selector = selector.strip().strip('"\'')
    mac = selector.replace('-', ':')
    by_mac = bool(re.fullmatch(MAC, mac))
    if not by_mac and values.get('complete') is not True:
        return None
    normal = normalize(selector.replace('_', ' '))
    matches = [row for row in values.get('clients', ())
               if re.fullmatch(MAC, row['mac']) and (
                   row['mac'] == mac if by_mac else normal and
                   any(normalize(row.get(field, '')) == normal for field in ('name', 'label')))]
    return matches[0] if len(matches) == 1 else None


def _app(text: str) -> str:
    return next(key for key, pattern in APPS.items() if re.fullmatch(pattern, text))


def _schedule(text: str) -> tuple[str, dict] | None:
    if match := re.fullmatch(rf'(.+?) {DELAY}(?: {DURATION})?', text):
        device, delay, duration = match.groups()
        return device, {'after_minutes': int(delay)} | ({'duration_minutes': int(duration)} if duration else {})
    if match := re.fullmatch(rf'(.+?) {DURATION}', text):
        device, duration = match.groups()
        return device, {'duration_minutes': int(duration)}
    if match := re.fullmatch(rf'(.+?) (?:tu|from|at) {TIME}(?: (?:den|to) {TIME}| {DURATION})? {ANCHOR}', text):
        device, start, end, duration, anchor = match.groups()
        key, value = ANCHORS[anchor]
        if end is None and duration is None:
            return None
        window = {'end_time': end} if end else {'duration_minutes': int(duration)}
        return device, {'start_time': start, key: value, **window}
    return None


DIRECTION = r'tai xuong|download|xuong|tai len|upload|len'
RATE = rf'(?:({DIRECTION}) (\d{{1,5}}) mbps|(\d{{1,5}}) mbps ({DIRECTION}))'


def _rate(text: str) -> Proposal | str:
    if match := re.fullmatch(rf'(.+?) (?:to )?{RATE}(?: (?:va |and )?{RATE})?', text):
        device, *values = match.groups()
        args: dict[str, int] = {}
        for i in (0, 4):
            first, amount1, amount2, last = values[i:i + 4]
            if (direction := first or last) is not None:
                key = 'upload_limit_mbps' if direction in ('tai len', 'upload', 'len') else 'download_limit_mbps'
                if key in args:
                    break
                args[key] = int(amount1 or amount2)
        else:
            return Proposal('qos.rate_limit', 'limit', args, device)
    return 'Hãy cho biết tên thiết bị, chiều tải lên hoặc xuống và số Mbps nguyên.'


def parse_proposal(text: str) -> Proposal | str | None:
    """Return a display proposal, a clarification, or no iGate write match."""
    if re.fullmatch(r'(?:bat|tat|enable|disable|turn (?:on|off)) (?:wifi khach|guest wifi)', text):
        enabled = text.startswith(('bat ', 'enable ', 'turn on '))
        return Proposal('network.guest_wifi', 'set_guest_wifi', {'enabled': enabled}, target_type='gateway')
    if re.match(r'^(?:huy lich|cancel schedule)\b', text):
        if match := re.fullmatch(r'(?:huy lich|cancel schedule)(?: so| id| #)? ([0-9]{1,12})', text):
            return Proposal('schedule.cancel', 'cancel_schedule', {'schedule_id': int(match[1])},
                            target_type='schedules')
        return 'Hãy cho biết ID của lịch muốn hủy.'
    if match := re.fullmatch(r'(?:doi|chuyen) (?:ngon ngu(?: giao dien)?|giao dien)(?: sang)? (.+)|'
                             r'(?:set|switch) (?:ui )?language(?: to)? (.+)', text):
        language = {'tieng anh': 'en', 'english': 'en', 'en': 'en', 'tieng viet': 'vi',
                    'vietnamese': 'vi', 'vi': 'vi'}.get(match[1] or match[2])
        if language is None:
            return 'Hãy chọn tiếng Việt hoặc tiếng Anh cho giao diện.'
        return Proposal('ui.set_language', 'set_language', {'language': language}, target_type='gateway')
    if match := re.fullmatch(r'(bat|tat|turn on|turn off) (?:thiet bi|device) (.+)', text):
        return Proposal('device.control', 'device_control',
                        {'action': 'on' if match[1] in ('bat', 'turn on') else 'off'}, match[2])
    if match := re.fullmatch(rf'(?:gioi han|limit) {DEVICE_PREFIX}(.+)', text):
        return _rate(match[1])
    if match := re.fullmatch(rf'(?:uu tien|prioritize|prioritise) ({APP}) {APP_LINK}{DEVICE_PREFIX}(.+)', text):
        return Proposal('qos.prioritize', 'optimize', {'application': _app(match[1])}, match[2])
    if re.match(r'^(?:uu tien|prioriti[sz]e)\b', text):
        return 'Hãy cho biết loại ứng dụng và thiết bị cần ưu tiên.'
    if match := re.fullmatch(rf'({BLOCK}|{RESUME}) ({APP}) {APP_LINK}{DEVICE_PREFIX}(.+)', text):
        block = bool(re.fullmatch(BLOCK, match[1]))
        return Proposal('application.block' if block else 'application.resume',
                        'block' if block else 'unblock',
                        {'scope': 'application', 'application': _app(match[2])}, match[3])
    if re.match(rf'^(?:{BLOCK}|{RESUME}) {APP}(?: |$)', text):
        return 'Hãy cho biết một thiết bị cho đề xuất theo ứng dụng.'
    if match := re.fullmatch(rf'(hen gio |dat lich |schedule )?{BLOCK} {DEVICE_PREFIX}(.+)', text):
        if timed := _schedule(match[2]):
            return Proposal('device.schedule', 'block', {'schedule': timed[1]}, timed[0])
        if match[1] or re.search(r'\b(?:trong|sau|tu|for|in|after|from|at) \d', match[2]):
            return 'Hãy nêu thời gian chặn rõ ràng, ví dụ trong 30 phút hoặc từ 21:00 đến 06:00 mỗi ngày.'
        return Proposal('device.block', 'block', device=match[2])
    if match := re.fullmatch(rf'{RESUME} {DEVICE_PREFIX}(.+)', text):
        return Proposal('device.resume', 'unblock', device=match[1])
    return None


def impact(proposal: Proposal, device: str = '') -> str:
    args = proposal.arguments
    if proposal.skill == 'application.block':
        return f'Firmware tham chiếu chặn toàn bộ Internet của {device}, kể cả ứng dụng ngoài {args["application"]}.'
    if proposal.skill == 'application.resume':
        return f'Firmware tham chiếu gỡ chặn toàn bộ Internet của {device}, kể cả ứng dụng ngoài {args["application"]}.'
    if proposal.skill == 'device.block':
        return f'{device} sẽ mất quyền truy cập Internet.'
    if proposal.skill == 'device.resume':
        return f'{device} có thể truy cập Internet trở lại nếu kết nối và các chính sách khác cho phép.'
    if proposal.skill == 'device.schedule':
        schedule = args['schedule']
        if 'start_time' in schedule:
            return f'Internet của {device} sẽ bị chặn theo lịch đề xuất, theo múi giờ của router.'
        delay = schedule.get('after_minutes')
        duration = schedule.get('duration_minutes')
        start = f' sau {delay} phút' if delay else ' ngay'
        window = f' trong {duration} phút.' if duration else '. Lịch này không đặt giờ tự khôi phục.'
        return f'Internet của {device} sẽ bị chặn{start}{window}'
    if proposal.skill == 'qos.prioritize':
        return f'Firmware tham chiếu ưu tiên toàn bộ lưu lượng của {device}. Các thiết bị khác có thể chậm hơn khi mạng bận.'
    if proposal.skill == 'qos.rate_limit':
        return f'Tốc độ của {device} có thể giảm đến mức đặt cho từng chiều. Chiều bỏ trống giữ cấu hình hiện tại.'
    if proposal.skill == 'network.guest_wifi':
        return ('Khách có thể kết nối mạng Wi-Fi khách khi được cấp thông tin truy cập.' if args['enabled'] else
                'Thiết bị đang dùng Wi-Fi khách có thể mất kết nối.')
    if proposal.skill == 'schedule.cancel':
        return f'Bỏ lịch số {args["schedule_id"]}. Nếu lịch đang chạy, firmware có thể khôi phục trạng thái trước lịch.'
    if proposal.skill == 'ui.set_language':
        return 'Đổi ngôn ngữ giao diện và nhận dạng giọng nói trên thiết bị tham chiếu.'
    if proposal.skill == 'device.control':
        return f'Lệnh bật/tắt dành cho {device}. Firmware tham chiếu còn thiếu chức năng điều khiển thiết bị.'
    raise ValueError('unknown_igate_proposal_skill')
