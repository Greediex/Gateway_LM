"""Synthetic composite Claims over scoped Core states, never new READ Functions.

Source aliases are a read-only Claim view, not ports or admitted observations.
The trusted simulation binds sources explicitly; count-only inventory cannot
prove client membership, device type, individual lifecycle, or causal RCA.
"""
from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from ..graph_v3.claims import ClaimBook
from ..graph_v3.contracts import validate
from ..graph_v3.state import CaseState
from .catalog import DATA_DIR
from .coverage import COMPOSITE_BATCHES
from .simulation import PORTS_DIR, SimulationError, _no_gold

ROOT = Path(__file__).resolve().parents[2]


def batch_paths(batch: str) -> tuple[Path, Path]:
    try:
        directory, diagnostics = COMPOSITE_BATCHES[batch]
    except KeyError as exc:
        raise SimulationError(f'unknown composite batch: {batch}') from exc
    return DATA_DIR / directory, ROOT / 'config/skill_launcher' / f'{diagnostics}.diagnostics.json'


SIM_DIR, DIAGNOSTICS = batch_paths('A')


def _source_fields(spec: dict) -> frozenset[str]:
    # Use the existing port contract, never fixture or diagnostics keys, as
    # the allowlist for measurements such as expected_routes.
    port = PORTS_DIR / f"{spec['function_id']}.json"
    schema = json.loads(port.read_text(encoding='utf-8'))['schema']
    return frozenset(schema.get('properties', {}))


def contracts(batch: str = 'A') -> dict:
    _, diagnostics = batch_paths(batch)
    doc = json.loads(diagnostics.read_text(encoding='utf-8'))
    if (doc.get('format') != 'gateway-lm.composite-diagnostics/v1'
            or doc.get('version') != '1.0.0' or doc.get('synthetic_only') is not True):
        raise SimulationError('invalid composite contracts')
    metadata = copy.deepcopy(doc)
    for workflow in metadata['workflows'].values():
        for alias, spec in workflow['sources'].items():
            value_schema = spec.pop('value_schema', None)
            if value_schema is not None:
                _no_gold(value_schema, f'composite source schema {alias}', _source_fields(spec))
    _no_gold(metadata, 'composite contracts')
    return doc


def timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('timezone required')
        return parsed
    except (AttributeError, TypeError, ValueError) as exc:
        raise SimulationError('invalid simulated timestamp') from exc


def load_scenarios(batch: str = 'A') -> list[dict]:
    sim_dir, _ = batch_paths(batch)
    doc = json.loads((sim_dir / 'scenarios.json').read_text(encoding='utf-8'))
    if (doc.get('format') != 'gateway-lm.composite-simulation/v1'
            or doc.get('version') != '1.0.0' or doc.get('synthetic_only') is not True):
        raise SimulationError('invalid composite scenarios')
    _no_gold({key: value for key, value in doc.items() if key != 'scenarios'},
             'composite scenarios')
    workflows = contracts(batch)['workflows']
    seen = set()
    for row in doc['scenarios']:
        _no_gold({key: value for key, value in row.items() if key != 'sources'},
                 'composite scenario metadata')
        if (set(row) != {'id', 'skill_id', 'sources'} or row['id'] in seen
                or row['skill_id'] not in workflows
                or set(row['sources']) != set(workflows[row['skill_id']]['sources'])):
            raise SimulationError('invalid composite scenario sources or id')
        seen.add(row['id'])
        for alias, sample in row['sources'].items():
            _no_gold({key: value for key, value in sample.items() if key != 'values'},
                     f'composite sample metadata {alias}')
            if set(sample) != {'simulated_at', 'values'}:
                raise SimulationError('invalid composite sample')
            timestamp(sample['simulated_at'])
            spec = workflows[row['skill_id']]['sources'][alias]
            _no_gold(sample['values'], f"{row['id']}.{alias}", _source_fields(spec))
    if not seen:
        raise SimulationError('empty composite scenarios')
    return doc['scenarios']


@dataclass(frozen=True)
class VerifiedSource:
    """Trusted local Core reference; must never be accepted from HTTP/LLM input."""

    state: CaseState
    simulated_at: str


class _ClaimView:
    def __init__(self, facts: dict):
        self.facts = facts

    def fact(self, alias: str) -> dict | None:
        return self.facts.get(alias)


def assess(skill_id: str, sources: dict[str, VerifiedSource], *, batch: str = 'A') -> dict:
    """Recheck every source before ClaimBook; any missing source fails closed.

    History compares two independently verified samples, with distinct proof IDs,
    increasing simulated times, identical environment/target/segment and live TTL
    checks on both Core states. Simulated time never extends an evidence lease.
    """
    doc = contracts(batch)
    workflow = doc['workflows'][skill_id]
    rows = [copy.deepcopy(c) for c in doc['claims'] if c['workflow'] == workflow['workflow_id']]
    unknown = {'verdict': 'UNKNOWN', 'claims': {
        c['claim_id']: {'value': 'UNKNOWN', 'evidence': [], 'severity': c['severity']}
        for c in rows}, 'limitation': workflow['limitation']}
    if set(sources) != set(workflow['sources']):
        return {**unknown, 'reason': 'missing_or_foreign_source'}
    facts, environments, sample_times = {}, set(), set()
    for alias, spec in workflow['sources'].items():
        source = sources[alias]
        state = source.state
        if not isinstance(state, CaseState):
            return {**unknown, 'reason': 'not_core_state'}
        fact = state.fact(spec['function_id'])
        runtime = getattr(state.registry, 'runtime', None)
        if (fact is None or runtime is None or not state.allowed(state.registry.functions[spec['function_id']])
                or runtime.context.scope != spec['scope'] or runtime.context.target_id != spec['target']
                or fact['scope'] != spec['scope'] or fact['target'] != spec['target']
                or not fact['source'].startswith('synthetic_replay/')):
            return {**unknown, 'reason': 'unusable_source:' + alias}
        environments.add((state.boot_id, state.config_version))
        facts[alias] = fact
        sample_times.add(timestamp(source.simulated_at))
        value = fact['value']
        value_schema = spec.get('value_schema')
        if value_schema is not None:
            if (not validate(value, value_schema)
                    or any(isinstance(field, float) and not math.isfinite(field)
                           for field in value.values())):
                return {**unknown, 'reason': 'insufficient_source:' + alias}
        if any(value[field] > value[upper_field]
               for field, upper_field in spec.get('field_maximums', {}).items()):
            return {**unknown, 'reason': 'inconsistent_source:' + alias}
        if ('devices_count' in value and value['devices_count'] < 0
                or value.get('oui_known') is True and not value.get('oui_vendor', '').strip()):
            return {**unknown, 'reason': 'inconsistent_source:' + alias}
    if len(environments) != 1 or len({f['id'] for f in facts.values()}) != len(facts):
        return {**unknown, 'reason': 'environment_or_duplicate_proof'}
    if workflow.get('require_same_sample_time') and len(sample_times) != 1:
        return {**unknown, 'reason': 'different_sample_times'}
    history = workflow.get('history')
    if history:
        earlier, later = history['earlier'], history['later']
        if (timestamp(sources[earlier].simulated_at) >= timestamp(sources[later].simulated_at)
                or facts[earlier]['value'][history['same_field']] != facts[later]['value'][history['same_field']]):
            return {**unknown, 'reason': 'history_order_or_segment'}
    # Resolve cross-sample numeric comparisons only from usable facts. No new
    # evidence is manufactured: ClaimBook returns the original Core proof IDs.
    for row in rows:
        for predicate in row['requires']:
            value = predicate['value']
            if isinstance(value, dict):
                predicate['value'] = facts[value['source']]['value'][value['field']]
    wid = workflow['workflow_id']
    book = ClaimBook(rows, facts, {wid: workflow})
    results = book.evaluate_all(_ClaimView(facts), wid)
    severities = {c['severity'] for c in results.values() if c['value'] == 'TRUE' and c['evidence']}
    return {'verdict': next(iter(severities)) if len(severities) == 1 else 'UNKNOWN',
            'claims': results, 'limitation': workflow['limitation']}
