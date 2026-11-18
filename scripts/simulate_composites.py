"""WP-A4 synthetic orchestration through existing Core; gold only in scorer."""
from __future__ import annotations

import json
from collections.abc import Callable

from gateway_pilot.core import PlanError
from gateway_pilot.skill_expansion.composite import (
    SIM_DIR, VerifiedSource, assess, contracts, load_scenarios,
)
from gateway_pilot.skill_expansion.runtime_bridge import SkillNotReady
from gateway_pilot.skill_expansion.simulation import SimulationError
from scripts.core_replay_smoke_v2 import smoke


def run_scenario(row: dict, *, inspect: Callable | None = None) -> dict:
    """Trusted fixture harness, with no deployment approvals or gold input."""
    sources, calls, failures = {}, 0, {}
    specs = contracts()['workflows'][row['skill_id']]['sources']
    if set(row['sources']) != set(specs):
        raise SimulationError('composite source set mismatch')
    for alias, spec in specs.items():
        sample = row['sources'][alias]
        def capture(state):
            sources[alias] = VerifiedSource(state, sample['simulated_at'])
            return {}
        try:
            result = smoke(spec['function_id'], values=sample['values'],
                           omit=sample['values'] is None, assess=capture, require_fact=False)
            calls += result['core_calls']
        except (SkillNotReady, PlanError) as exc:
            failures[alias] = str(exc)
    if inspect is not None:
        inspect(sources)
    result = assess(row['skill_id'], sources)
    return {'id': row['id'], 'skill_id': row['skill_id'], 'core_calls': calls,
            'source_errors': failures, **result}


def evaluate() -> dict:
    scenarios = load_scenarios()
    rows = [run_scenario(row) for row in scenarios]
    # Deliberately after all execution; never consulted by the backend/Claim view.
    gold = json.loads((SIM_DIR / 'gold.json').read_text(encoding='utf-8'))
    expected = gold.get('expected', {})
    if (gold.get('format') != 'gateway-lm.composite-gold/v1' or gold.get('version') != '1.0.0'
            or gold.get('scenarios_version') != '1.0.0'
            or set(expected) != {r['id'] for r in rows}
            or not set(expected.values()) <= {'HEALTHY', 'FAULT', 'UNKNOWN'}):
        raise SimulationError('invalid composite gold')
    for row in rows:
        row['pass'] = row['verdict'] == expected[row['id']]
    return {'synthetic_only': True, 'total': len(rows), 'passed': sum(r['pass'] for r in rows), 'rows': rows}


if __name__ == '__main__':
    report = evaluate()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    raise SystemExit(report['total'] != report['passed'])
