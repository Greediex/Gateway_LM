"""GATEWAY_DESIGN: in-memory conversation sessions that keep one Case across turns (C4, G23).

A session remembers the last Case: its request, workflow, target, the evidence
that was still verifiable, and any pending question. The next turn reuses the
gateway facts that are still fresh instead of measuring again. Client facts are
only carried when the target is the same device; a different device starts with
no client facts. Evidence keeps its original receipt time, so TTL is unchanged.
Nothing is persisted: a restarted process or an expired session starts a new Case.
"""
from __future__ import annotations

import copy
import time
import uuid
from dataclasses import dataclass, field

DEFAULT_TTL_S = 900


@dataclass
class Session:
    session_id: str
    created_at: float
    last_used: float
    environment: str | None = None
    request: str | None = None
    workflow: str | None = None
    route: str = "auto"
    target: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    boot_id: str | None = None
    config_version: str | None = None
    state_revision: int = 0
    pending_question: dict | None = None
    history: list = field(default_factory=list)
    turns: int = 0

    @property
    def status(self):
        return "WAITING_INPUT" if self.pending_question else ("ACTIVE" if self.request else "NEW")

    def reset_case(self):
        self.request = self.workflow = None
        self.route, self.target, self.evidence = "auto", {}, []
        self.boot_id = self.config_version = None
        self.state_revision, self.pending_question = 0, None

    def pending_device(self, message, devices):
        """The inventory device a reply names, when this session is waiting for a target."""
        if not (self.pending_question and self.pending_question.get("kind") == "target"):
            return None
        from .workflow import match_device, normalize
        return match_device(normalize(message), devices)

    def carry(self, replay):
        """A replay copy whose initial evidence includes this session's still-usable observations."""
        replay = dict(replay)
        if self.evidence:
            replay["initial_evidence"] = [*replay.get("initial_evidence", ()), *copy.deepcopy(self.evidence)]
        return replay

    def remember(self, result, *, request, route="auto"):
        """Store the Case after a diagnostic turn (requires diagnose(..., return_state=True))."""
        state = result.get("case_state")
        self.turns += 1
        self.request, self.workflow, self.route = request, result.get("workflow"), route
        self.target = copy.deepcopy(result.get("target") or {})
        if state is not None:
            self.boot_id, self.config_version = state.boot_id, state.config_version
            self.state_revision = state.state_revision
            kept = []
            for e in state.evidence:
                port = state.registry.ports.get(e.get("port"))
                if port is None or state.fact(e["port"], port) is not e:
                    continue  # only the current, verified observation per port is carried
                record = copy.deepcopy(e)
                if not str(record["id"]).startswith("s"):
                    record["id"] = f"s{self.turns}.{record['id']}"  # unique across turns
                kept.append(record)
            self.evidence = kept
        terminal = result.get("terminal", {})
        self.pending_question = None
        if result.get("case_status") == "NEEDS_INPUT":
            self.pending_question = {"kind": "target" if terminal.get("diagnosis") == "target_ambiguous" else "input",
                                     "request": request, "workflow": result.get("workflow")}
        self.history.append({"turn": self.turns, "request": request, "workflow": result.get("workflow"),
                             "case_status": result.get("case_status"), "diagnosis": terminal.get("diagnosis")})


class SessionStore:
    def __init__(self, *, ttl_s=DEFAULT_TTL_S, clock=time.monotonic):
        self.ttl_s, self.clock, self._sessions = ttl_s, clock, {}

    def get(self, session_id=None, *, environment=None):
        """Existing live session, or a new one when missing, expired or bound to another environment."""
        now = self.clock()
        for sid in [sid for sid, s in self._sessions.items() if now - s.last_used > self.ttl_s]:
            del self._sessions[sid]
        session = self._sessions.get(session_id) if isinstance(session_id, str) else None
        if session is None:
            session = Session(uuid.uuid4().hex, now, now, environment=environment)
            self._sessions[session.session_id] = session
        elif environment is not None and session.environment != environment:
            session.reset_case()
            session.environment = environment
        session.last_used = now
        return session
