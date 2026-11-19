"""Score synthetic Core evidence and versioned Claims; gold is scorer-only.

Can generate simulation acceptance without granting deployment approval.
FAULT/HEALTHY describe the declared predicates, not causal RCA or repair.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateway_pilot.graph_v3.claims import ClaimBook
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.skill_expansion.catalog import DATA_DIR
from gateway_pilot.skill_expansion.coverage import COMPOSITE_BATCHES, DIRECT_BATCHES
from gateway_pilot.skill_expansion.runtime_bridge import SkillNotReady
from gateway_pilot.skill_expansion.simulation import (
    SIM_DIR, Scenario, SimulationError, load_gold, load_scenarios,
)
from scripts.core_replay_smoke_v2 import smoke

ROOT = Path(__file__).resolve().parents[1]
DIAGNOSTICS = ROOT / 'config/skill_launcher/replay_a.diagnostics.json'
# (scenario/gold dir, Claim diagnostics) per direct-Skill batch; composites run separately.
BATCHES = tuple((DATA_DIR / d, ROOT / 'config/skill_launcher' / f'{diag}.diagnostics.json')
                for d, diag in DIRECT_BATCHES.values())


def assess_claims(state: CaseState, skill_id: str, diagnostics: Path = DIAGNOSTICS) -> dict:
    """Evaluate declared predicates on Core state, never on raw fixture values."""
    doc = json.loads(diagnostics.read_text(encoding='utf-8'))
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


def run_scenario(sc: Scenario, diagnostics: Path = DIAGNOSTICS) -> dict:
    try:
        result = smoke(sc.function_id, values=sc.values, omit=sc.values is None,
                       assess=lambda state: assess_claims(state, sc.skill_id, diagnostics))
    except SkillNotReady as exc:
        return {'id': sc.id, 'outcome': 'NOT_READY', 'verdict': 'UNKNOWN',
                'claims': {}, 'reason': str(exc)}
    if result['fact_value'] != sc.values:
        return {'id': sc.id, 'outcome': 'VALUE_MISMATCH', 'verdict': 'UNKNOWN', 'claims': {}}
    return {'id': sc.id, 'outcome': 'VERIFIED', 'evidence_id': result['evidence_id'],
            'core_calls': result['core_calls'], **result['assessment']}


def evaluate(sim_dir: Path = SIM_DIR, diagnostics: Path = DIAGNOSTICS) -> dict:
    scenarios = load_scenarios(sim_dir)
    rows = [run_scenario(sc, diagnostics) for sc in scenarios]
    gold = load_gold(scenarios, sim_dir)
    claim_gold = load_claim_gold(scenarios, sim_dir)
    for row in rows:
        row['pass'] = row['outcome'] == gold[row['id']] and row['verdict'] == claim_gold[row['id']]
    skill_of = {sc.id: sc.skill_id for sc in scenarios}
    for row in rows:
        row['skill_id'] = skill_of[row['id']]
    return {'synthetic_only': True, 'total': len(rows),
            'passed': sum(r['pass'] for r in rows), 'rows': rows}


def evaluate_all() -> dict:
    """Every direct-Skill batch plus composites, as one report (gold read after each run)."""
    from scripts.simulate_composites import evaluate as evaluate_composites
    reports = [evaluate(sim_dir, diagnostics) for sim_dir, diagnostics in BATCHES]
    reports.extend(evaluate_composites(batch) for batch in COMPOSITE_BATCHES)
    return {'synthetic_only': True, 'total': sum(r['total'] for r in reports),
            'passed': sum(r['passed'] for r in reports),
            'rows': [row for r in reports for row in r['rows']]}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-acceptance', action='store_true',
                        help='write simulation_v1/acceptance.json from this run (WP-A5)')
    args = parser.parse_args()
    report = evaluate_all()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.write_acceptance:
        from gateway_pilot.skill_expansion.coverage import ACCEPTANCE, build_acceptance
        ACCEPTANCE.write_text(json.dumps(build_acceptance(report['rows']), indent=2) + '\n',
                              encoding='utf-8')
    raise SystemExit(0 if report['passed'] == report['total'] else 1)
