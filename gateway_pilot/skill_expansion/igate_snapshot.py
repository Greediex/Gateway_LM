"""Project iGate snapshot tables onto typed synthetic READ ports."""
from __future__ import annotations

import ipaddress
import math
import re
from datetime import datetime, timezone

import yaml

from ..core import PlanError

MAC = r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}'
APPLICATIONS = ('GAMING', 'VSTREAM', 'VOICE', 'VIDEOCALL')


class SnapshotLoader(yaml.SafeLoader):
    def construct_mapping(self, node, deep=False):
        pairs = self.construct_pairs(node, deep=deep)
        if any(type(key) is not str for key, _ in pairs) or len(dict(pairs)) != len(pairs):
            raise yaml.YAMLError('invalid or duplicate snapshot key')
        return dict(pairs)


def obj(properties: dict, required: tuple = ()) -> dict:
    return {'type': 'object', 'properties': properties, 'required': list(required),
            'additionalProperties': False}


def array(schema: dict) -> dict:
    return {'type': 'array', 'items': schema, 'maxItems': 512}


def numeric(kind='number', minimum=0, maximum=None) -> dict:
    return {'type': kind, 'minimum': minimum} | ({} if maximum is None else {'maximum': maximum})


INTEGER = numeric('integer')
NUMBER = numeric()
PERCENT = numeric(maximum=100)
BOOLEAN = {'type': 'boolean'}
STRING = {'type': 'string', 'minLength': 1}
MAC_SCHEMA = {'type': 'string', 'minLength': 17, 'maxLength': 17}
CLIENT_FIELDS = {'mac': MAC_SCHEMA, 'name': STRING, 'label': STRING, 'band': STRING, 'ip': STRING}
DEVICE_METRICS = {'rssi_dbm': numeric('integer', -127, -1), 'snr_db': numeric('integer', -127),
                  'rx_mbps': NUMBER, 'tx_mbps': NUMBER, 'link_mbps': NUMBER,
                  'idle_s': INTEGER, 'conn_s': INTEGER}
SYSTEM_METRICS = {'cpu_pct': PERCENT, 'mem_pct': PERCENT, 'temp_c': numeric(maximum=200)}
WAN_METRICS = {'ping_ms': NUMBER, 'rx_mbps': NUMBER, 'tx_mbps': NUMBER, 'link_mbps': NUMBER}
SPEED_METRICS = {'dl_mbps': NUMBER, 'ul_mbps': NUMBER, 'ping_ms': NUMBER, 'jitter_ms': NUMBER}
IDENTITY = {'complete': BOOLEAN, 'truncated': BOOLEAN}
PORT_SCHEMAS = {
    'device.find': obj({**IDENTITY, 'online_count': INTEGER,
                        'clients': array(obj(CLIENT_FIELDS, ('mac',)))}),
    'device.telemetry': obj({**IDENTITY, 'sampled_clients': INTEGER, 'weak_clients': INTEGER,
                             'clients': array(obj(CLIENT_FIELDS | DEVICE_METRICS, ('mac',)))}),
    'router.telemetry': obj({**SYSTEM_METRICS, **WAN_METRICS, 'system_metrics': INTEGER,
                             'wan_up': BOOLEAN, 'internet': BOOLEAN, 'guest_enabled': BOOLEAN,
                             'speedtest': obj(SPEED_METRICS | {'ok': BOOLEAN, 'last_ts': STRING})}),
    'traffic.application_sessions': obj({'qos_available': BOOLEAN, 'sessions_complete': BOOLEAN,
        'sessions': array(obj({'mac': MAC_SCHEMA, 'name': STRING, 'class': {'type': 'string', 'enum': list(APPLICATIONS)},
                               'session_s': INTEGER}, ('mac', 'class')))}),
    'schedule.list': obj({'known_counts': INTEGER, 'total': INTEGER,
                         'devices': array(obj({'mac': MAC_SCHEMA, 'count': INTEGER, 'name': STRING},
                                              ('mac', 'count')))}),
}


def _section(row: dict, key: str) -> dict:
    return row[key] if isinstance(row.get(key), dict) else {}


def _table(raw: object, *required: str) -> list[dict] | None:
    if raw in (None, '-'):
        return None
    if type(raw) is not str:
        raise PlanError('skill_sim_igate_table_format')
    lines = [line.split() for line in raw.splitlines() if line.strip()]
    if not lines:
        return None
    header, *rows = lines
    if len(set(header)) != len(header) or any(len(row) != len(header) for row in rows):
        raise PlanError('skill_sim_igate_table_shape')
    if not set(required) <= set(header):
        return None
    return [{key: item for key, item in zip(header, row) if item != '-'} for row in rows]


def _number(raw: object, schema: dict) -> float | int | None:
    if type(raw) not in (int, float, str):
        return None
    try:
        parse = int if schema['type'] == 'integer' else float
        if parse is int and type(raw) is float:
            return None
        value = parse(raw)
    except (ValueError, OverflowError):
        return None
    if not schema['minimum'] <= value <= schema.get('maximum', math.inf) or not math.isfinite(value):
        return None
    return value


def _numbers(row: dict, fields: dict) -> dict:
    return {key: value for key, schema in fields.items()
            if (value := _number(row.get(key), schema)) is not None}


def _flag(value: object) -> bool | None:
    if type(value) in (bool, int, str) and value in (0, 1, '0', '1'):
        return value in (1, '1')
    return None


def _stamp(value: object) -> str | None:
    try:
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        return moment.astimezone(timezone.utc).isoformat() if moment.tzinfo else None
    except ValueError:
        return None


def _mac(value: str = '') -> str | None:
    value = value.lower().replace('-', ':')
    return value if re.fullmatch(MAC, value) else None


def _ip(value: str = '') -> str | None:
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return None


def _devices(snapshot: dict) -> tuple[dict, list[dict], bool]:
    inventory = _numbers(snapshot, {'clients_count': INTEGER})
    if 'clients_count' in inventory:
        inventory['online_count'] = inventory.pop('clients_count')
    truncated = _flag(snapshot.get('clients_truncated'))
    if truncated is not None:
        inventory['truncated'] = truncated
    rows = _table(snapshot.get('clients'), 'mac')
    if rows is None:
        return inventory, [], False
    clients = []
    seen = set()
    for row in rows:
        mac = _mac(row.get('mac', ''))
        if mac is None or mac in seen:
            # A malformed or non-unique identity table cannot ground a request.
            return inventory, [], False
        seen.add(mac)
        client = {key: row[key].replace('_', ' ') for key in ('name', 'label', 'band') if key in row}
        if (ip := _ip(row.get('ip', ''))) is not None:
            client['ip'] = ip
        clients.append({'mac': mac, **client, **_numbers(row, DEVICE_METRICS)})
    count = inventory.get('online_count')
    # A present list with no completeness metadata can describe individual MACs,
    # but cannot prove an exact name match or an exact online count.
    inventory['complete'] = ((truncated is False and count in (None, len(clients)))
                             or (truncated is None and count == len(clients)))
    if count is not None and (count < len(clients) or (truncated is False and count != len(clients))):
        inventory.pop('online_count')
    if inventory['complete']:
        inventory.setdefault('online_count', len(clients))
    inventory['clients'] = [{key: row[key] for key in CLIENT_FIELDS if key in row} for row in clients]
    return inventory, clients, True


def _router(snapshot: dict) -> dict:
    metrics = _numbers(_section(snapshot, 'sys'), SYSTEM_METRICS)
    values = metrics | ({'system_metrics': len(metrics)} if metrics else {})
    wan = _section(snapshot, 'wan')
    values.update(_numbers(wan, WAN_METRICS))
    for key, field in (('up', 'wan_up'), ('internet', 'internet')):
        if (state := _flag(wan.get(key))) is not None:
            values[field] = state
    ssids = _table(_section(snapshot, 'wifi').get('ssids'), 'network', 'enabled')
    if ssids is not None:
        flags = [_flag(row.get('enabled')) for row in ssids if row.get('network') == 'guest']
        if True in flags:
            values['guest_enabled'] = True
        elif flags and all(flag is False for flag in flags) and all('network' in row for row in ssids):
            values['guest_enabled'] = False
    speedtest = _section(snapshot, 'speedtest')
    ok = _flag(speedtest.get('ok'))
    recorded_at = _stamp(speedtest.get('last_ts'))
    if recorded_at is not None and ok is not None:
        values['speedtest'] = {'ok': ok, 'last_ts': recorded_at}
        if ok:
            values['speedtest'].update(_numbers(speedtest, SPEED_METRICS))
    return values


def _by_ip(clients: list[dict]) -> dict:
    by_ip = {}
    for row in clients:
        if ip := row.get('ip'):
            by_ip[ip] = row if ip not in by_ip else None
    return by_ip


def _sessions(snapshot: dict, clients: list[dict]) -> dict:
    available = _flag(_section(snapshot, 'feed').get('qos'))
    if available is not True:
        return {} if available is None else {'qos_available': False}
    rows = _table(snapshot.get('qos'), 'ip', 'class')
    if rows is None:
        return {'qos_available': True}
    by_ip = _by_ip(clients)
    sessions, complete = [], True
    for row in rows:
        if 'class' not in row:
            complete = False
        if row.get('class') not in APPLICATIONS:
            continue
        client = by_ip.get(_ip(row.get('ip', '')))
        if client is None:
            complete = False
            continue
        sessions.append({'mac': client['mac'], 'name': device_name(client), 'class': row['class'],
                         **_numbers(row, {'session_s': INTEGER})})
    return {'qos_available': True, 'sessions': sessions, 'sessions_complete': complete}


def _schedules(snapshot: dict, clients: list[dict]) -> dict:
    policy = snapshot.get('policy')
    rows = _table(snapshot.get('policy_rows', policy if type(policy) is str else None), 'mac', 'scheds')
    if rows is None:
        return {}
    by_mac = {row['mac']: row for row in clients}
    devices = {}
    complete = True
    for row in rows:
        mac = _mac(row.get('mac', ''))
        count = _number(row.get('scheds'), INTEGER)
        if mac is None or count is None or (mac in devices and devices[mac]['count'] != count):
            complete = False
            continue
        devices[mac] = {'mac': mac, 'count': count, **(
            {'name': device_name(by_mac[mac])} if mac in by_mac else {})}
    values = {'devices': list(devices.values()), 'known_counts': len(devices)}
    if complete:
        values['total'] = sum(row['count'] for row in devices.values())
    return values if complete or devices else {}


def device_name(row: dict) -> str:
    return row.get('label') or row.get('name') or row['mac']


def read_snapshot(data: bytes) -> tuple[str, dict]:
    if len(data) > 65536:
        raise PlanError('skill_sim_igate_snapshot_size')
    try:
        snapshot = yaml.load(data, Loader=SnapshotLoader)
    except yaml.YAMLError as exc:
        raise PlanError('skill_sim_igate_snapshot_yaml') from exc
    if type(snapshot) is not dict or snapshot.get('mode') != 'demo' or not (ts := _stamp(snapshot.get('ts'))):
        raise PlanError('skill_sim_igate_demo_snapshot_required')
    inventory, clients, have_clients = _devices(snapshot)
    telemetry = {key: inventory[key] for key in IDENTITY if key in inventory}
    if have_clients:
        telemetry.update(clients=clients, sampled_clients=sum(bool(DEVICE_METRICS.keys() & row.keys())
                                                               for row in clients),
                         weak_clients=sum(row.get('rssi_dbm', 0) < -75 for row in clients))
    return ts, {'device.find': inventory, 'device.telemetry': telemetry,
                'router.telemetry': _router(snapshot),
                'traffic.application_sessions': _sessions(snapshot, clients),
                'schedule.list': _schedules(snapshot, clients)}
