"""Review-only projection into Gateway_LM legacy SkillGraph relations.

No writes or runtime binding. This deliberately refuses proposed edges by
runtime default and does not call production SkillGraph / SkillDAG.
"""
from __future__ import annotations
from .catalog import SkillCatalog

def existing_v01_edges(catalog: SkillCatalog) -> list[dict]:
    """Export only the three already documented v0.1 edges for comparison."""
    return [{"source":r.source, "target":r.target, "type":r.type, "weight":r.weight}
            for r in catalog.relations if r.status == "EXISTING_V01"]

def candidate_edges_for_review(catalog: SkillCatalog) -> list[dict]:
    """Proposed diff; NOT a production merge or graph.edit approval."""
    return [{"source":r.source,"target":r.target,"type":r.type,
             "weight":r.weight,"status":"PROPOSED","reason":r.reason}
            for r in catalog.relations if r.status == "PROPOSED"]
