"""COV-02: versioned shared simulation scenarios (synthetic, READ-only).

Scenarios hold fixture values only. Gold outcomes live in a separate file that
only the scorer reads (no ground-truth leakage into fixtures or evidence).
Values are validated against the proposed port schemas before any run.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .catalog import DATA_DIR

SIM_DIR = DATA_DIR / "simulation_v1"
PORTS_DIR = DATA_DIR.parents[1] / "proposed_catalog_v02" / "ports"
STATES = frozenset({"normal", "fault", "missing"})
_SCENARIO_FIELDS = {"id", "skill_id", "state", "simulated_at", "function_id", "values"}
_GOLD_WORDS = ("gold", "expected", "label", "ground_truth", "verdict")


class SimulationError(ValueError):
    pass


@dataclass(frozen=True)
class Scenario:
    id: str
    skill_id: str
    state: str
    simulated_at: str
    function_id: str
    values: dict | None


def _read(path: Path) -> Any:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _no_gold(obj: Any, where: str) -> None:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if any(w in str(key).lower() for w in _GOLD_WORDS):
                raise SimulationError(f"gold-like key in scenarios: {where}.{key}")
            _no_gold(value, f"{where}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            _no_gold(value, f"{where}[{i}]")


def load_scenarios(sim_dir: Path = SIM_DIR, ports_dir: Path = PORTS_DIR) -> list[Scenario]:
    doc = _read(sim_dir / "scenarios.json")
    if doc.get("format") != "gateway-lm.skill-simulation/v1" or doc.get("synthetic_only") is not True:
        raise SimulationError("scenarios must be gateway-lm.skill-simulation/v1 and synthetic_only")
    _no_gold(doc, "scenarios")
    rows, seen = [], set()
    for raw in doc.get("scenarios", []):
        if not isinstance(raw, dict) or set(raw) != _SCENARIO_FIELDS:
            raise SimulationError(f"scenario fields mismatch: {raw!r:.80}")
        sc = Scenario(**raw)
        if sc.id in seen:
            raise SimulationError(f"duplicate scenario id {sc.id}")
        seen.add(sc.id)
        if sc.state not in STATES:
            raise SimulationError(f"{sc.id}: unknown state {sc.state!r}")
        if (sc.state == "missing") != (sc.values is None):
            raise SimulationError(f"{sc.id}: values must be null iff state is missing")
        port_path = ports_dir / f"{sc.function_id}.json"
        if not port_path.is_file():
            raise SimulationError(f"{sc.id}: unknown function/port {sc.function_id}")
        if sc.values is not None:
            schema = _read(port_path)["schema"]
            if not Draft202012Validator(schema).is_valid(sc.values):
                raise SimulationError(f"{sc.id}: values violate port schema")
        rows.append(sc)
    if not rows:
        raise SimulationError("no scenarios")
    return rows


def load_gold(scenarios: list[Scenario], sim_dir: Path = SIM_DIR) -> dict[str, str]:
    """Scorer-only access to expected outcomes."""
    doc = _read(sim_dir / "gold_v1.json")
    expected = doc.get("expected", {})
    if set(expected) != {s.id for s in scenarios}:
        raise SimulationError("gold must cover exactly the scenario ids")
    if not set(expected.values()) <= {"VERIFIED", "NOT_READY"}:
        raise SimulationError("gold outcome must be VERIFIED or NOT_READY")
    return dict(expected)
