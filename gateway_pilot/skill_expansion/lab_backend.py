"""LAB-01: read a few proposed Skill ports from the OpenWrt lab router over ubus.

Same supports/sample shape as StrictSkillReplayBackend, but values come from a
live read of an emulated router at sample time, inside Core. Evidence is
labelled ``openwrt_lab/``: emulated, never "Router verified" (CLAUDE.md L2).
Each reader maps raw ubus output to the port schema; anything it cannot map
raises, so Core admits no fact and Claims stay UNKNOWN.
"""
from __future__ import annotations

import copy
import json
from collections.abc import Callable
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any
from uuid import uuid4

from jsonschema import Draft202012Validator

SOURCE = 'openwrt_lab/ubus-ro'
PROVENANCE = 'openwrt_lab/'
TARGET_ID = 'lab-router'
ENVIRONMENT_ID = sha256(b'gateway-lm-openwrt-lab-qemu').hexdigest()


class LabReadError(ValueError):
    pass


def _wan(transport) -> dict:
    status = transport.read('network.interface.wan', 'status', {})
    if type(status.get('up')) is not bool:
        raise LabReadError('wan_status_without_up')
    return status


def wan_link(transport) -> dict:
    status = _wan(transport)
    if not status['up']:
        return {'link_up': False, 'uptime_seconds': 0}
    device = status.get('device') or status.get('l3_device')
    if not isinstance(device, str):
        raise LabReadError('wan_up_without_device')
    carrier = transport.read('network.device', 'status', {'name': device}).get('carrier')
    if type(carrier) is not bool or type(status.get('uptime')) is not int:
        raise LabReadError('wan_link_fields_missing')
    return {'link_up': carrier, 'uptime_seconds': status['uptime'] if carrier else 0}


def wan_routes(transport) -> dict:
    routes = _wan(transport).get('route', [])
    if not isinstance(routes, list):
        raise LabReadError('wan_routes_not_list')
    defaults = [r for r in routes if isinstance(r, dict) and r.get('target') == '0.0.0.0' and r.get('mask') == 0]
    return {'default_route': bool(defaults), 'default_route_count': len(defaults)}


def firmware_info(transport) -> dict:
    version = transport.read('system', 'board', {}).get('release', {}).get('version')
    avail_kib = transport.read('system', 'info', {}).get('root', {}).get('avail')
    if not isinstance(version, str) or not version or type(avail_kib) is not int:
        raise LabReadError('firmware_fields_missing')
    return {'version': version, 'free_storage_mb': round(avail_kib / 1024, 1)}


READERS: dict[str, Callable[[Any], dict]] = {
    'expansion.wan_link': wan_link,
    'expansion.wan_routes': wan_routes,
    'expansion.firmware_info': firmware_info,
}
# ubus methods each reader needs; probe() checks the router ACL grants them.
METHODS = {
    'expansion.wan_link': (('network.interface.wan', 'status'), ('network.device', 'status')),
    'expansion.wan_routes': (('network.interface.wan', 'status'),),
    'expansion.firmware_info': (('system', 'board'), ('system', 'info')),
}


class OpenWrtLabBackend:
    revision = '0.1.0'
    source = SOURCE

    def __init__(self, functions: list[dict], ports: list[dict], transport):
        self._functions = {f['function_id']: copy.deepcopy(f) for f in functions if f['function_id'] in READERS}
        self._ports = {p['port_id']: p for p in ports}
        self.transport = transport
        self.probe_ids = {fid: f['capability_probe'] for fid, f in self._functions.items()}

    def supports(self, function_id: str, context: Any) -> bool:
        f = self._functions.get(function_id)
        if f is None or getattr(context, 'scope', None) != f['scope'] \
                or getattr(context, 'target_id', None) != TARGET_ID \
                or getattr(context, 'environment_id', None) != ENVIRONMENT_ID:
            return False
        try:
            return all(self.transport.probe(o, m) is True for o, m in METHODS[function_id])
        except (OSError, RuntimeError, ValueError, TimeoutError):
            return False

    def sample_preview(self, function: dict, arguments: dict, context: Any) -> tuple[dict, ...]:
        fid = function['function_id']
        if arguments != {} or function != self._functions.get(fid) or not self.supports(fid, context):
            raise LabReadError('unsupported function, arguments or target')
        (port_id,) = function['outputs']
        value = READERS[fid](self.transport)
        if not Draft202012Validator(self._ports[port_id]['schema']).is_valid(value):
            raise LabReadError('lab value violates port schema: ' + port_id)
        encoded = (json.dumps(function, sort_keys=True, ensure_ascii=False, allow_nan=False,
                              separators=(',', ':')) + '\n').encode('utf-8')
        return ({'id': f'{fid}:0:{uuid4().hex}', 'function_id': fid, 'function_version': function['version'],
                 'metadata_function_digest': sha256(encoded).hexdigest(), 'port': port_id,
                 'scope': context.scope, 'target': context.target_id, 'environment_id': context.environment_id,
                 'source': self.source, 'status': 'OK', 'value': value,
                 'observed_at': datetime.now(timezone.utc).isoformat(), 'age_s': 0.0,
                 'ttl_s': function['ttl_seconds']},)

    def sample(self, function: dict, arguments: dict, context: Any):
        from gateway_pilot.adapters.results import ToolResult
        return ToolResult(observations=self.sample_preview(function, arguments, context))
