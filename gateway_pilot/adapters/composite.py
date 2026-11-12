"""Explicit, fail-closed dispatch to multiple typed Function adapters.

This is a composition boundary, not a plugin loader or a generic tool API.
The assignment mapping must come from trusted startup configuration.
"""
from __future__ import annotations

from collections.abc import Mapping

from ..core import PlanError
from . import Adapter, PROBE_FAILED, PROBE_OK


class CompositeAdapter(Adapter):
    """Dispatch each registered Function ID to exactly one trusted adapter.

    Probe results are rechecked at execution time. A missing, failing or
    malformed probe makes the assigned Function unavailable. Unassigned
    Functions never leak from a backend's broader capability list.
    """

    name = "composite"

    def __init__(self, assignments: Mapping[str, Adapter]):
        if not isinstance(assignments, Mapping) or not assignments:
            raise ValueError("adapter_assignments_required")
        for function_id, adapter in assignments.items():
            if (not isinstance(function_id, str) or not function_id.strip()
                    or not isinstance(adapter, Adapter) or adapter is self):
                raise ValueError("invalid_adapter_assignment")
        self._assignments = dict(assignments)

    def probe(self) -> dict[str, str]:
        by_backend: dict[int, tuple[Adapter, list[str]]] = {}
        for function_id, adapter in self._assignments.items():
            key = id(adapter)
            if key not in by_backend:
                by_backend[key] = (adapter, [])
            by_backend[key][1].append(function_id)

        capabilities = {}
        for adapter, assigned in by_backend.values():
            try:
                advertised = adapter.probe()
            except (OSError, RuntimeError, ValueError, PlanError):
                advertised = {}
            if not isinstance(advertised, Mapping):
                advertised = {}
            for function_id in assigned:
                capabilities[function_id] = (
                    PROBE_OK if advertised.get(function_id) == PROBE_OK else PROBE_FAILED
                )
        return capabilities

    def call(self, function_id, arguments, state, case):
        # The existing gate rejects untyped or unprobed Function calls.
        self._check(function_id, arguments)
        return self._assignments[function_id].call(function_id, arguments, state, case)
