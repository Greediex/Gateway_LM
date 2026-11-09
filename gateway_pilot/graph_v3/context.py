"""WF-067 bounded context built from compiler-verified function bundles."""

from ..core import PlanError
from ..rag import json_bytes
from .planner import Compiler
from .skilldag import check_skills


def retrieve_context(registry, state, request, goals, *, k=3, max_bytes=1800, method="gos"):
    if type(k) is not int or not 1 <= k <= 8 or type(max_bytes) is not int or not 2 <= max_bytes <= 32_000:
        raise ValueError("Invalid skill context budget")
    ranked = registry.retrieve(request, goals, state, k=min(24, max(1, len(registry.functions))), method=method)
    bundles, skipped = [], {}
    for fid in ranked["functions"] if ranked["lexical_match"] else ():
        if len(bundles) >= k or ranked["scores"].get("f:" + fid, 0) <= 0:
            break
        try:
            plan = Compiler(registry).compile([], state, requested=[fid])
        except PlanError as exc:
            skipped[fid] = str(exc)
            continue
        ordered = plan.topological()
        if not ordered:
            continue
        check = check_skills(registry.gs, dict.fromkeys(plan.nodes[node].skill_context for node in ordered))
        if check["conflicts"]:
            skipped[fid] = "skilldag_conflict"
            continue
        bundle = {
            "root": fid,
            "skills": [{"id": sid, "name": registry.skills[sid]["name"]} for sid in check["expanded"]],
            "functions": [
                {"id": node, "description": registry.functions[node].description,
                 "input_ports": sorted(plan.nodes[node].bindings),
                 "output_ports": sorted(registry.functions[node].outputs)}
                for node in ordered
            ],
        }
        if json_bytes([*bundles, bundle]) <= max_bytes:
            bundles.append(bundle)
        else:
            skipped[fid] = "context_budget"
    return {"workflow_id": "WF-067", "bundles": bundles, "context_bytes": json_bytes(bundles),
            "skipped": skipped}
