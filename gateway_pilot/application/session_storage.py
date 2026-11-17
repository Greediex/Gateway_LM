"""Trusted local READ persistence; callers supply paths/IDs outside HTTP.

Resume requires explicit operator session ID, authenticated case ID and matching
runtime context on the same OS boot. Jobs are never automatically replayed.
Facts retain TTL; cumulative budgets and original deadlines never restart.
Files contain scoped evidence (unencrypted), but never raw request text. History
exports only counts. A trusted local operator owns this directory and key.
"""
from __future__ import annotations

import copy
from collections import Counter
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import secrets
import stat
import tempfile
import time
from weakref import WeakKeyDictionary

from ..command_catalog.session import ReadSession
from ..core import PlanError
from ..graph_v3.checkpoint import EvidenceCheckpoint
from ..graph_v3.repair import P_MAX
from ..graph_v3.job_journal import ReadOnlyJobJournal


class SessionStorage:
    """Single-process local composition of existing signed READ stores."""

    def __init__(self, directory: Path, secret: bytes | None = None, *, clock=time.time):
        self.directory = Path(directory).absolute()
        if self.directory.is_symlink():
            raise PlanError("storage_directory_unsafe")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        info = self.directory.stat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise PlanError("storage_directory_unsafe")
        self.directory.chmod(0o700)
        self.secret = self._local_key() if secret is None else secret
        if not isinstance(self.secret, bytes) or len(self.secret) < 32:
            raise ValueError("storage_secret_minimum_32_bytes")
        if not callable(clock):
            raise ValueError("storage_clock_required")
        self.clock = clock
        self._sessions = WeakKeyDictionary()

    def _local_key(self) -> bytes:
        path = self.directory / ".session-key"
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(fd, "wb") as file:
                file.write(secrets.token_bytes(32))
                file.flush()
                os.fsync(file.fileno())
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        with os.fdopen(fd, "rb") as file:
            info = os.fstat(file.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or stat.S_IMODE(info.st_mode) != 0o600 or info.st_size != 32):
                raise PlanError("storage_key_unsafe")
            return file.read()

    @staticmethod
    def _session_key(session_id: str) -> str:
        if type(session_id) is not str or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", session_id) is None:
            raise PlanError("storage_operator_session_id_required")
        return hashlib.sha256(session_id.encode()).hexdigest()

    @staticmethod
    def _scope(request: str, goals) -> tuple[str, tuple[str, ...]]:
        if (type(request) is not str or not 0 < len(request) <= 4096
                or type(goals) not in (list, tuple) or not 0 < len(goals) <= 256
                or any(type(g) is not str for g in goals)):
            raise PlanError("storage_request_goals_invalid")
        return hashlib.sha256(request.encode()).hexdigest(), tuple(goals)

    def _path(self, sid: str, request: str, goals, suffix: str) -> Path:
        scope = hashlib.sha256(EvidenceCheckpoint._json([request, goals])).hexdigest()
        return self.directory / f"{sid}.{scope}.{suffix}.json"

    def bind(self, session: ReadSession, session_id: str) -> None:
        """Attach once; journal scope follows each execute(request, goals)."""
        if type(session) is not ReadSession:
            raise PlanError("storage_read_session_required")
        with session._lock:
            session._validate()
            sid = self._session_key(session_id)
            self._require_open(sid)
            existing = self._sessions.get(session)
            if existing is not None:
                if existing != sid:
                    raise PlanError("storage_session_binding_mismatch")
                return
            if session.runner.event_sink is not None:
                raise PlanError("storage_event_sink_already_bound")
            self._sessions[session] = sid

            def append(event):
                try:
                    session._validate()
                    request, goals = self._scope(session.runner.case["request"], session.runner.plans[-1].goals)
                    path = self._path(sid, request, goals, "journal")
                    journal_request = path.name.split(".")[1]
                    journal = ReadOnlyJobJournal(path, self.secret,
                                                max_events=10000)
                    # No exception/user output is copied into the durable audit reason.
                    row = dict(event, reason="read_step_terminal")
                    journal.append(session.runtime.registry, session.state, journal_request, goals, row)
                except Exception:
                    session.close()
                    raise
            session.runner.event_sink = append

    def _bound(self, session: ReadSession, session_id: str | None = None) -> str:
        sid = self._sessions.get(session)
        if sid is None or (session_id is not None and sid != self._session_key(session_id)):
            raise PlanError("storage_session_binding_mismatch")
        self._require_open(sid)
        session._validate()
        return sid

    @staticmethod
    def _budget(session: ReadSession) -> dict:
        runner = session.runner
        return {"created_at": session.created_at, "expires_at": session.expires_at,
                "started": runner.started, "deadline_s": runner.deadline_s,
                "max_calls": runner.max_calls, "max_plans": session._max_plans,
                "cost_budget": runner.cost_budget, "calls": runner.calls,
                "spent": runner.spent, "plans": len(runner.plans) + getattr(session, "_prior_plans", 0),
                "repairs": runner.repairs, "max_repairs": runner.max_repairs,
                "global_replans": runner.global_replans}

    def _write(self, path: Path, body: dict) -> None:
        mac = hmac.new(self.secret, EvidenceCheckpoint._json(body), hashlib.sha256).hexdigest()
        fd, temporary = tempfile.mkstemp(prefix=".session-", dir=self.directory)
        try:
            with os.fdopen(fd, "wb") as file:
                file.write(EvidenceCheckpoint._json({"body": body, "mac": mac}))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _read(self, path: Path) -> dict:
        try:
            if path.is_symlink() or path.stat().st_size > 8 * 1024 * 1024:
                raise PlanError("storage_file_unsafe")
            envelope = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(envelope, dict) or set(envelope) != {"body", "mac"}:
                raise ValueError("envelope")
            body, mac = envelope["body"], envelope["mac"]
            expected = hmac.new(self.secret, EvidenceCheckpoint._json(body), hashlib.sha256).hexdigest()
            if not isinstance(mac, str) or not hmac.compare_digest(expected, mac):
                raise PlanError("storage_signature_invalid")
            if not isinstance(body, dict) or body.get("version") != 1:
                raise ValueError("version")
            return body
        except PlanError:
            raise
        except (OSError, ValueError, TypeError, UnicodeError) as exc:
            raise PlanError("storage_unreadable") from exc

    def checkpoint(self, session: ReadSession, request: str, goals) -> int:
        """Persist a complete signed snapshot after a READ execution."""
        with session._lock:
            sid = self._bound(session)
            request, goals = self._scope(request, goals)
            if any(goal not in session.runtime.registry.ports for goal in goals):
                raise PlanError("storage_unknown_goal")
            with tempfile.TemporaryDirectory(prefix=".evidence-", dir=self.directory) as temp:
                checkpoint = EvidenceCheckpoint(Path(temp) / "facts.json", self.secret, clock=self.clock)
                count = checkpoint.save(session.runtime.registry, session.state, request, goals)
                evidence = json.loads(checkpoint.path.read_text())
            body = {"version": 1, "session": sid, "budget": self._budget(session),
                    "evidence": evidence, "saved_at": self.clock(), "facts": count,
                    "host_boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                    "execution": {"excluded": sorted(session.runner.excluded),
                                  "incomplete": session.runner.incomplete,
                                  "attempts": dict(session.state.attempts),
                                  "target_attempts": {target: dict(counts) for target, counts
                                                      in session.runner.target_attempts.items()}}}
            self._write(self.directory / f"{sid}.checkpoint.json", body)
            return count

    def restore(self, session: ReadSession, session_id: str, request: str, goals) -> int:
        """Restore matching facts and consumed budgets; never replay pending jobs."""
        with session._lock:
            try:
                sid = self._bound(session, session_id)
                request, goals = self._scope(request, goals)
                body = self._read(self.directory / f"{sid}.checkpoint.json")
                if (body.get("session") != sid or body["evidence"]["body"].get("binding")
                        != EvidenceCheckpoint._binding(session.runtime.registry, session.state, request, goals)):
                    raise PlanError("storage_context_mismatch")
                if body.get("host_boot_id") != Path("/proc/sys/kernel/random/boot_id").read_text().strip():
                    raise PlanError("storage_host_boot_mismatch")
                old, current = body["budget"], self._budget(session)
                if set(old) != set(current):
                    raise PlanError("storage_budget_invalid")
                for value in old.values():
                    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                        raise PlanError("storage_budget_invalid")
                for name in ("calls", "plans", "max_calls", "max_plans", "repairs", "max_repairs", "global_replans"):
                    if type(old[name]) is not int:
                        raise PlanError("storage_budget_invalid")
                if (old["max_repairs"] > 4096 or old["global_replans"] > P_MAX
                        or max(old["repairs"], current["repairs"]) > min(old["max_repairs"], current["max_repairs"]) + P_MAX):
                    raise PlanError("storage_repair_budget_invalid")
                execution = body["execution"]
                if (not isinstance(execution, dict)
                        or set(execution) != {"excluded", "attempts", "target_attempts", "incomplete"}
                        or type(execution["incomplete"]) is not bool
                        or not isinstance(execution["excluded"], list)
                        or len(execution["excluded"]) > len(session.runtime.registry.functions)
                        or any(type(fid) is not str or fid not in session.runtime.registry.functions
                               for fid in execution["excluded"])
                        or len(set(execution["excluded"])) != len(execution["excluded"])
                        or not isinstance(execution["target_attempts"], dict)
                        or len(execution["target_attempts"]) > 256):
                    raise PlanError("storage_execution_invalid")
                attempt_maps = [execution["attempts"]]
                for target, counts in execution["target_attempts"].items():
                    if type(target) is not str or not 0 < len(target) <= 256:
                        raise PlanError("storage_execution_invalid")
                    attempt_maps.append(counts)
                for counts in attempt_maps:
                    if (not isinstance(counts, dict) or len(counts) > len(session.runtime.registry.functions)
                            or any(fid not in session.runtime.registry.functions
                                   or type(count) is not int or not 0 <= count <= 4096
                                   for fid, count in counts.items())):
                        raise PlanError("storage_execution_invalid")
                now = session.runtime._clock()
                if (now < old["created_at"] or now < old["started"]
                        or now >= old["expires_at"] or now - old["started"] >= old["deadline_s"]):
                    raise PlanError("storage_session_expired")
                if (type(old["calls"]) is not int or type(old["plans"]) is not int
                        or type(old["max_calls"]) is not int or type(old["max_plans"]) is not int
                        or old["max_calls"] < 1 or old["max_plans"] < 1
                        or old["deadline_s"] <= 0 or old["cost_budget"] <= 0
                        or old["expires_at"] <= old["created_at"]
                        or max(old["calls"], current["calls"]) > min(old["max_calls"], current["max_calls"])
                        or max(old["spent"], current["spent"]) > min(old["cost_budget"], current["cost_budget"])
                        or max(old["plans"], current["plans"]) > min(old["max_plans"], current["max_plans"])):
                    raise PlanError("storage_budget_invalid")
                journals = list(self.directory.glob(f"{sid}.*.journal.json"))
                if len(journals) > 4096:
                    raise PlanError("storage_journal_budget_invalid")
                events = 0
                for path in journals:
                    try:
                        journal_binding = json.loads(path.read_text())["binding"]
                        journal_request = path.name.split(".")[1]
                        journal_goals = journal_binding["goals"]
                    except (OSError, ValueError, KeyError, TypeError) as exc:
                        raise PlanError("storage_journal_invalid") from exc
                    events += len(ReadOnlyJobJournal(path, self.secret, max_events=10000).recover(
                        session.runtime.registry, session.state, journal_request, journal_goals))
                if events != old["calls"]:
                    # A crash after a journaled READ but before its checkpoint
                    # must not grant that already consumed call budget again.
                    raise PlanError("storage_checkpoint_journal_count_mismatch")
                # Trial restore prevents any partially admitted facts on failure.
                candidate = copy.copy(session.state)
                candidate.evidence = []
                with tempfile.TemporaryDirectory(prefix=".evidence-", dir=self.directory) as temp:
                    path = Path(temp) / "facts.json"
                    path.write_bytes(EvidenceCheckpoint._json(body["evidence"]))
                    path.chmod(0o600)
                    count = EvidenceCheckpoint(path, self.secret, clock=self.clock).restore(
                        session.runtime.registry, candidate, request, goals)
                existing = {e["id"] for e in session.state.evidence}
                added = [e for e in candidate.evidence if e["id"] not in existing]
                for evidence in added:
                    session.state.evidence.append(evidence)
                    session.state.record(evidence)
                session.state.refresh_revision()
                session.runner.calls = max(current["calls"], old["calls"])
                session.runner.spent = max(current["spent"], old["spent"])
                session.runner.repairs = max(current["repairs"], old["repairs"])
                session.runner.max_repairs = min(current["max_repairs"], old["max_repairs"])
                session.runner.global_replans = max(current["global_replans"], old["global_replans"])
                session.runner.excluded.update(execution["excluded"])
                session.runner.incomplete = session.runner.incomplete or execution["incomplete"]
                for fid, attempts in execution["attempts"].items():
                    session.state.attempts[fid] = max(session.state.attempts[fid], attempts)
                for target, counts in execution["target_attempts"].items():
                    live = session.runner.target_attempts.setdefault(target, Counter())
                    for fid, attempts in counts.items():
                        live[fid] = max(live[fid], attempts)
                session.runner.max_calls = min(current["max_calls"], old["max_calls"])
                session.runner.cost_budget = min(current["cost_budget"], old["cost_budget"])
                session._max_plans = min(current["max_plans"], old["max_plans"])
                session._prior_plans = max(current["plans"], old["plans"]) - len(session.runner.plans)
                session.created_at = min(current["created_at"], old["created_at"])
                session.expires_at = min(current["expires_at"], old["expires_at"])
                deadline = min(current["started"] + current["deadline_s"], old["started"] + old["deadline_s"])
                session.runner.started = min(current["started"], old["started"])
                session.runner.deadline_s = deadline - session.runner.started
                session._validate()
                return len(added)
            except Exception as exc:
                session.close()
                if isinstance(exc, PlanError):
                    raise
                raise PlanError("storage_restore_invalid") from exc

    def describe(self, session_id: str) -> dict:
        """Authenticated local bootstrap hints; caller independently rebuilds runtime."""
        sid = self._session_key(session_id)
        self._require_open(sid)
        body = self._read(self.directory / f"{sid}.checkpoint.json")
        if body.get("session") != sid:
            raise PlanError("storage_session_binding_mismatch")
        binding = body["evidence"]["body"]["binding"]
        return {"case_id": binding["case_id"], "request_sha256": binding["request"],
                "goals": list(binding["goals"]), **body["budget"]}

    def _require_open(self, sid: str) -> None:
        path = self.directory / f"{sid}.closed.json"
        if path.exists() or path.is_symlink():
            self._read(path)
            raise PlanError("storage_session_closed")

    def close(self, session_id: str) -> None:
        """Durably revoke operator handle; preserve evidence/history for local audit."""
        sid = self._session_key(session_id)
        self._write(self.directory / f"{sid}.closed.json", {"version": 1, "session": sid, "closed": True})
        for session, bound in list(self._sessions.items()):
            if bound == sid:
                session.close()

    def history(self, *, limit: int = 20) -> list[dict]:
        """Bounded authenticated summaries; no target, network values or prompts."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("storage_history_limit")
        paths = sorted(self.directory.glob("*.checkpoint.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
        result = []
        for path in paths:
            body = self._read(path)
            result.append({"saved_at": body["saved_at"], "facts": body["facts"],
                           "calls": body["budget"]["calls"], "plans": body["budget"]["plans"],
                           "expires_at": body["budget"]["expires_at"],
                           "status": "CLOSED" if (self.directory / f"{body['session']}.closed.json").exists() else "SAVED"})
        return sorted(result, key=lambda row: row["saved_at"], reverse=True)
