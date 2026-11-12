"""Crash-safe *in-doubt* WRITE receipts, never automatic re-application.

A durable SQLite outbox records only hashes of before/desired states.
If a process crashes after APPLY began, firmware reconciliation is mandatory;
the application must NOT re-issue the same change without a new approval.
This is at-most-once admission, NOT exactly-once device-side execution.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from pathlib import Path

from ..core import PlanError


def _digest(obj):
    from .change_transaction import canonical
    return hashlib.sha256(canonical(obj)).hexdigest()


class DurableWriteOutbox:
    TERMINAL = {"COMMITTED", "ROLLED_BACK", "COMMITTED_OBSERVED",
                "NOT_APPLIED_OBSERVED", "MANUAL_RECOVERY_REQUIRED"}

    def __init__(self, path: Path):
        self.path = Path(path)

    def _open(self):
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            db.execute(
                "CREATE TABLE IF NOT EXISTS write_outbox ("
                "nonce TEXT PRIMARY KEY, target TEXT NOT NULL, revision TEXT NOT NULL,"
                "function_id TEXT NOT NULL, before_hash TEXT NOT NULL,"
                "desired_hash TEXT NOT NULL, status TEXT NOT NULL)"
            )
            os.chmod(self.path, 0o600)
            return db
        except Exception:
            db.close()
            raise

    def prepare(self, *, nonce, target, revision, function_id, before, desired):
        if any(not isinstance(x, str) or not 1 <= len(x) <= 128
               for x in (nonce, target, revision, function_id)):
            raise PlanError("outbox_invalid_metadata")
        old = _digest(before)
        new = _digest(desired)
        try:
            with self._open() as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    db.execute(
                        "INSERT INTO write_outbox VALUES (?,?,?,?,?,?,?)",
                        (nonce, target, revision, function_id, old, new, "PREPARED")
                    )
                except sqlite3.IntegrityError as exc:
                    raise PlanError("outbox_duplicate_nonce") from exc
        except sqlite3.Error as exc:
            raise PlanError("outbox_unavailable") from exc

    def transition(self, nonce, *, from_status, to_status):
        allowed = {
            ("PREPARED", "IN_FLIGHT"),
            ("IN_FLIGHT", "COMMITTED"), ("IN_FLIGHT", "ROLLED_BACK"),
            ("IN_FLIGHT", "MANUAL_RECOVERY_REQUIRED"),
            ("IN_FLIGHT", "COMMITTED_OBSERVED"),
            ("IN_FLIGHT", "NOT_APPLIED_OBSERVED"),
        }
        if (from_status, to_status) not in allowed:
            raise PlanError("outbox_invalid_transition")
        try:
            with self._open() as db:
                db.execute("BEGIN IMMEDIATE")
                result = db.execute(
                    "UPDATE write_outbox SET status=? "
                    "WHERE nonce=? AND status=?",
                    (to_status, nonce, from_status),
                )
                if result.rowcount != 1:
                    raise PlanError("outbox_stale_or_missing_nonce")
        except sqlite3.Error as exc:
            raise PlanError("outbox_unavailable") from exc

    def inspect(self, nonce):
        try:
            with self._open() as db:
                row = db.execute(
                    "SELECT target,revision,function_id,before_hash,"
                    "desired_hash,status FROM write_outbox WHERE nonce=?",
                    (nonce,),
                ).fetchone()
        except sqlite3.Error as exc:
            raise PlanError("outbox_unavailable") from exc
        if row is None:
            raise PlanError("outbox_unknown_nonce")
        keys = ("target", "revision", "function_id",
                "before_hash", "desired_hash", "status")
        return dict(zip(keys, row))

    def reconcile(self, nonce, *, driver, target, revision):
        """Read-back ONLY; never call apply() on an uncertain device state."""
        row = self.inspect(nonce)
        if row["target"] != target or row["revision"] != revision:
            raise PlanError("outbox_reconcile_context_mismatch")
        if row["status"] != "IN_FLIGHT":
            raise PlanError("outbox_reconcile_requires_inflight")
        if not callable(getattr(driver, "readback", None)):
            raise PlanError("outbox_readback_required")
        try:
            actual_hash = _digest(driver.readback())
        except (OSError, RuntimeError, ValueError, TimeoutError, PlanError):
            return {"status": "UNKNOWN", "reason": "readback_unavailable"}
        if actual_hash == row["desired_hash"]:
            status = "COMMITTED_OBSERVED"
        elif actual_hash == row["before_hash"]:
            status = "NOT_APPLIED_OBSERVED"
        else:
            status = "MANUAL_RECOVERY_REQUIRED"
        self.transition(nonce, from_status="IN_FLIGHT", to_status=status)
        return {"status": status, "reason": "readback_hash_comparison_only"}
