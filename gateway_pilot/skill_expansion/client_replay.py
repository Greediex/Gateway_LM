"""Trusted normal fixtures for the isolated client replay deployment.

Only scenario values enter the backend; gold files are never read here.
"""
from __future__ import annotations

from ..adapters.bindings import require
from .simulation import load_scenarios


def normal_fixtures() -> dict[str, dict]:
    selected = [s for s in load_scenarios()
                if s.state == 'normal' and s.skill_id in {'A04', 'A06', 'A08'}]
    require(len(selected) == 3 and {s.skill_id for s in selected} == {'A04', 'A06', 'A08'},
            'skill_client_scenarios')
    fixtures = {s.function_id: {s.function_id: s.values} for s in selected}
    fixtures['expansion.synthetic_client_identity'] = {
        'client.identity': {'client_id': 'synthetic-test-target'}}
    return fixtures
