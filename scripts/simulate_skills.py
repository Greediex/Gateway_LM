"""Score synthetic Core evidence and versioned Claims; gold is scorer-only.

Does not approve deployment or mark Skills Simulation verified (WP-A5).
FAULT/HEALTHY describe the declared predicates, not causal RCA or repair.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateway_pilot.graph_v3.claims import ClaimBook
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.skill_expansion.runtime_bridge import SkillNotReady
from gateway_pilot.skill_expansion.simulation import (
    SIM_DIR, Scenario, SimulationError, load_gold, load_scenarios,
)
from scripts.core_replay_smoke_v2 import smoke

DIAGNOSTICS = Path(__file__).resolve().parents[1] / 'config/skill_launcher/replay_a.diagnostics.json'


def assess_claims(state: CaseState, skill_id: str) -> dict:
    """Evaluate declared predicates on Core state, never on raw fixture values."""
    doc = json.loads(DIAGNOSTICS.read_text(encoding='utf-8'))
    workflows = {wid: doc['workflows'][wid] for wid in doc['skill_workflows'][skill_id]}
    rows = [row for row in doc['claims'] if row['workflow'] in workflows]
    book = ClaimBook(rows, state.registry.ports, workflows)
    results = {}
    for workflow in workflows:
        results.update(book.evaluate_all(state, workflow))
    supported = [r for r in results.values() if r['value'] == 'TRUE' and r['evidence']]
    severities = {r['severity'] for r in supported}
    # Conflicting or insufficient proof must never yield a positive verdict.
    verdict = next(iter(severities)) if len(severities) == 1 else 'UNKNOWN'
    return {'verdict': verdict, 'claims': results}


def load_claim_gold(scenarios: list[Scenario], sim_dir: Path = SIM_DIR) -> dict[str, str]:
    """Scorer-only versioned expectations, read after execution has finished."""
    doc = json.loads((sim_dir / 'gold_claims_v1.json').read_text(encoding='utf-8'))
    expected = doc.get('expected', {})
    if (doc.get('format') != 'gateway-lm.skill-simulation-claims-gold/v1'
            or doc.get('version') != '1.0.0' or doc.get('scenarios_version') != '1.0.0'
            or set(expected) != {s.id for s in scenarios}
            or not set(expected.values()) <= {'FAULT', 'HEALTHY', 'UNKNOWN'}):
        raise SimulationError('invalid claim gold version, scenario ids or verdicts')
    return dict(expected)


def run_scenario(sc: Scenario) -> dict:
    try:
        result = smoke(sc.function_id, values=sc.values, omit=sc.values is None,
                       assess=lambda state: assess_claims(state, sc.skill_id))
    except SkillNotReady as exc:
        return {'id': sc.id, 'outcome': 'NOT_READY', 'verdict': 'UNKNOWN',
                'claims': {}, 'reason': str(exc)}
    if result['fact_value'] != sc.values:
        return {'id': sc.id, 'outcome': 'VALUE_MISMATCH', 'verdict': 'UNKNOWN', 'claims': {}}
    return {'id': sc.id, 'outcome': 'VERIFIED', 'evidence_id': result['evidence_id'],
            'core_calls': result['core_calls'], **result['assessment']}


def evaluate() -> dict:
    scenarios = load_scenarios()
    rows = [run_scenario(sc) for sc in scenarios]
    gold = load_gold(scenarios)
    claim_gold = load_claim_gold(scenarios)
    for row in rows:
        row['pass'] = row['outcome'] == gold[row['id']] and row['verdict'] == claim_gold[row['id']]
    return {'synthetic_only': True, 'total': len(rows),
            'passed': sum(r['pass'] for r in rows), 'rows': rows}


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    report = evaluate()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report['passed'] == report['total'] else 1)
