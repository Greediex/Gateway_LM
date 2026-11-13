"""Opt-in HMAC-authenticated evidence checkpoint for trusted read-only hosts.

This resumes *facts*, not RUNNING nodes or WRITE actions. Files are local,
tamper-evident but not encrypted. The signing key must come from trusted
runtime configuration and must never be accepted through the HTTP API.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import math
import os
import tempfile
import time
from pathlib import Path

from ..core import PlanError


class EvidenceCheckpoint:
    VERSION = 1
    STORED_FIELDS = (
        "id", "function_id", "port", "scope", "target", "source",
        "observed_at", "status", "value", "age_s", "ttl_s",
    )

    def __init__(self, path: Path, secret: bytes, *, clock=time.time):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("checkpoint_secret_minimum_32_bytes")
        if not callable(clock):
            raise ValueError("checkpoint_clock_required")
        self.path = Path(path)
        self.secret = secret
        self.clock = clock

    @staticmethod
    def _json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False).encode("utf-8")

    @classmethod
    def _fingerprint(cls, registry):
        # Both Function interfaces and Port contracts must match the saved run.
        ports = {name: vars(port) for name, port in sorted(registry.ports.items())}
        functions = {fid: f.digest() for fid, f in sorted(registry.functions.items())}
        return hashlib.sha256(cls._json({"ports": ports, "functions": functions})).hexdigest()

    @classmethod
    def _binding(cls, registry, state, request, goals):
        binding = {
            "request": request,
            "goals": list(goals),
            "registry": cls._fingerprint(registry),
            "case_id": state.case_id,
            "gateway_id": state.gateway_id,
            "target": copy.deepcopy(state.target),
            "boot_id": state.boot_id,
            "config_version": state.config_version,
            "capabilities": sorted(state.capabilities),
            "permissions": sorted(state.permissions),
        }
        if getattr(registry, "contract_format", None) == "v0.2":
            runtime = getattr(registry, "runtime", None)
            if runtime is None:
                raise PlanError("checkpoint_v02_runtime_required")
            binding["v02_runtime"] = runtime.checkpoint_binding()
        return binding

    @classmethod
    def _stored_fields(cls, registry):
        if getattr(registry, "contract_format", None) == "v0.2":
            return cls.STORED_FIELDS + ("contract_digest", "function_version",
                                        "metadata_function_digest", "environment_id")
        return cls.STORED_FIELDS

    def save(self, registry, state, request: str, goals):
        if not isinstance(request, str) or not goals:
            raise ValueError("checkpoint_requires_request_and_goals")
        now = self.clock()
        if not isinstance(now, (int, float)) or not math.isfinite(now):
            raise PlanError("checkpoint_invalid_clock")
        evidence = []
        for e in state.evidence:
            port = registry.ports.get(e.get("port"))
            function = registry.functions.get(e.get("function_id"))
            if (port is None or function is None or port.untrusted_text
                    or port.name not in function.outputs or not state.usable(e, port)):
                continue
            delta = max(0.0, state.clock() - e.get("_received_at", state.clock()))
            age = e.get("age_s", 0) + delta
            if not math.isfinite(age) or age >= e["ttl_s"]:
                continue
            row = {key: copy.deepcopy(e.get(key)) for key in self._stored_fields(registry)}
            row["age_s"] = age
            evidence.append(row)
        body = {
            "version": self.VERSION,
            "saved_at": now,
            "binding": self._binding(registry, state, request, goals),
            "evidence": evidence,
        }
        mac = hmac.new(self.secret, self._json(body), hashlib.sha256).hexdigest()
        envelope = {"body": body, "mac": mac}
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=".glm-checkpoint-", dir=self.path.parent)
        try:
            os.chmod(temporary, 0o600)
            with os.fdopen(fd, "wb") as fp:
                fp.write(self._json(envelope))
                fp.flush()
                os.fsync(fp.fileno())
            os.replace(temporary, self.path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return len(evidence)

    def restore(self, registry, state, request: str, goals):
        """Load only matching, still-fresh facts; no call budgets or jobs resume."""
        if not self.path.is_file():
            return 0
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, ValueError) as exc:
            raise PlanError("checkpoint_unreadable") from exc
        if not isinstance(envelope, dict) or set(envelope) != {"body", "mac"}:
            raise PlanError("checkpoint_invalid_format")
        body = envelope["body"]
        if not isinstance(body, dict) or not isinstance(envelope["mac"], str):
            raise PlanError("checkpoint_invalid_format")
        try:
            expected = hmac.new(self.secret, self._json(body), hashlib.sha256).hexdigest()
        except (TypeError, ValueError) as exc:
            raise PlanError("checkpoint_invalid_format") from exc
        if not hmac.compare_digest(expected, envelope["mac"]):
            raise PlanError("checkpoint_signature_invalid")
        if body.get("version") != self.VERSION:
            raise PlanError("checkpoint_version_mismatch")
        if body.get("binding") != self._binding(registry, state, request, goals):
            # Different boot/config/target/ACL/registry/request: never reuse.
            return 0
        now = self.clock()
        saved_at = body.get("saved_at")
        if (not isinstance(saved_at, (int, float)) or not math.isfinite(saved_at)
                or not isinstance(now, (int, float)) or not math.isfinite(now)):
            raise PlanError("checkpoint_invalid_clock")
        elapsed = now - saved_at
        if elapsed < -1:
            raise PlanError("checkpoint_clock_rollback")
        elapsed = max(0.0, elapsed)
        rows = body.get("evidence")
        if not isinstance(rows, list) or len(rows) > 1000:
            raise PlanError("checkpoint_invalid_evidence")
        pending = []
        seen = {e["id"] for e in state.evidence}
        from .contracts import validate
        for item in rows:
            if not isinstance(item, dict) or set(item) != set(self._stored_fields(registry)):
                raise PlanError("checkpoint_invalid_evidence")
            port = registry.ports.get(item["port"])
            function = registry.functions.get(item["function_id"])
            if (port is None or function is None or port.untrusted_text
                    or item["port"] not in function.outputs
                    or item["scope"] != port.scope or item["status"] != "OK"
                    or not isinstance(item["source"], str)
                    or not item["source"].startswith(port.provenance)
                    or not validate(item["value"], port.schema)
                    or not isinstance(item["id"], str) or not item["id"]
                    or item["id"] in seen):
                raise PlanError("checkpoint_evidence_contract_invalid")
            seen.add(item["id"])
            age, ttl = item["age_s"], item["ttl_s"]
            if (type(age) not in (int, float) or type(ttl) not in (int, float)
                    or not math.isfinite(age) or not math.isfinite(ttl)
                    or age < 0 or ttl <= 0):
                raise PlanError("checkpoint_invalid_freshness")
            if age + elapsed >= ttl:
                continue
            e = copy.deepcopy(item)
            e["age_s"] = age + elapsed
            pending.append(e)
        if getattr(registry, "contract_format", None) == "v0.2":
            candidate = copy.copy(state)
            candidate.evidence = copy.deepcopy(state.evidence)
            trial = copy.deepcopy(pending)
            for e in trial:
                candidate.evidence.append(e)
                candidate.record(e)
            if any(not candidate.usable(e, registry.ports[e["port"]]) for e in trial):
                raise PlanError("checkpoint_evidence_unusable")
        # Restore after all contract-shape checks: failures do not partially
        # mutate CaseState. CaseState itself verifies target/scope/freshness.
        for e in pending:
            state.evidence.append(e)
            state.record(e)
        for e in pending:
            if not state.usable(e, registry.ports[e["port"]]):
                raise PlanError("checkpoint_evidence_unusable")
        state.refresh_revision()
        return len(pending)
