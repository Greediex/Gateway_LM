"""Plan compilation boundary: typed candidates are allowlisted before DAG search."""
from __future__ import annotations

from ..core import PlanError
from .planner import Compiler


class FunctionPlanner:
    """Compile a restricted Function DAG from an already gated Contract 0."""

    def compile(self, registry, state, contract: dict):
        candidates = contract["function_candidates"]
        if not candidates:
            raise PlanError("planner_requires_candidates")
        unknown = set(candidates) - set(registry.functions)
        if unknown:
            raise PlanError("planner_unknown_candidates")
        if contract.get("decision") in {"BLOCKED", "ASK_USER"}:
            raise PlanError("planner_forbidden_contract")
        revision = contract["plan_revision"]
        if not isinstance(revision, int) or revision < 1:
            raise PlanError("planner_invalid_revision")
        return Compiler(
            registry,
            excluded=set(registry.functions) - set(candidates),
        ).compile(
            (), state, requested=candidates, revision=revision,
            skill_context=contract["skill_context"],
        )
