"""HMAC-chained, atomic, local audit journal for *read-only* DAG steps.

This preserves execution history across process restarts but does not
automatically replay RUNNING nodes or provide exactly-once hardware side
effects. Use alongside EvidenceCheckpoint for fresh-fact restoration.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import tempfile
from pathlib import Path

from ..core import PlanError
from .checkpoint import EvidenceCheckpoint


class ReadOnlyJobJournal:
    VERSION = 1

    def __init__(self, path: Path, secret: bytes, *, max_events=100):
        if not isinstance(secret, bytes) or len(secret) < 32:
            raise ValueError("job_journal_secret_min_32_bytes")
        if type(max_events) is not int or not 1 <= max_events <= 10000:
            raise ValueError("invalid_journal_event_budget")
        self.path = Path(path)
        self.secret, self.max_events = secret, max_events

    @staticmethod
    def _json(obj):
        return json.dumps(
            obj, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False
        ).encode("utf-8")

    @classmethod
    def _binding(cls, registry, state, request, goals):
        bound = EvidenceCheckpoint._binding(registry, state, request, goals)
        # Do not persist raw user text. A private journal still contains case
        # identifiers/target scope and requires filesystem access control.
        bound["request_sha256"] = hashlib.sha256(
            bound.pop("request").encode("utf-8")
        ).hexdigest()
        return bound

    def _mac(self, binding, seq, event, previous):
        return hmac.new(
            self.secret,
            self._json({"binding": binding, "sequence": seq,
                        "event": event, "previous": previous}),
            hashlib.sha256,
        ).hexdigest()

    def recover(self, registry, state, request, goals):
        if not self.path.is_file():
            return []
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError, UnicodeError) as exc:
            raise PlanError("journal_unreadable") from exc
        if (not isinstance(envelope, dict)
                or set(envelope) != {"version", "binding", "entries"}
                or envelope.get("version") != self.VERSION
                or not isinstance(envelope.get("entries"), list)
                or len(envelope["entries"]) > self.max_events):
            raise PlanError("journal_invalid_envelope")
        expected_binding = self._binding(registry, state, request, goals)
        if envelope["binding"] != expected_binding:
            raise PlanError("journal_binding_mismatch")
        previous = ""
        events = []
        for seq, item in enumerate(envelope["entries"], 1):
            if (not isinstance(item, dict)
                    or set(item) != {"sequence", "event", "previous", "mac"}
                    or item["sequence"] != seq
                    or item["previous"] != previous
                    or not isinstance(item["mac"], str)
                    or not isinstance(item["event"], dict)
                    or set(item["event"]) != {"revision", "node", "state", "reason"}):
                raise PlanError("journal_invalid_entry")
            expected = self._mac(expected_binding, seq, item["event"], previous)
            if not hmac.compare_digest(expected, item["mac"]):
                raise PlanError("journal_signature_invalid")
            previous = item["mac"]
            events.append(copy.deepcopy(item["event"]))
        return events

    def append(self, registry, state, request, goals, event):
        if not isinstance(event, dict) or not {"revision", "node", "state", "reason"} <= set(event):
            raise PlanError("journal_invalid_runtime_event")
        revision = event["revision"]
        node = event["node"]
        status = getattr(event["state"], "value", event["state"])
        reason = event["reason"]
        if (type(revision) is not int or revision <= 0
                or not isinstance(node, str) or not 1 <= len(node) <= 160
                or not isinstance(status, str) or status not in {
                    "SUCCEEDED", "FAILED", "INCONCLUSIVE", "SKIPPED",
                }
                or not isinstance(reason, str)):
            raise PlanError("journal_invalid_runtime_event")
        row = {"revision": revision, "node": node, "state": status,
               "reason": reason[:200]}
        previous_rows = self.recover(registry, state, request, goals)
        if len(previous_rows) >= self.max_events:
            raise PlanError("journal_event_budget_exceeded")
        binding = self._binding(registry, state, request, goals)
        # A verified journal is rebuilt into a complete atomic envelope,
        # and every event MAC includes its predecessor. O(n), bounded.
        rows = []
        prev = ""
        for sequence, item in enumerate([*previous_rows, row], 1):
            mac = self._mac(binding, sequence, item, prev)
            rows.append({"sequence": sequence, "event": item,
                         "previous": prev, "mac": mac})
            prev = mac
        envelope = {"version": self.VERSION, "binding": binding,
                    "entries": rows}
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(prefix=".glm-journal-", dir=self.path.parent)
        try:
            os.chmod(temp, 0o600)
            with os.fdopen(fd, "wb") as file:
                file.write(self._json(envelope))
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, self.path)
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
        return len(rows)
