"""COV-01: derive the 120-Skill coverage inventory from data and deployments.

Every number is computed from versioned catalog data, Registry v0.1 and the
approved launcher deployments; nothing is typed in by hand. Reported levels
are deliberately conservative: being in a deployment is *launchable*, not
*verified*. ``simulation_verified`` comes only from ``acceptance.json``, which
``scripts.simulate_skills --write-acceptance`` generates from a real run and
pins to its input files; ``router_verified`` stays False (L1/L2 in CLAUDE.md).
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from .catalog import DATA_DIR, SkillCatalog

REGISTRY_V01 = DATA_DIR.parents[0] / "registry_v01.json"
EXPECTED_TOTAL = 120
EXPECTED_DOMAINS = 15
EXPECTED_PER_DOMAIN = 8
SKILL_TYPES = ("direct", "composite", "history", "change", "legacy_v01")
ACCEPTANCE = DATA_DIR / "simulation_v1" / "acceptance.json"
# Direct-Skill batches: letter -> (scenario/gold dir under DATA_DIR, Claim diagnostics name).
# One place to register a batch; simulate_skills and the acceptance digest both read it.
DIRECT_BATCHES = {
    "A": ("simulation_v1", "replay_a"),
    "B": ("simulation_b_v1", "replay_b"),
    "C": ("simulation_c_v1", "replay_c"),
    "D": ("simulation_d_v1", "replay_d"),
    "E": ("simulation_e_v1", "replay_e"),
    "F": ("simulation_f_v1", "replay_f"),
    "G": ("simulation_g_v1", "replay_g"),
    "H": ("simulation_h_v1", "replay_h"),
    "I": ("simulation_i_v1", "replay_i"),
    "J": ("simulation_j_v1", "replay_j"),
    "L": ("simulation_l_v1", "replay_l"),
    "N": ("simulation_n_v1", "replay_n"),
}
# Batch A keeps the original WP-A4 fixture directory.
COMPOSITE_BATCHES = {
    "A": ("simulation_composite_v1", "replay_a_composite"),
    "C": ("simulation_c_composite_v1", "replay_c_composite"),
    "D": ("simulation_d_composite_v1", "replay_d_composite"),
    "G": ("simulation_g_composite_v1", "replay_g_composite"),
    "I": ("simulation_i_composite_v1", "replay_i_composite"),
    "J": ("simulation_j_composite_v1", "replay_j_composite"),
    "K": ("simulation_k_composite_v1", "replay_k_composite"),
    "L": ("simulation_l_composite_v1", "replay_l_composite"),
    "M": ("simulation_m_composite_v1", "replay_m_composite"),
    "N": ("simulation_n_composite_v1", "replay_n_composite"),
    "O": ("simulation_o_composite_v1", "replay_o_composite"),
    "S": ("simulation_s_composite_v1", "replay_s_composite"),
}
# INCIDENT-GAPS checks GP01..GP07 are not among the 120 Skills: they have their own scenarios and
# diagnostics, run in replay_sim, and are reported as incident_checks_simulated, never as verified Skills.
INCIDENT_BATCHES = {"GAP": ("simulation_gaps_composite_v1", "replay_gaps_composite")}
INCIDENT_CONFIG = DATA_DIR.parents[1] / "config" / "skill_launcher" / "replay_sim.incidents.json"
# Every file that decides a simulated verdict; editing one invalidates acceptance.
ACCEPTANCE_INPUTS = tuple(
    [f"{d}/{name}" for d, _ in DIRECT_BATCHES.values()
     for name in ("scenarios.json", "gold_v1.json", "gold_claims_v1.json")]
    + [f"{d}/{name}" for d, _ in COMPOSITE_BATCHES.values()
       for name in ("scenarios.json", "gold.json")]
    + [f"../../config/skill_launcher/{diag}.diagnostics.json" for _, diag in DIRECT_BATCHES.values()]
    + [f"../../config/skill_launcher/{diag}.diagnostics.json" for _, diag in COMPOSITE_BATCHES.values()]
)
ACCEPTANCE_STATES = ("normal", "fault", "missing")


class CoverageError(ValueError):
    """Raised when the inventory does not have the exact 120/15x8 shape."""


@dataclass(frozen=True)
class SkillCoverage:
    skill_id: str
    name: str
    domain: str
    batch: str
    skill_type: str
    catalog: bool
    contract_reviewed: bool
    replay_launchable: bool
    live_launchable: bool
    simulation_verified: bool
    router_verified: bool
    hard_dependencies: tuple[str, ...]
    proposed_dependencies: tuple[str, ...]
    gaps: tuple[str, ...]


def _load(path: Path):
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def classify(*, mapping: Mapping, stub: Mapping, write_set: tuple[str, ...]) -> str:
    """Skill type from data only: WRITE set > time-series scope > mapping mode."""
    if write_set:
        return "change"
    if "time-series" in str(stub.get("target_scope_draft", "")):
        return "history"
    mode = mapping.get("proposal_mode")
    if mode == "PROPOSED_READ_METADATA":
        return "direct"
    if mode == "NO_DIRECT_READ_FUNCTION":
        return "composite"
    if mode == "LEGACY_DISCOVER_FROM_REPO":
        return "legacy_v01"
    raise CoverageError(f"unknown proposal_mode for {mapping.get('skill_id')}: {mode!r}")


def inputs_digest(data_dir: Path = DATA_DIR) -> str:
    h = hashlib.sha256()
    for rel in ACCEPTANCE_INPUTS:
        h.update(rel.encode() + b"\0" + (data_dir / rel).read_bytes() + b"\0")
    return h.hexdigest()


def build_acceptance(rows: list[dict], data_dir: Path = DATA_DIR) -> dict:
    """Per-Skill evidence from simulate_skills rows; the only acceptance writer."""
    skills: dict[str, dict] = {}
    for row in rows:
        state = row["id"].rsplit("-", 1)[-1]
        if state not in ACCEPTANCE_STATES or state in skills.get(row["skill_id"], {}):
            raise CoverageError(f"unexpected simulation row {row['id']!r}")
        skills.setdefault(row["skill_id"], {})[state] = {
            "pass": row["pass"] is True, "core_calls": int(row.get("core_calls") or 0),
            "verdict": row["verdict"]}
    return {"format": "gateway-lm.skill-acceptance/v1", "version": "1.0.0",
            "synthetic_only": True, "inputs_digest": inputs_digest(data_dir),
            "skills": dict(sorted(skills.items()))}


def accepted_skills(path: Path = ACCEPTANCE, data_dir: Path = DATA_DIR) -> set[str]:
    """Skills with passing normal/fault/missing runs; normal/fault must reach Core."""
    if not path.exists():
        return set()
    doc, skills = acceptance_snapshot(path)
    if doc.get("inputs_digest") != inputs_digest(data_dir):
        raise CoverageError("stale acceptance: rerun simulate_skills --write-acceptance")
    return skills


def acceptance_snapshot(path: Path = ACCEPTANCE) -> tuple[dict, set[str]]:
    """Read recorded membership without opening scorer inputs such as gold."""
    doc = _load(path)
    if (doc.get("format") != "gateway-lm.skill-acceptance/v1" or doc.get("version") != "1.0.0"
            or doc.get("synthetic_only") is not True):
        raise CoverageError("invalid acceptance format")
    return doc, {sid for sid, states in doc["skills"].items()
            if set(states) == set(ACCEPTANCE_STATES)
            and all(states[s]["pass"] is True for s in ACCEPTANCE_STATES)
            and all(states[s]["core_calls"] > 0 for s in ("normal", "fault"))}


def _default_actions(mode: str) -> Mapping:
    from .deployment import deployment
    return deployment(mode)[3]


def build_coverage(
    data_dir: Path = DATA_DIR,
    registry_path: Path = REGISTRY_V01,
    actions_for: Callable[[str], Mapping] = _default_actions,
    acceptance_path: Path = ACCEPTANCE,
) -> list[SkillCoverage]:
    return _coverage_rows(data_dir, registry_path, actions_for,
                          lambda: accepted_skills(acceptance_path, data_dir))


def _coverage_rows(data_dir: Path, registry_path: Path, actions_for: Callable[[str], Mapping],
                   accepted_for: Callable[[], set[str]]) -> list[SkillCoverage]:
    catalog = SkillCatalog.load(data_dir)
    mappings = {m["skill_id"]: m for m in _load(data_dir / "skill_function_mapping_120.json")}
    stubs = {s["skill_id"]: s for s in _load(data_dir / "skill_contract_stubs_120.json")}
    writes = {s["skill_id"]: tuple(s.get("write_set", ()))
              for s in _load(registry_path).get("skills", ())}
    ids = list(catalog.skills)
    if len(ids) != EXPECTED_TOTAL or set(ids) != set(mappings) or set(ids) != set(stubs):
        raise CoverageError("skills, mapping and contract stubs must share exactly 120 IDs")
    per_domain = Counter(s.domain for s in catalog.skills.values())
    if len(per_domain) != EXPECTED_DOMAINS or set(per_domain.values()) != {EXPECTED_PER_DOMAIN}:
        raise CoverageError(f"expected 15 domains x 8 skills, got {dict(per_domain)}")

    def design_ids(mode: str) -> set[str]:
        return {k for k, v in actions_for(mode).items() if v.get("kind") == "design"}

    replay, live = design_ids("replay"), design_ids("live")
    accepted = accepted_for()
    unknown = (replay | live | accepted) - set(ids)
    if unknown:
        raise CoverageError(f"deployment references unknown skills: {sorted(unknown)}")

    hard: dict[str, set[str]] = {i: set() for i in ids}
    proposed: dict[str, set[str]] = {i: set() for i in ids}
    for rel in catalog.relations:
        if rel.type == "depends_on" and rel.source in hard:
            (hard if rel.status == "EXISTING_V01" else proposed)[rel.source].add(rel.target)

    rows = []
    for sid in ids:
        skill, mapping, stub = catalog.skills[sid], mappings[sid], stubs[sid]
        stype = classify(mapping=mapping, stub=stub, write_set=writes.get(sid, ()))
        reviewed = bool(stub.get("runtime_binding_approved"))
        gaps = []
        if not reviewed:
            gaps.append("CONTRACT_NOT_REVIEWED")
        if mapping.get("requires_claim_or_workflow_definition"):
            gaps.append("NEEDS_CLAIM_OR_WORKFLOW")
        if stype == "change":
            gaps.append("WRITE_SANDBOX_ONLY")
        if sid in replay:
            gaps.append("REPLAY_PENDING_ACCEPTANCE")
        elif stype != "change":
            gaps.append("NO_REPLAY_PROFILE")
        if sid not in live:
            gaps.append("NO_LIVE_BINDING")
        gaps.append("NO_ROUTER_BACKEND")
        rows.append(SkillCoverage(
            skill_id=sid, name=skill.name_vi, domain=skill.domain,
            batch=f"COV-{skill.domain}", skill_type=stype, catalog=True,
            contract_reviewed=reviewed, replay_launchable=sid in replay,
            live_launchable=sid in live, simulation_verified=sid in accepted, router_verified=False,
            hard_dependencies=tuple(sorted(hard[sid])),
            proposed_dependencies=tuple(sorted(proposed[sid])), gaps=tuple(gaps)))
    return rows


def summarize(rows: list[SkillCoverage]) -> dict:
    count = lambda field: sum(1 for r in rows if getattr(r, field))
    return {
        "total": len(rows),
        "denominator_note": "120 catalog Skills only; laptop.* actions are excluded",
        "by_type": dict(sorted(Counter(r.skill_type for r in rows).items())),
        "levels": {f: count(f) for f in ("catalog", "contract_reviewed", "replay_launchable",
                                         "live_launchable", "simulation_verified",
                                         "router_verified")},
        "by_batch": {b: n for b, n in sorted(Counter(r.batch for r in rows).items())},
    }


def coverage_report(**kwargs) -> dict:
    from .igate_data import catalog

    rows = build_coverage(**kwargs)
    incidents = _load(INCIDENT_CONFIG)["skills"]
    return {"summary": summarize(rows), "skills": [asdict(r) for r in rows],
            "igate_simulated": {sid: item["skill"] for sid, item in catalog().items()},
            "incident_checks_simulated": {sid: item["name"] for sid, item in incidents.items()}}


def _graph_actions(config: Path, mode: str) -> Mapping:
    """Read pinned launch descriptors without building a registry or probing a backend."""
    from ..command_catalog.loader import digest, read_json

    approvals = read_json(config / "approvals.json")
    actions = read_json(config / f"{mode}.actions.json")
    if (approvals.get("format") != "gateway-lm.skill-launcher-approval/v1"
            or actions.get("format") != "gateway-lm.skill-actions/v1"
            or actions.get("mode") != mode
            or digest(actions) != approvals[mode]["actions_digest"]):
        raise CoverageError(f"unapproved graph launch metadata: {mode}")
    return {action["skill_id"]: action for action in actions["actions"]}


def skill_graph(data_dir: Path = DATA_DIR, *, replay_sim: bool = False) -> dict:
    """Project catalog links and coverage metadata for display."""
    config = data_dir.parents[1] / "config" / "skill_launcher"
    path = data_dir / "simulation_v1" / "acceptance.json"
    def accepted_for():
        return acceptance_snapshot(path)[1] if replay_sim else accepted_skills(path, data_dir)

    rows = _coverage_rows(data_dir, REGISTRY_V01, lambda mode: _graph_actions(config, mode), accepted_for)
    catalog = SkillCatalog.load(data_dir)
    groups = {s.domain: s.domain_name for s in catalog.skills.values()}
    edges = {
        (mapping["skill_id"], function_id)
        for mapping in _load(data_dir / "skill_function_mapping_120.json")
        for function_id in mapping.get("declared_v02_function_refs", [])
    }
    for _, diag in COMPOSITE_BATCHES.values():
        doc = _load(config / f"{diag}.diagnostics.json")
        edges.update(
            (skill_id, source["function_id"])
            for skill_id, workflow in doc["workflows"].items()
            for source in workflow["sources"].values()
        )
    if replay_sim:
        from .replay_sim import CLIENT_IDENTITY

        accepted = {row.skill_id for row in rows if row.simulation_verified}
        client_functions = {f["function_id"] for f in _load(data_dir / "function_proposals.json")
                            if f["scope"] == "client"}
        edges.update({(sid, CLIENT_IDENTITY) for sid, fid in edges
                      if sid in accepted and fid in client_functions})
    functions = {function_id for _, function_id in edges}
    if (any(skill_id not in catalog.skills for skill_id, _ in edges)
            or any(not isinstance(fid, str) or not fid or fid in catalog.skills for fid in functions)):
        raise CoverageError("invalid skill graph edge")
    nodes = [
        {"id": r.skill_id, "kind": "skill", "label": r.name, "group": r.domain,
         "type": r.skill_type, "verified": r.simulation_verified,
         "chat_callable": r.replay_launchable or r.live_launchable}
        for r in rows
    ]
    nodes.extend({"id": fid, "kind": "function", "label": fid} for fid in sorted(functions))
    if replay_sim:
        from . import igate_data

        groups[igate_data.DOMAIN] = "iGate mô phỏng"
        for sid, item in igate_data.catalog().items():
            fid = igate_data.function_id(sid)
            nodes.extend([
                {"id": sid, "kind": "skill", "label": item["name"], "group": igate_data.DOMAIN,
                 "type": igate_data.KIND, "verified": False, "chat_callable": False},
                {"id": fid, "kind": "function", "label": item["skill"]},
            ])
            edges.add((sid, fid))
    return {
        "format": "gateway-lm.skill-graph/v1",
        "groups": groups,
        "nodes": nodes,
        "edges": [{"source": sid, "target": fid} for sid, fid in sorted(edges)],
    }
