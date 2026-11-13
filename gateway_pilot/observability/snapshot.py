"""Immutable, short-lived snapshots issued only from verified CaseState facts."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Callable

from ..core import PlanError
from ..command_catalog.loader import canonical_bytes
from ..graph_v3.state import CaseState


@dataclass(frozen=True)
class VerifiedSnapshot:
    _payload: bytes
    _clock: Callable
    _context_valid: Callable

    @classmethod
    def from_state(cls, state: CaseState, ports, *, context_valid: Callable,
                   allow_replay: bool = False):
        if not isinstance(state, CaseState) or not callable(context_valid):
            raise PlanError("snapshot_requires_verified_state")
        now = state.clock()
        facts = {}
        for pid in ports:
            fact = state.fact(pid)
            if fact is None:
                continue
            source = fact.get("source", "")
            if not source.startswith("linux_client/") and not (allow_replay and source.startswith("synthetic_replay/")):
                continue
            expires = fact["_received_at"] + fact["ttl_s"] - fact.get("age_s", 0)
            if not now < expires:
                continue
            facts[pid] = {"evidence_id": fact["id"], "function_id": fact["function_id"],
                          "contract_digest": fact.get("contract_digest"), "source": source, "scope": fact["scope"],
                          "target": fact["target"], "observed_at": fact["observed_at"],
                          "value": fact["value"], "expires_at": expires}
        payload = {"generated_at": datetime.now(UTC).isoformat(), "issued_at": now,
                   "ports": list(ports), "facts": facts}
        return cls(canonical_bytes(payload), state.clock, context_valid)

    def export(self) -> dict:
        payload = json.loads(self._payload)
        try:
            valid = self._context_valid() is True
        except (OSError, ValueError, RuntimeError, PlanError, TimeoutError):
            valid = False
        now = self._clock()
        valid = valid and now >= payload["issued_at"]
        facts = {}
        if valid:
            for pid, row in payload["facts"].items():
                if now < row["expires_at"]:
                    row["expires_in_s"] = max(0, row.pop("expires_at")-now)
                    facts[pid] = row
        missing = sorted(set(payload["ports"])-facts.keys())
        ttl = min((row["expires_in_s"] for row in facts.values()), default=0)
        return {"generated_at": payload["generated_at"], "facts": facts,
                "expires_at": (datetime.now(UTC)+timedelta(seconds=ttl)).isoformat(), "missing_ports": missing,
                "expires_in_s": ttl,
                "context_valid": valid}
