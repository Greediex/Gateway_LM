"""Operator-pinned Simulation replay inputs and scoped Core READ composition."""
from __future__ import annotations

import copy
import json
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from functools import lru_cache

from jsonschema import Draft202012Validator

from ..adapters.bindings import BindingSelection, TargetContext, binding_digest, declare_binding, require
from ..command_catalog.builder import build_registry
from ..command_catalog.loader import canonical_bytes, digest, read_json
from ..command_catalog.runtime import ReadRuntime
from ..core import ROOT
from ..graph_v3.claims import ClaimBook
from . import composite, igate_data, incident_replay, simulation
from .catalog import DATA_DIR, Skill, SkillCatalog
from .coverage import ACCEPTANCE_STATES, COMPOSITE_BATCHES, DIRECT_BATCHES, acceptance_snapshot
from .replay_backend import StrictSkillReplayBackend
from .runtime_bridge import RuntimeSkillBridge

MODE = 'replay_sim'
STATES = ACCEPTANCE_STATES
CLIENT_IDENTITY = 'expansion.synthetic_client_identity'
TARGET = 'synthetic-test-target'
NOTICE = 'Dữ liệu mô phỏng, không phải mạng thật.'
CONFIG = ROOT / 'config/skill_launcher'
CLIENT_CATALOG = ROOT / 'examples/skill_deployments/client_replay_v1'


class SimulationReplayBackend(StrictSkillReplayBackend):
    source = 'synthetic_replay/replay_sim_v1'

    def __init__(self, functions: list[dict], ports: list[dict], fixture: dict, context: TargetContext):
        super().__init__(functions, ports, fixture)
        self._context = context

    def supports(self, function_id: str, context: TargetContext) -> bool:
        return context == self._context and super().supports(function_id, context)


@dataclass(frozen=True)
class Sample:
    function_id: str
    scope: str
    target: str
    simulated_at: str
    values: dict | None


@dataclass(frozen=True)
class ReplayCatalog:
    actions: dict
    diagnostics: dict
    samples: dict[str, dict[str, dict[str, Sample]]]
    registries: dict


@dataclass(frozen=True)
class ReplayProfile(ReplayCatalog):
    approval: dict[str, str]
    igate: ReplayCatalog
    igate_vendor: dict[str, bytes]
    incidents: ReplayCatalog  # GP01..GP07: not among the 120 Skills, never counted as verified
    incident_replay: incident_replay.IncidentReplay

    def open_sample(self, sample: Sample, *, environment: str, clock: Callable[[], float],
                    max_calls: int, ttl_s: float, cost_budget: float = 100):
        catalog = (self if sample.function_id in self.registries
                   else self.igate if sample.function_id in self.igate.registries else self.incidents)
        artifact, policy, owner = catalog.registries[sample.function_id]
        fixture = {} if sample.values is None else {sample.function_id: {sample.function_id: sample.values}}
        if sample.scope == 'client':
            fixture[CLIENT_IDENTITY] = {'client.identity': {'client_id': sample.target}}
        context = TargetContext(sample.scope, sample.target, environment)
        backend = SimulationReplayBackend(artifact['functions'], artifact['ports'], fixture, context)
        frozen_fixture = digest(fixture)
        bindings = [declare_binding(artifact, f['function_id'], 'launcher.' + f['function_id'],
                                    self.approval['backend_id'], backend, context)
                    for f in artifact['functions']]
        selection = BindingSelection(
            artifact, policy, bindings, approved_digests=frozenset(map(binding_digest, bindings)),
            backends={self.approval['backend_id']: backend}, context=context)
        permissions = frozenset(f['permission'] for f in artifact['functions'])
        require(permissions <= {'network.read', 'system.read'}, 'skill_sim_read_permissions')
        runtime = ReadRuntime(
            artifact, policy, approved_digest=artifact['content_digest'], selection=selection, context=context,
            permissions=permissions,
            policy_context_id=digest({'principal': 'localhost-skill-operator', 'mode': MODE,
                                      'permissions': sorted(permissions), 'revision': 1}),
            clock=clock)
        session = runtime.open_session(max_calls=max_calls, ttl_s=ttl_s, max_plans=1, cost_budget=cost_budget,
                                       context_valid=lambda: digest(backend._fixture) == frozen_fixture)
        if catalog is self.igate:
            row = catalog.actions[owner]
            owner = artifact['skills'][0]['skill_id']
            design = Skill(owner, row['name'], row['domain'], 'iGate', 'P0', 'PROPOSED',
                           'Synthetic READ', sample.scope, MODE, 'iGate snapshot', None, 'NOT_BOUND')
            return session, RuntimeSkillBridge(runtime, SkillCatalog([design], [])), owner
        return session, RuntimeSkillBridge(runtime), owner


@lru_cache(maxsize=128)
def _compile_registry(catalog: bytes, selection: bytes, policy: bytes) -> dict:
    return build_registry(json.loads(catalog), json.loads(selection), json.loads(policy))


def _registry(function: dict, *, port: dict | None = None, owner: dict | None = None) -> tuple[dict, dict, str]:
    """Compile the selected READ Function and its required synthetic identity."""
    function = copy.deepcopy(function)
    fid = function['function_id']
    require(function['risk'] == 'READ_ONLY' and function['lifecycle'] == 'PROPOSED'
            and function['permission'] in {'network.read', 'system.read'}
            and not function['inputs'] and not function['order_after'] and len(function['skill_refs']) == 1
            and set(function['outputs']) == {fid}, 'skill_sim_function_contract')
    function['lifecycle'] = 'IMPLEMENTED'
    ref = function['skill_refs'][0]
    if owner is None:
        owner = read_json(simulation.skill_path(ref['skill_id'], fid))
    functions = [function]
    ports = [port if port is not None else read_json(simulation.port_path(fid))]
    if function['scope'] == 'client':
        identity = read_json(CLIENT_CATALOG / 'functions/skill_expansion' / f'{CLIENT_IDENTITY}.json')
        identity['skill_refs'] = [ref]
        functions.append(identity)
        ports.append(read_json(CLIENT_CATALOG / 'ports/client.identity.json'))
        function['inputs'].update(identity['outputs'])
        owner['function_refs'][CLIENT_IDENTITY] = identity['version']
        owner['produces'].update(identity['outputs'])
    policy = {'schema_version': '0.2.0', 'allowed_probe_ids': [f['capability_probe'] for f in functions]}
    selection = {'schema_version': '0.2.0', 'kind': 'selection',
                 'functions': {f['function_id']: f['version'] for f in functions},
                 'ports': {p['port_id']: p['version'] for p in ports}}
    catalog = {'functions': functions, 'ports': ports, 'skills': [owner],
               'source_digests': {}, 'record_digests': {}}
    for group in ('functions', 'ports', 'skills'):
        for row in catalog[group]:
            kind = row['kind']
            key = row[kind + '_id']
            path = f"{group}/{row['domain']}/{key}.json" if kind == 'function' else f'{group}/{key}.json'
            catalog['source_digests'][path] = catalog['record_digests'][f"{kind}:{key}@{row['version']}"] = digest(row)
    artifact = _compile_registry(canonical_bytes(catalog), canonical_bytes(selection), canonical_bytes(policy))
    return copy.deepcopy(artifact), policy, ref['skill_id'].split('.')[-1].upper()


def _igate_catalog(vendor: dict) -> tuple[ReplayCatalog, str]:
    from hashlib import sha256

    from .igate_snapshot import PORT_SCHEMAS, read_snapshot

    definitions = igate_data.catalog()
    require(len(definitions) == len(PORT_SCHEMAS)
            and {row['skill'] for row in definitions.values()} == PORT_SCHEMAS.keys()
            and set(definitions) == {f'IG{i:02d}' for i in range(1, 6)}, 'skill_sim_igate_skills')
    raw = {state: (igate_data.SCENARIOS / f'{state}.yaml').read_bytes() for state in STATES}
    snapshots = {state: read_snapshot(data) for state, data in raw.items()}
    actions, skills, sources, registries = {}, {}, {}, {}
    for sid, row in definitions.items():
        actions[sid] = igate_data.action(sid, row)
        fid = igate_data.function_id(sid)
        schema = PORT_SCHEMAS[row['skill']]
        version = '1.0.0'
        ref = {'skill_id': fid, 'version': version}
        common = {'schema_version': '0.2.0', 'version': version}
        port = {**common, 'kind': 'port', 'port_id': fid, 'scope': 'gateway', 'schema': schema,
                'provenance': 'synthetic_replay/', 'untrusted_text': True}
        function = {**common, 'kind': 'function', 'function_id': fid, 'description': row['name'],
                    'domain': igate_data.DOMAIN, 'skill_refs': [ref], 'lifecycle': 'PROPOSED',
                    'inputs': {}, 'outputs': {fid: version}, 'scope': 'gateway', 'risk': 'READ_ONLY',
                    'permission': 'network.read', 'arguments_schema': {'type': 'object', 'properties': {},
                        'required': [], 'additionalProperties': False}, 'argument_sources': {},
                    'preconditions': [], 'order_after': [], 'effects': [], 'timeout_ms': 2000,
                    'retry': {'max_attempts': 1}, 'ttl_seconds': 30, 'cost': 1.0, 'latency_ms': 0.0,
                    'capability_probe': 'probe.' + fid, 'verifier': 'schema_scope_provenance_freshness/v3',
                    'on_unknown': 'BLOCK_AND_REQUEST_EVIDENCE', 'tags': ['synthetic_replay']}
        owner = {**common, 'kind': 'skill', **ref, 'name': row['name'], 'description': row['skill'],
                 'requires': {}, 'produces': {fid: version}, 'completion_ports': {fid: version},
                 'function_refs': {fid: version}, 'tags': ['replay']}
        artifact, policy, owner_id = _registry(function, port=port, owner=owner)
        require(owner_id == sid, 'skill_sim_igate_owner')
        registries[fid] = artifact, policy, owner_id
        claims = [{'claim_id': name, 'diagnosis': name, 'scope': 'gateway', 'severity': severity,
                   'requires': [{'port': fid, 'field': field, 'op': op, 'value': value}], 'excludes': [],
                   'message_key': name, 'workflow': sid}
                  for name, severity, field, op, value in row['claims']]
        require(all(c['claim_id'].endswith('_v1') and c['requires'][0]['field'] in schema['properties']
                    for c in claims), 'skill_sim_igate_claim_schema')
        workflows = {sid: {'target_scope': 'gateway', 'claims': [c['claim_id'] for c in claims]}}
        ClaimBook(claims, {fid: port}, workflows)
        skills[sid] = {'kind': 'direct', 'workflows': workflows, 'claims': claims}
        validator = Draft202012Validator(schema)
        sources[sid] = {}
        for state, (ts, snapshot) in snapshots.items():
            value = snapshot[row['skill']] or None
            require(value is None or validator.is_valid(value), 'skill_sim_igate_fixture_schema')
            sources[sid][state] = {fid: Sample(fid, 'gateway', TARGET, ts, value)}
    pin = digest({'catalog': definitions, 'vendor': vendor,
                  'registries': {fid: a['content_digest'] for fid, (a, _, _) in registries.items()},
                  'snapshots': {state: sha256(data).hexdigest() for state, data in raw.items()},
                  'samples': {sid: {state: [asdict(sample) for sample in by_alias.values()]
                                    for state, by_alias in states.items()} for sid, states in sources.items()}})
    return ReplayCatalog(actions, {'skills': skills}, sources, registries), pin


def _incident_catalog(design: dict, proposals: dict) -> tuple[ReplayCatalog, str]:
    """GP incident checks: composite workflows over READ ports, with their own scenarios and pin."""
    from .coverage import INCIDENT_CONFIG

    cfg = read_json(INCIDENT_CONFIG)
    doc = composite.contracts(cfg['batch'])
    require(cfg['format'] == 'gateway-lm.replay-sim-incident-checks/v1'
            and set(cfg['skills']) == set(doc['workflows']) and not design.keys() & cfg['skills'].keys(),
            'skill_sim_incident_membership')
    skills, samples, fids = {}, {sid: {} for sid in cfg['skills']}, set()
    for sid, workflow in doc['workflows'].items():
        skills[sid] = {'kind': 'composite', 'scope': workflow['target_scope'], 'workflows': {sid: workflow},
                       'claims': [c for c in doc['claims'] if c['workflow'] == workflow['workflow_id']]}
    for row in composite.load_scenarios(cfg['batch']):
        sid, workflow = row['skill_id'], doc['workflows'][row['skill_id']]
        sources = {}
        for alias, spec in workflow['sources'].items():
            fid = spec['function_id']
            require(fid in proposals and spec['scope'] == proposals[fid]['scope'] and spec['target'] == TARGET,
                    'skill_sim_source_scope_or_target')
            composite.timestamp(row['sources'][alias]['simulated_at'])
            sources[alias] = Sample(fid, spec['scope'], spec['target'], row['sources'][alias]['simulated_at'],
                                    row['sources'][alias]['values'])
            fids.add(fid)
        state = row['id'].rsplit('-', 1)[-1]
        require(state in STATES and state not in samples[sid], 'skill_sim_duplicate_scenario')
        samples[sid][state] = sources
    require(all(set(v) == set(STATES) for v in samples.values()), 'skill_sim_scenario_membership')
    registries = {fid: _registry(proposals[fid]) for fid in sorted(fids)}
    for states in samples.values():
        for sources in states.values():
            for sample in sources.values():
                schema = next(p['schema'] for p in registries[sample.function_id][0]['ports']
                              if p['port_id'] == sample.function_id)
                require(sample.values is None or Draft202012Validator(schema).is_valid(sample.values),
                        'skill_sim_fixture_schema')
    actions = {sid: {'skill_id': sid, 'name': cfg['skills'][sid]['name'], 'domain': 'GP', 'kind': 'incident',
                     'scope': skills[sid]['scope'],
                     'required_ports': {s.function_id: proposals[s.function_id]['outputs'][s.function_id]
                                        for s in samples[sid]['normal'].values()}, 'optional_ports': {}}
               for sid in skills}
    diagnostics = {'skills': skills,
                   'routing': {sid: item['phrases'] for sid, item in cfg['skills'].items()},
                   'claim_text': {c: t for item in cfg['skills'].values() for c, t in item['claim_text'].items()}}
    pin = digest({'config': cfg, 'actions': actions, 'diagnostics': diagnostics,
                  'samples': {sid: {state: [[a, asdict(s)] for a, s in sources.items()]
                                    for state, sources in states.items()} for sid, states in samples.items()},
                  'registries': {fid: a['content_digest'] for fid, (a, _, _) in registries.items()}})
    return ReplayCatalog(actions, diagnostics, samples, registries), pin


def prepare_profile() -> ReplayProfile:
    """Build deterministic approval inputs from accepted contracts and scenarios."""
    acceptance, accepted = acceptance_snapshot()
    design = SkillCatalog.load().skills
    require(bool(accepted) and accepted <= design.keys() and 'SK13' not in accepted, 'skill_sim_membership')
    proposals = {f['function_id']: f for f in simulation.function_proposals()}
    skills: dict[str, dict] = {}
    samples: dict[str, dict[str, dict[str, Sample]]] = {sid: {} for sid in accepted}
    fids = set()
    routing = read_json(CONFIG / 'replay_sim.routing.json')
    require(set(routing) == {'format', 'phrases', 'nonlocal_scope_phrases'}
            and routing['format'] == 'gateway-lm.replay-sim-routing/v1'
            and routing['phrases'].keys() <= design.keys(), 'skill_sim_routing')

    def add(sid: str, state: str, sources: dict[str, Sample]):
        require(state in STATES and state not in samples[sid], 'skill_sim_duplicate_scenario')
        for sample in sources.values():
            require(sample.function_id in proposals and sample.scope == proposals[sample.function_id]['scope']
                    and sample.target == TARGET, 'skill_sim_source_scope_or_target')
            composite.timestamp(sample.simulated_at)
            fids.add(sample.function_id)
        samples[sid][state] = sources

    for directory, filename in DIRECT_BATCHES.values():
        doc = read_json(CONFIG / f'{filename}.diagnostics.json')
        require(doc['format'] == 'gateway-lm.laptop-diagnostics/v1', 'skill_sim_diagnostics_format')
        for sc in simulation.load_scenarios(DATA_DIR / directory):
            sid, fid = sc.skill_id, sc.function_id
            if sid not in accepted:
                continue
            scope = proposals[fid]['scope']
            workflows = {wid: doc['workflows'][wid] for wid in doc['skill_workflows'][sid]}
            diagnostic = {'kind': 'direct', 'scope': scope, 'workflows': workflows,
                          'claims': [c for c in doc['claims'] if c['workflow'] in workflows]}
            require(not sid in skills or skills[sid] == diagnostic, 'skill_sim_diagnostics_membership')
            skills[sid] = diagnostic
            add(sid, sc.state, {fid: Sample(fid, scope, TARGET, sc.simulated_at, sc.values)})

    for batch in COMPOSITE_BATCHES:
        doc = composite.contracts(batch)
        for row in composite.load_scenarios(batch):
            sid = row['skill_id']
            if sid not in accepted:
                continue
            workflow = doc['workflows'][sid]
            diagnostic = {'kind': 'composite', 'scope': workflow['target_scope'],
                          'workflows': {sid: workflow}, 'claims': [
                              c for c in doc['claims'] if c['workflow'] == workflow['workflow_id']]}
            require(not sid in skills or skills[sid] == diagnostic, 'skill_sim_diagnostics_membership')
            skills[sid] = diagnostic
            add(sid, row['id'].rsplit('-', 1)[-1], {
                alias: Sample(spec['function_id'], spec['scope'], spec['target'],
                              row['sources'][alias]['simulated_at'], row['sources'][alias]['values'])
                for alias, spec in workflow['sources'].items()})

    require(skills.keys() == accepted and all(set(v) == set(STATES) for v in samples.values()),
            'skill_sim_scenario_membership')
    registries = {fid: _registry(proposals[fid]) for fid in sorted(fids)}
    validators = {fid: Draft202012Validator(next(p['schema'] for p in a['ports'] if p['port_id'] == fid))
                  for fid, (a, _, _) in registries.items()}
    for states in samples.values():
        for sources in states.values():
            for sample in sources.values():
                require(sample.values is None or validators[sample.function_id].is_valid(sample.values),
                        'skill_sim_fixture_schema')
    # Include aliases and sampling order: a JSON object digest alone ignores insertion order.
    fixture_inputs = {sid: {state: [[alias, asdict(sample)] for alias, sample in sources.items()]
                            for state, sources in states.items()} for sid, states in samples.items()}
    actions = {}
    for sid, diagnostic in skills.items():
        ports = {s.function_id: proposals[s.function_id]['outputs'][s.function_id]
                 for s in samples[sid]['normal'].values()}
        if diagnostic['kind'] == 'direct':
            require(all({s.function_id for s in sources.values()} == ports.keys()
                        for sources in samples[sid].values()), 'skill_sim_direct_function')
            fid = next(iter(ports))
            artifact, _, owner = registries[fid]
            require(owner == sid, 'skill_sim_direct_owner')
            ClaimBook(diagnostic['claims'], {p['port_id']: p for p in artifact['ports']}, diagnostic['workflows'])
        actions[sid] = {'skill_id': sid, 'name': design[sid].name_vi, 'domain': design[sid].domain,
                        'kind': 'design', 'scope': diagnostic['scope'], 'required_ports': ports,
                        'optional_ports': {}}
    diagnostics = {'routing': routing, 'skills': skills}
    approval = {
        'registry_digest': digest({fid: a['content_digest'] for fid, (a, _, _) in registries.items()}),
        'actions_digest': digest(actions), 'diagnostics_digest': digest(diagnostics),
        'fixtures_digest': digest({'acceptance': digest(acceptance), 'samples': fixture_inputs,
                                   'client_identity_target': TARGET}),
        'backend_id': 'expansion.simulation_replay', 'backend_revision': SimulationReplayBackend.revision,
        'source': SimulationReplayBackend.source,
    }
    vendor, contents = igate_data.vendor_data()
    igate, approval['igate_digest'] = _igate_catalog(vendor)
    incidents, approval['incident_checks_digest'] = _incident_catalog(design, proposals)
    base = ReplayCatalog(actions, diagnostics, samples, registries)
    worlds, approval['incident_scenarios_digest'] = incident_replay.load_incident_replay(base, igate, incidents)
    return ReplayProfile(actions, diagnostics, samples, registries, approval,
                         igate=igate, igate_vendor=contents, incidents=incidents, incident_replay=worlds)


def approved_profile(approval: dict) -> ReplayProfile:
    profile = prepare_profile()
    for key, value in profile.approval.items():
        require(approval.get(key) == value, 'skill_sim_' + key + '_pin')
    return profile


@dataclass
class ReplaySession:
    """One fixed scenario and cumulative budget across scoped READ sessions."""
    profile: ReplayProfile
    scenario: str
    clock: Callable[[], float] = time.monotonic
    calls: int = 0
    max_calls: int = 24
    plans: int = 0
    max_plans: int = 64
    spent: float = 0
    cost_budget: float = 100
    closed: bool = False

    def __post_init__(self):
        require(type(self.scenario) is str and
                (self.scenario in STATES or self.scenario in self.profile.incident_replay.measurements),
                'skill_sim_scenario')
        self.expires_at = self.clock() + 300
        self.environment = digest({'approval': self.profile.approval, 'scenario': self.scenario})

    def close(self):
        self.closed = True
