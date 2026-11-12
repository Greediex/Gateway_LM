"""Disabled-by-default, approval-bound WRITE transaction contract.

No router driver is shipped. Only an explicitly supplied, trusted Adapter can
apply changes. Requests never originate from the LLM/HTTP path. The pilot uses
durable one-time approval nonces and verifies read-back or rollback.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import sqlite3
import time
import uuid
from pathlib import Path

from ..core import PlanError
from .contracts import validate
from .write_outbox import DurableWriteOutbox


def canonical(obj):
    try:
        data = json.dumps(
            obj, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PlanError("write_non_json_payload") from exc
    if len(data) > 8192:
        raise PlanError("write_payload_too_large")
    return data


class ApprovalAuthority:
    """Only trusted authorization code receives the signing key."""

    def __init__(self, secret: bytes, *, clock=time.time):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("write_approval_secret_min_32_bytes")
        if not callable(clock):
            raise ValueError("write_approval_clock_required")
        self.secret, self.clock = secret, clock

    def issue(self, *, function_id, arguments, target, revision, operator,
              ttl_seconds=60):
        if (any(not isinstance(x, str) or not 1 <= len(x) <= 128
                for x in (function_id, target, revision, operator))
                or not isinstance(arguments, dict)
                or type(ttl_seconds) is not int or not 1 <= ttl_seconds <= 300):
            raise ValueError("invalid_write_approval_request")
        created = self.clock()
        if not math.isfinite(created):
            raise ValueError("write_approval_clock_invalid")
        payload = {
            "function_id": function_id,
            "arguments": arguments,
            "target": target,
            "revision": revision,
            "operator": operator,
            "nonce": uuid.uuid4().hex,
            "issued_at": created,
            "expires_at": created + ttl_seconds,
        }
        signature = hmac.new(self.secret, canonical(payload), hashlib.sha256).hexdigest()
        return {"payload": payload, "signature": signature}

    def verify(self, token):
        if not isinstance(token, dict) or set(token) != {"payload", "signature"}:
            raise PlanError("invalid_write_approval_format")
        payload = token["payload"]
        if not isinstance(payload, dict) or set(payload) != {
            "function_id", "arguments", "target", "revision",
            "operator", "nonce", "issued_at", "expires_at"
        } or not isinstance(token["signature"], str):
            raise PlanError("invalid_write_approval_format")
        expected = hmac.new(self.secret, canonical(payload), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, token["signature"]):
            raise PlanError("invalid_write_approval_signature")
        now = self.clock()
        if (not isinstance(now, (int, float)) or not math.isfinite(now)
                or type(payload["issued_at"]) not in (int, float)
                or type(payload["expires_at"]) not in (int, float)
                or not math.isfinite(payload["issued_at"])
                or not math.isfinite(payload["expires_at"])
                or now < payload["issued_at"] - 1
                or now >= payload["expires_at"]
                or payload["expires_at"] - payload["issued_at"] > 300):
            raise PlanError("write_approval_expired")
        if not isinstance(payload["nonce"], str) or len(payload["nonce"]) != 32:
            raise PlanError("invalid_write_nonce")
        return payload


class DurableApprovalLedger:
    """SQLite nonce consumption. One-time approvals survive process restarts."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def consume(self, nonce, signature):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        # Directory/key path comes from trusted host config, never HTTP input.
        try:
            with sqlite3.connect(self.path, timeout=3, isolation_level=None) as db:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA synchronous=FULL")
                db.execute(
                    "CREATE TABLE IF NOT EXISTS used_approvals "
                    "(nonce TEXT PRIMARY KEY, signature TEXT NOT NULL)"
                )
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute("INSERT INTO used_approvals VALUES (?, ?)",
                               (nonce, signature))
                except sqlite3.IntegrityError as exc:
                    db.execute("ROLLBACK")
                    raise PlanError("write_approval_already_used") from exc
                db.execute("COMMIT")
            os.chmod(self.path, 0o600)
        except sqlite3.Error as exc:
            raise PlanError("write_approval_ledger_unavailable") from exc


class SafeWriteTransaction:
    """Isolated opt-in gateway WRITE executor with snapshot/preview/readback.

    Driver contract: probe(function_id) -> bool; snapshot() -> JSON object;
    preview(function_id, args, snapshot) -> desired JSON object;
    apply(function_id, args) -> None; readback() -> JSON object;
    rollback(snapshot) -> None.

    `preview` must be side-effect free and `apply` idempotent under the
    driver's own device-level protection. No arbitrary command interface.
    """

    def __init__(self, registry, adapter, authority: ApprovalAuthority,
                 ledger: DurableApprovalLedger, *, allowlist=(), enabled=False,
                 outbox=None):
        if (type(enabled) is not bool or not isinstance(authority, ApprovalAuthority)
                or not isinstance(ledger, DurableApprovalLedger)
                or not all(callable(getattr(adapter, name, None)) for name in (
                    "probe", "snapshot", "preview", "apply", "readback", "rollback"
                ))):
            raise ValueError("write_requires_trusted_driver")
        if not isinstance(allowlist, (list, tuple, set, frozenset)) or any(
            not isinstance(x, str) for x in allowlist
        ):
            raise ValueError("invalid_write_allowlist")
        self.registry, self.adapter = registry, adapter
        self.authority, self.ledger = authority, ledger
        if outbox is not None and not isinstance(outbox, DurableWriteOutbox):
            raise ValueError("write_outbox_must_be_trusted")
        self.allowlist, self.enabled = frozenset(allowlist), enabled
        self.outbox = outbox

    def commit(self, token, *, target, revision, operator,
               permissions=frozenset(), capabilities=frozenset()):
        if not self.enabled:
            raise PlanError("write_transactions_disabled")
        payload = self.authority.verify(token)
        if (any(not isinstance(x, str) for x in (target, revision, operator))
                or any(payload[x] != value for x, value in (
                    ("target", target), ("revision", revision),
                    ("operator", operator)
                ))):
            raise PlanError("write_approval_context_mismatch")
        fid = payload["function_id"]
        f = self.registry.functions.get(fid)
        if (fid not in self.allowlist or f is None or f.risk != "WRITE"
                or f.scope != "gateway"
                or f.permission not in permissions or fid not in capabilities):
            raise PlanError("write_function_not_authorized")
        if getattr(self.registry, "contract_format", None) == "v0.1" and (
            getattr(f, "status", None) != "PROBED_OK"
        ):
            raise PlanError("write_function_not_firmware_probed")
        if not isinstance(payload["arguments"], dict) or not validate(
            payload["arguments"], f.arguments_schema
        ):
            raise PlanError("write_arguments_schema_invalid")
        try:
            probed = self.adapter.probe(fid)
        except (OSError, RuntimeError, ValueError, TimeoutError):
            probed = False
        if probed is not True:
            raise PlanError("write_backend_not_probed")
        self.ledger.consume(payload["nonce"], token["signature"])
        # No approval may be reused even when snapshot/preview/apply fails.
        try:
            before = self.adapter.snapshot()
            desired = self.adapter.preview(
                fid, dict(payload["arguments"]), before
            )
            canonical(before)
            canonical(desired)
            if not isinstance(before, dict) or not isinstance(desired, dict):
                raise PlanError("write_snapshot_invalid")
        except (OSError, RuntimeError, ValueError, TimeoutError) as exc:
            raise PlanError("write_prepare_failed") from exc
        if self.outbox is not None:
            self.outbox.prepare(
                nonce=payload["nonce"], target=target, revision=revision,
                function_id=fid, before=before, desired=desired,
            )
            # IN_FLIGHT is fsynced before the real adapter.apply. A crash
            # after this transition leaves an IN-DOUBT receipt to reconcile,
            # never a retry token.
            self.outbox.transition(
                payload["nonce"], from_status="PREPARED", to_status="IN_FLIGHT"
            )
        try:
            self.adapter.apply(fid, dict(payload["arguments"]))
            actual = self.adapter.readback()
            if canonical(actual) != canonical(desired):
                raise PlanError("write_readback_mismatch")
        except (OSError, RuntimeError, ValueError, TimeoutError, PlanError) as exc:
            try:
                self.adapter.rollback(before)
                recovered = self.adapter.readback()
                if canonical(recovered) != canonical(before):
                    raise PlanError("write_rollback_not_verified")
            except (OSError, RuntimeError, ValueError, TimeoutError, PlanError):
                if self.outbox is not None:
                    self.outbox.transition(
                        payload["nonce"], from_status="IN_FLIGHT",
                        to_status="MANUAL_RECOVERY_REQUIRED",
                    )
                return {
                    "status": "MANUAL_RECOVERY_REQUIRED", "function_id": fid,
                    "reason": "rollback_or_postrollback_verification_failed",
                    "evidence": "NO_VERIFIED_POSTCONDITION",
                }
            if self.outbox is not None:
                self.outbox.transition(
                    payload["nonce"], from_status="IN_FLIGHT", to_status="ROLLED_BACK"
                )
            return {
                "status": "ROLLED_BACK", "function_id": fid,
                "reason": type(exc).__name__,
                "evidence": "ROLLBACK_READBACK_VERIFIED",
            }
        if self.outbox is not None:
            self.outbox.transition(
                payload["nonce"], from_status="IN_FLIGHT", to_status="COMMITTED"
            )
        return {
            "status": "COMMITTED", "function_id": fid,
            "reason": "postcondition_readback_verified",
            "evidence": "DEVICE_READBACK_MATCHED_PREVIEW",
        }
