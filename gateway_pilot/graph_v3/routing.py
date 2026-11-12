"""Function-routing boundary: resolver output is a proposal, not executable authority.

A different retrieval/resolver implementation can be injected by trusted startup
code. All candidates must still belong to the typed Function Registry.
"""
from __future__ import annotations

from collections.abc import Callable

from ..core import PlanError
from .resolver import resolve


class FunctionRouter:
    """Build Contract 0 without executing tools or broadening capability ACLs."""

    def __init__(self, resolver: Callable | None = None):
        self._resolve = resolver if resolver is not None else resolve

    def route(self, registry, state, request: str, *, goals=(), method="gos"):
        contract = self._resolve(registry, state, request, goals=goals, method=method)
        if not isinstance(contract, dict):
            raise PlanError("router_invalid_contract")
        candidates = contract.get("function_candidates")
        if (not isinstance(candidates, list)
                or any(not isinstance(fid, str) or fid not in registry.functions
                       for fid in candidates)
                or len(candidates) != len(set(candidates))):
            raise PlanError("router_invalid_candidates")
        if contract.get("decision") in {"BLOCKED", "ASK_USER"} and candidates:
            raise PlanError("router_blocked_with_candidates")
        if not isinstance(contract.get("skill_context"), dict):
            raise PlanError("router_missing_skill_context")
        if set(contract["skill_context"]) != set(candidates):
            raise PlanError("router_skill_context_mismatch")
        if any(not set(registry.functions[fid].skills).intersection({sid})
               for fid, sid in contract["skill_context"].items()):
            raise PlanError("router_unknown_skill_context")
        return contract
