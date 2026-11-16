"""Versioned, read-only design catalog for Gateway_LM Skill Graph expansion.

Do not confuse catalog existence with runtime readiness. Every imported
candidate has runtime_status=NOT_BOUND; the existing Registry/FeatureRegistry
and approved backend bindings remain the only execution authority.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from collections import Counter, defaultdict
from typing import Iterable
import json
import math

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "skill_expansion_v1"
KINDS = frozenset({"depends_on", "composes_with", "similar_to", "specializes",
                   "conflicts_with", "produces_for", "workflow", "alternative_to"})

class CatalogError(ValueError):
    pass

@dataclass(frozen=True)
class Skill:
    id: str
    name_vi: str
    domain: str
    domain_name: str
    priority: str
    catalog_status: str
    kind: str
    scope: str
    planned_backend: str
    notes: str
    source: str | None
    runtime_status: str

@dataclass(frozen=True)
class Relation:
    source: str
    target: str
    type: str
    status: str
    reason: str
    direction_note: str
    weight: float

class SkillCatalog:
    """Validates design data, but does not grant graph.edit or runtime permissions."""
    def __init__(self, skills: Iterable[Skill], relations: Iterable[Relation]):
        raw_skills = tuple(skills)
        self.skills = {s.id: s for s in raw_skills}
        self.relations = tuple(relations)
        self.validate(raw_skills)

    @classmethod
    def load(cls, data_dir: Path | str = DATA_DIR) -> "SkillCatalog":
        data_dir = Path(data_dir)
        def load_json(filename):
            with (data_dir / filename).open(encoding="utf-8") as file:
                return json.load(file)
        return cls((Skill(**row) for row in load_json("skills.json")),
                   (Relation(**row) for row in load_json("relations.json")))

    def validate(self, original_skills: tuple[Skill, ...] | None = None) -> None:
        if original_skills is not None and len(original_skills) != len(self.skills):
            raise CatalogError("Duplicate skill IDs")
        if not self.skills:
            raise CatalogError("Empty catalog")
        for skill in self.skills.values():
            if (not skill.id or not skill.name_vi or not skill.domain or
                skill.priority not in {"P0", "P1", "P2"} or
                skill.catalog_status not in {"EXISTING_V01", "PROPOSED"} or
                skill.runtime_status != "NOT_BOUND"):
                raise CatalogError(f"Invalid/unreviewed runtime skill contract: {skill.id}")
        seen: set[tuple[str, str, str]] = set()
        for r in self.relations:
            key=(r.source,r.target,r.type)
            if (r.type not in KINDS or r.status not in {"EXISTING_V01", "PROPOSED"} or
                r.source not in self.skills or r.target not in self.skills or
                r.source == r.target or not math.isfinite(r.weight) or r.weight <= 0):
                raise CatalogError(f"Invalid graph edge: {key}")
            if key in seen:
                raise CatalogError(f"Duplicate graph edge: {key}")
            seen.add(key)
            if r.status == "EXISTING_V01" and (self.skills[r.source].catalog_status != "EXISTING_V01" or
                self.skills[r.target].catalog_status != "EXISTING_V01"):
                raise CatalogError("Verified edge mentions proposed Skill")
        self._check_hard_dependency_cycles()

    def _check_hard_dependency_cycles(self) -> None:
        outgoing: dict[str,list[str]] = defaultdict(list)
        for r in self.relations:
            if r.type == "depends_on": outgoing[r.source].append(r.target)
        state: dict[str,int] = {}
        def visit(node: str):
            if state.get(node) == 1:
                raise CatalogError(f"Hard dependency cycle at {node}")
            if state.get(node) == 2: return
            state[node] = 1
            for target in outgoing[node]: visit(target)
            state[node] = 2
        for node in self.skills: visit(node)

    def summary(self) -> dict:
        return {
            "total_skills": len(self.skills), "total_relations": len(self.relations),
            "skills_by_priority": dict(sorted(Counter(s.priority for s in self.skills.values()).items())),
            "skills_by_status": dict(sorted(Counter(s.catalog_status for s in self.skills.values()).items())),
            "relations_by_status": dict(sorted(Counter(r.status for r in self.relations).items())),
            "relations_by_type": dict(sorted(Counter(r.type for r in self.relations).items())),
            "domains": len({s.domain for s in self.skills.values()}),
            "executable_skills_granted_by_package": 0,
        }

    def neighbors(self, skill_id: str, *, include_proposed: bool = False,
                  relation_types: set[str] | None = None) -> list[Relation]:
        if skill_id not in self.skills:
            raise KeyError(skill_id)
        return [r for r in self.relations
                if (r.source == skill_id or r.target == skill_id)
                and (include_proposed or r.status == "EXISTING_V01")
                and (relation_types is None or r.type in relation_types)]

    def hard_dependencies(self, skill_ids: Iterable[str], *, preview_proposed: bool = False) -> set[str]:
        """Dependency closure, never executable authorization.

        preview_proposed=True is for design reviews; it never changes runtime.
        Soft relations are never hard prerequisites.
        """
        chosen = set(skill_ids)
        if not chosen.issubset(self.skills):
            raise CatalogError(f"Unknown Skill IDs: {sorted(chosen - self.skills.keys())}")
        dependencies: dict[str,set[str]] = defaultdict(set)
        for relation in self.relations:
            if relation.type == "depends_on" and (preview_proposed or relation.status == "EXISTING_V01"):
                dependencies[relation.source].add(relation.target)
        result: set[str] = set()
        pending = list(sorted(chosen))
        while pending:
            sid = pending.pop()
            for dep in sorted(dependencies[sid]):
                if dep not in chosen and dep not in result:
                    result.add(dep)
                    pending.append(dep)
        return result

    def conflicts(self, skill_ids: Iterable[str], *, include_proposed: bool = False) -> list[Relation]:
        selected = set(skill_ids)
        return [r for r in self.relations
                if r.type == "conflicts_with" and r.source in selected and r.target in selected
                and (include_proposed or r.status == "EXISTING_V01")]

    def group(self, domain: str) -> list[Skill]:
        return sorted((s for s in self.skills.values() if s.domain == domain), key=lambda s:s.id)

    def export_graphviz_dot(self, *, skill_ids: Iterable[str] | None = None,
                            include_proposed: bool = False) -> str:
        selected = set(skill_ids) if skill_ids is not None else set(self.skills)
        invalid = selected - self.skills.keys()
        if invalid: raise CatalogError(f"Unknown skill IDs: {sorted(invalid)}")
        def q(value: str) -> str:
            return '"' + value.replace('\\','\\\\').replace('"','\\"').replace('\n',' ') + '"'
        lines = ["digraph GatewaySkillGraph {", '  rankdir=LR;',
                 '  graph [label="Proposal Skill Graph — NOT runtime-enabled", labelloc=t];',
                 '  node [shape=box, style="rounded,filled", fontname="DejaVu Sans"];']
        for sid in sorted(selected):
            s=self.skills[sid]
            color="#BFE6D2" if s.catalog_status == "EXISTING_V01" else "#EEF2F7"
            lines.append(f'  {q(sid)} [label={q(sid+" | "+s.name_vi)}, fillcolor={q(color)}];')
        for r in self.relations:
            if r.source in selected and r.target in selected and (include_proposed or r.status == "EXISTING_V01"):
                style = "solid" if r.status == "EXISTING_V01" else "dashed"
                arrow = "normal" if r.type in {"depends_on", "produces_for", "workflow", "specializes"} else "none"
                lines.append(f'  {q(r.source)} -> {q(r.target)} [label={q(r.type)}, style={q(style)}, arrowhead={q(arrow)}];')
        return "\n".join(lines+["}",""])
