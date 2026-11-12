"""Conservative, data-driven decomposition of *read-only* network questions.

A clause is executable only when it uniquely names a declared output port via
the trusted aliases manifest. This is not an open-ended LLM planner: unknown,
ambiguous or write-related clauses block the *entire* compound request.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ..core import ROOT, PlanError, read_json
from ..workflow import CHANGE_REQUEST, normalize


DEFAULT_ALIASES = ROOT / "data/goal_aliases_v01.json"
SPLIT = re.compile(r"\s*(?:[,;]|\b(?:va|and|dong thoi)\b)\s*")


@dataclass(frozen=True)
class GoalDecomposition:
    decision: str
    goals: tuple[str, ...]
    clauses: tuple[str, ...]
    unresolved: tuple[str, ...] = ()
    reason: str = ""


class TaskDecomposer:
    """Produce a bounded set of registered measurement goals, never Functions."""

    def __init__(self, registry, *, manifest: Path = DEFAULT_ALIASES, max_clauses=6):
        if type(max_clauses) is not int or not 2 <= max_clauses <= 12:
            raise ValueError("invalid_decomposition_limit")
        self.registry, self.max_clauses = registry, max_clauses
        data = read_json(manifest)
        if not isinstance(data, dict) or set(data) != {"version", "aliases", "unsafe_phrases"}:
            raise PlanError("invalid_goal_alias_manifest")
        if data["version"] != "1.0" or not isinstance(data["aliases"], dict):
            raise PlanError("invalid_goal_alias_version")
        if not isinstance(data["unsafe_phrases"], list) or not data["unsafe_phrases"]:
            raise PlanError("invalid_unsafe_phrases")
        self.unsafe = self._phrases(data["unsafe_phrases"])
        self.aliases = {}
        ownership = {}
        for port, aliases in data["aliases"].items():
            # A manifest may contain aliases for a broader Registry revision.
            # It must never create or execute an unknown output port.
            if port not in registry.ports:
                continue
            if not isinstance(aliases, list) or not aliases:
                raise PlanError("invalid_goal_aliases:" + port)
            for alias in (*aliases, port):
                normalized = normalize(alias)
                if not normalized or len(normalized) > 128:
                    raise PlanError("invalid_goal_alias:" + port)
                if normalized in ownership and ownership[normalized] != port:
                    raise PlanError("ambiguous_goal_alias:" + normalized)
                ownership[normalized] = port
                self.aliases.setdefault(port, set()).add(normalized)
        # All port names are always valid explicit names; no hand-edited Python
        # dictionary is needed when a new Function/Port is registered.
        for port in registry.ports:
            normalized = normalize(port)
            if normalized in ownership and ownership[normalized] != port:
                raise PlanError("ambiguous_port_name:" + normalized)
            self.aliases.setdefault(port, set()).add(normalized)

    @staticmethod
    def _phrases(rows):
        if any(not isinstance(x, str) or not normalize(x) or len(x) > 128 for x in rows):
            raise PlanError("invalid_unsafe_phrase")
        return tuple(dict.fromkeys(normalize(x) for x in rows))

    @staticmethod
    def _contains(clause: str, phrase: str) -> bool:
        return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", clause) is not None

    def decompose(self, request: str) -> GoalDecomposition:
        if not isinstance(request, str) or not request.strip() or len(request) > 2000:
            raise ValueError("invalid_decomposition_request")
        normalized = normalize(request)
        clauses = tuple(s.strip() for s in SPLIT.split(normalized))
        if len(clauses) < 2:
            return GoalDecomposition("NOT_APPLICABLE", (), clauses, reason="single_intent")
        if len(clauses) > self.max_clauses or any(not c for c in clauses):
            return GoalDecomposition("NEEDS_INPUT", (), clauses,
                                     reason="invalid_compound_request")
        # Read-only pilot: never partially execute a request containing a
        # requested configuration or reboot, even if other clauses are benign.
        if re.search(CHANGE_REQUEST, normalized) or any(
            self._contains(normalized, phrase) for phrase in self.unsafe
        ):
            return GoalDecomposition("BLOCKED", (), clauses, reason="write_intent_in_compound_request")
        resolved, unresolved = [], []
        for clause in clauses:
            matches = {port for port, names in self.aliases.items()
                       if any(self._contains(clause, name) for name in names)}
            if len(matches) == 1:
                resolved.append(next(iter(matches)))
            else:
                unresolved.append(clause)
        if unresolved:
            return GoalDecomposition("NEEDS_INPUT", (), clauses, tuple(unresolved),
                                     "ambiguous_or_unsupported_clause")
        return GoalDecomposition("READY", tuple(dict.fromkeys(resolved)), clauses,
                                 reason="all_clauses_mapped_to_registered_ports")
