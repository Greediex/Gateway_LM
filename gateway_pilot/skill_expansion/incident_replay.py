"""Shared synthetic incident measurements, symptom routes and advisory metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

from ..adapters.bindings import require
from ..command_catalog.loader import digest, read_json
from ..graph_v3.claims import ClaimBook
from ..workflow import normalize
from .catalog import DATA_DIR
from .composite import timestamp

if TYPE_CHECKING:
    from .replay_sim import ReplayCatalog, Sample

DIRECTORY = DATA_DIR / 'incidents_v1'
ADVISORY = 'khuyến nghị — chưa thực hiện, áp dụng trên router của bạn'


def _text(value: object) -> bool:
    return type(value) is str and bool(value.strip())


def _texts(values: object) -> bool:
    return type(values) is list and bool(values) and all(map(_text, values))


def _source_url(value: str) -> bool:
    parts = urlsplit(value)
    return parts.scheme == 'https' and bool(parts.hostname) and parts.username is None


def _references() -> tuple[dict, dict]:
    doc = read_json(DIRECTORY / 'router_incidents_v1.json')
    require(set(doc) == {'format', 'note', 'note_vi', 'incidents'}
            and doc['format'] == 'gateway-lm.router-incidents/v1'
            and _text(doc['note']) and _text(doc['note_vi'])
            and type(doc['incidents']) is list and bool(doc['incidents']), 'skill_sim_incident_references')
    rows = {}
    for row in doc['incidents']:
        require(type(row) is dict and set(row) == {
            'id', 'title_vi', 'user_says', 'signals', 'fix_vi', 'skills', 'sources'
        }, 'skill_sim_incident_reference_fields')
        key = row['id']
        require(_text(key) and re.fullmatch(r'INC-[A-Z0-9-]+', key) and key not in rows
                and _text(row['title_vi']) and _texts(row['fix_vi'])
                and _texts(row['sources']) and all(map(_source_url, row['sources'])),
                'skill_sim_incident_reference')
        rows[key] = row
    return doc, rows


def scenario_options() -> list[dict[str, str]]:
    """Display metadata can load even while the operator pin is pending."""
    _, rows = _references()
    return [{'id': key, 'title': row['title_vi']} for key, row in rows.items()]


@dataclass(frozen=True)
class IncidentReplay:
    current_time: datetime
    measurements: dict[str, dict]
    guidance: dict[str, dict]
    symptom_routes: dict[str, str]
    claim_text: dict[str, str]
    joint_checks: dict[str, tuple[dict[str, Sample], dict]]

    def samples_for(self, scenario: str, baseline: dict[str, Sample]) -> dict[str, Sample]:
        values = self.measurements[scenario]
        times = {alias: timestamp(sample.simulated_at) for alias, sample in baseline.items()}
        latest = max(times.values())
        return {
            alias: replace(sample,
                           simulated_at=(self.current_time + (times[alias] - latest)).isoformat(),
                           values=values.get(sample.function_id, sample.values)
                           if times[alias] == latest else sample.values)
            for alias, sample in baseline.items()
        }

    def recommendation(self, scenario: str, proof: list[str], evidence: list[dict]) -> dict | None:
        overrides = self.measurements[scenario]
        ids = set(proof)
        if any(row['id'] in ids and row['port'] in overrides
               and timestamp(row['simulated_at']) == self.current_time for row in evidence):
            return self.guidance[scenario]
        return None


def _joint_check(sid: str, config: dict, current: dict, ports: dict) -> tuple[dict, dict]:
    require(set(config) == {'sources', 'claims', 'limitation'} and _text(config['limitation'])
            and type(config['sources']) is dict and len(config['sources']) >= 2
            and set(config['sources'].values()) <= current.keys(), 'skill_sim_incident_joint_check')
    samples = {alias: current[fid] for alias, fid in config['sources'].items()}
    require(len({s.function_id for s in samples.values()}) == len(samples)
            and len({s.scope for s in samples.values()}) == 1, 'skill_sim_incident_joint_sources')
    scope = next(iter(samples.values())).scope
    wid = 'REPLAY-INCIDENT-' + sid
    workflow = {'workflow_id': wid, 'target_scope': scope, 'require_same_sample_time': True,
                'sources': {alias: {'function_id': s.function_id, 'scope': s.scope, 'target': s.target}
                            for alias, s in samples.items()}, 'limitation': config['limitation']}
    claims = []
    for row in config['claims']:
        require(set(row) == {'claim_id', 'severity', 'requires'}
                and row['severity'] in {'FAULT', 'HEALTHY'}
                and all(p['port'] in samples and p['field'] in
                        ports[samples[p['port']].function_id]['schema']['properties'] for p in row['requires']),
                'skill_sim_incident_joint_claim')
        cid = row['claim_id']
        claims.append(dict(row, diagnosis=cid, scope=scope, excludes=[], message_key=cid, workflow=wid))
    workflow['claims'] = [row['claim_id'] for row in claims]
    ClaimBook(claims, samples, {wid: workflow})
    return samples, {'kind': 'composite', 'workflows': {sid: workflow}, 'claims': claims}


def load_incident_replay(base: ReplayCatalog, igate: ReplayCatalog, checks: ReplayCatalog) -> tuple[IncidentReplay, str]:
    reference, rows = _references()
    scenarios = read_json(DIRECTORY / 'scenarios.json')
    routing = read_json(DIRECTORY / 'routing.json')
    diagnostic = read_json(DIRECTORY / 'diagnostics.json')
    require(set(scenarios) == {'format', 'simulated_at', 'scenarios'}
            and scenarios['format'] == 'gateway-lm.incident-replay/v1'
            and type(scenarios['scenarios']) is dict and scenarios['scenarios'].keys() == rows.keys(),
            'skill_sim_incident_scenarios')
    require(set(routing) == {'format', 'phrases'} and routing['format'] == 'gateway-lm.incident-symptom-routing/v1'
            and type(routing['phrases']) is dict and routing['phrases'].keys() <= (base.actions.keys() | checks.actions.keys()),
            'skill_sim_incident_routing')
    require(set(diagnostic) == {'format', 'joint_checks', 'claim_text'}
            and diagnostic['format'] == 'gateway-lm.incident-replay-diagnostics/v1'
            and diagnostic['joint_checks'].keys() <= base.actions.keys(), 'skill_sim_incident_diagnostics')

    ports = {fid: next(p for p in artifact['ports'] if p['port_id'] == fid)
             for catalog in (base, igate, checks) for fid, (artifact, _, _) in catalog.registries.items()}
    validators = {fid: Draft202012Validator(port['schema']) for fid, port in ports.items()}
    for measurements in scenarios['scenarios'].values():
        require(type(measurements) is dict and bool(measurements)
                and all(fid in validators and type(value) is dict and validators[fid].is_valid(value)
                        for fid, value in measurements.items()), 'skill_sim_incident_fixture_schema')

    routes = {}
    for sid, phrases in routing['phrases'].items():
        require(_texts(phrases), 'skill_sim_incident_phrases')
        for phrase in phrases:
            key = normalize(phrase)
            require(bool(key) and key not in routes, 'skill_sim_incident_duplicate_phrase')
            routes[key] = sid

    direct = {sample.function_id: sample for sid, states in base.samples.items()
              if base.diagnostics['skills'][sid]['kind'] == 'direct'
              for sample in states['normal'].values()}
    joint = {sid: _joint_check(sid, config, direct, ports) for sid, config in diagnostic['joint_checks'].items()}
    for sid, (samples, _) in joint.items():
        action = base.actions[sid]
        require(action['required_ports'].keys() <= {s.function_id for s in samples.values()}
                and all(s.scope == action['scope'] for s in samples.values()),
                'skill_sim_incident_joint_action')
    # Direct fixtures have their own capture dates. Joint checks read both values
    # at the incident snapshot's common time.
    now = timestamp(scenarios['simulated_at'])
    joint = {sid: ({alias: replace(sample, simulated_at=now.isoformat()) for alias, sample in samples.items()}, doc)
             for sid, (samples, doc) in joint.items()}
    views = [*base.diagnostics['skills'].values(), *(doc for _, doc in joint.values())]
    claims = {c['claim_id'] for view in views for c in view['claims']}
    require(diagnostic['claim_text'].keys() <= claims and all(map(_text, diagnostic['claim_text'].values())),
            'skill_sim_incident_claim_text')
    guidance = {key: {'label': ADVISORY, 'steps': row['fix_vi'], 'sources': row['sources']}
                for key, row in rows.items()}
    profile = IncidentReplay(now, scenarios['scenarios'], guidance, routes, diagnostic['claim_text'], joint)
    # Source order affects which READs can run under a partial call budget.
    return profile, digest({'scenarios': scenarios, 'references': reference, 'routing': routing,
                            'diagnostics': diagnostic, 'advisory': ADVISORY,
                            'joint_source_order': {sid: list(samples) for sid, (samples, _) in joint.items()}})
