"""Explicit, synthetic READ-only backend for Gateway LM v0.2.

Not a router adapter, not a producer of factual real-world evidence. A trusted
composition root must supply reviewed catalog metadata, binding approvals and
explicit synthetic TargetContext. No auto-approval of metadata or capabilities.
"""
from __future__ import annotations
import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import json
import re
from typing import Any

from jsonschema import Draft202012Validator

_SOURCE = 'synthetic_replay/skill_expansion_v2'
_REVISION = '0.2.0'

class ReplayFixtureError(ValueError):
    pass

class StrictSkillReplayBackend:
    """Fixture-driven provider satisfying the same supports/sample methods as FND-04.

    Caller constructs this object from *trusted local* proposal metadata at startup;
    no user/LLM input is accepted as a function ID, target, or fixture path.
    """
    revision = _REVISION
    source = _SOURCE

    def __init__(self, functions: list[dict], ports: list[dict], fixture: dict[str, dict]):
        self._functions = {r['function_id']:copy.deepcopy(r) for r in functions}
        self._ports = {r['port_id']:copy.deepcopy(r) for r in ports}
        if len(self._functions)!=len(functions) or len(self._ports)!=len(ports):
            raise ReplayFixtureError('duplicate declaration')
        if type(fixture) is not dict:
            raise ReplayFixtureError('fixture must be mapping')
        self._fixture = copy.deepcopy(fixture)
        self.probe_ids = {f['function_id']: f['capability_probe'] for f in functions}
        for fid, values in self._fixture.items():
            if fid not in self._functions or type(values) is not dict:
                raise ReplayFixtureError('unknown fixture function')
            f = self._functions[fid]
            if set(values)!=set(f['outputs']):
                raise ReplayFixtureError('fixture missing/extra outputs:'+fid)
            for pid,value in values.items():
                if pid not in self._ports or self._ports[pid]['scope'] != f['scope']:
                    raise ReplayFixtureError('port missing/scope mismatch')
                if not Draft202012Validator(self._ports[pid]['schema']).is_valid(value):
                    raise ReplayFixtureError('fixture schema failure:'+pid)

    @classmethod
    def from_bundle(cls, data_dir: Path|str) -> 'StrictSkillReplayBackend':
        folder = Path(data_dir)
        return cls(json.loads((folder/'function_proposals.json').read_text(encoding='utf-8')),
                   _port_documents(folder.parent.parent/'proposed_catalog_v02'/'ports'),
                   json.loads((folder/'replay_fixtures_v2.json').read_text(encoding='utf-8')))

    def supports(self, function_id: str, context: Any) -> bool:
        """Synthetic contexts only. Never claim capability on a real gateway."""
        f = self._functions.get(function_id)
        return bool(f is not None and function_id in self._fixture and
                    getattr(context,'scope',None)==f['scope'] and
                    type(getattr(context,'target_id',None)) is str and
                    context.target_id.startswith('synthetic-') and
                    re.fullmatch(r'[0-9a-f]{64}',str(getattr(context,'environment_id',''))))

    def sample_preview(self, function: dict, arguments: dict, context: Any) -> tuple[dict,...]:
        """Generate observation rows for tests; Core still must validate and admit."""
        fid = function['function_id']
        if not self.supports(fid,context):
            raise ReplayFixtureError('unsupported function or target')
        if arguments != {}:
            raise ReplayFixtureError('unexpected replay arguments')
        if function != self._functions[fid]:
            raise ReplayFixtureError('function metadata changed')
        # Deliberately import same digest routine as Core if installed; local
        # fallback implements its documented canonical encoding for offline tests.
        from hashlib import sha256
        encoded=(json.dumps(function,sort_keys=True,ensure_ascii=False,
                  allow_nan=False,separators=(',',':'))+'\n').encode('utf-8')
        metadata_digest=sha256(encoded).hexdigest()
        observed=(datetime.now(timezone.utc)-timedelta(milliseconds=2)).isoformat()
        rows=[]
        for idx,pid in enumerate(sorted(function['outputs'])):
            rows.append({'id':f'{fid}:{idx}:{uuid4().hex}',
                'function_id':fid,'function_version':function['version'],
                'metadata_function_digest':metadata_digest,
                'port':pid,'scope':context.scope,'target':context.target_id,
                'environment_id':context.environment_id,'source':self.source,
                'status':'OK','value':copy.deepcopy(self._fixture[fid][pid]),
                'observed_at':observed,'age_s':0.0,'ttl_s':function['ttl_seconds']})
        return tuple(rows)

    def sample(self, function: dict, arguments: dict, context: Any):
        from gateway_pilot.adapters.results import ToolResult
        return ToolResult(observations=self.sample_preview(function, arguments, context))


def _port_documents(root: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding='utf-8')) for p in sorted(root.glob('*.json'))]
