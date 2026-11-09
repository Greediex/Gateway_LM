"""SQLite-backed replay for approved QoS changes and timed access policies."""

import json
import sqlite3
from contextlib import contextmanager
from uuid import uuid4


class OperationDenied(ValueError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS devices (id TEXT PRIMARY KEY, identity TEXT NOT NULL, qos TEXT);
CREATE TABLE IF NOT EXISTS grants (
    actor TEXT, scope TEXT, target TEXT, expires INTEGER NOT NULL, PRIMARY KEY(actor, scope, target)
);
CREATE TABLE IF NOT EXISTS config (id INTEGER PRIMARY KEY CHECK (id=1), version INTEGER NOT NULL);
INSERT OR IGNORE INTO config VALUES (1, 0);
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY, actor TEXT, target TEXT, identity TEXT, version INTEGER,
    before_policy TEXT, after_policy TEXT, approver TEXT, approval_until INTEGER
);
CREATE TABLE IF NOT EXISTS receipts (
    actor TEXT, request_key TEXT, plan_id TEXT UNIQUE, result TEXT NOT NULL,
    PRIMARY KEY(actor, request_key)
);
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY, actor TEXT, approver TEXT, target TEXT, identity TEXT,
    starts INTEGER, ends INTEGER, status TEXT
);
CREATE TABLE IF NOT EXISTS job_events (
    seq INTEGER PRIMARY KEY, job_id TEXT, status TEXT, time INTEGER, reason TEXT
);
"""


class ReplayOperations:
    """Local simulator. Device inventory, grants, clock and postchecks are trusted inputs."""

    def __init__(self, path, *, qos_postcheck):
        self.db = sqlite3.connect(path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)
        self.qos_postcheck = qos_postcheck

    def close(self):
        self.db.close()

    @contextmanager
    def write(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def device(self, target):
        row = self.db.execute("SELECT * FROM devices WHERE id=?", (target,)).fetchone()
        if row is None:
            raise OperationDenied("target_unknown")
        return row

    def register_device(self, target, identity):
        """Replay the current inventory. A different identity invalidates old authorizations."""
        if not isinstance(target, str) or not target or not isinstance(identity, str) or not identity:
            raise OperationDenied("invalid_target_identity")
        with self.write():
            old = self.db.execute("SELECT identity FROM devices WHERE id=?", (target,)).fetchone()
            self.db.execute(
                "INSERT INTO devices VALUES (?, ?, NULL) ON CONFLICT(id) DO UPDATE "
                "SET identity=excluded.identity, qos=CASE WHEN identity=excluded.identity THEN qos ELSE NULL END",
                (target, identity))
            if old is not None and old["identity"] != identity:
                self.db.execute("UPDATE config SET version=version+1")

    def grant(self, actor, scope, expires, *, target="*"):
        """Load a trusted replay ACL entry. Set expiry to the current time to revoke it."""
        if type(expires) is not int:
            raise OperationDenied("invalid_grant_expiry")
        with self.write():
            self.db.execute("INSERT OR REPLACE INTO grants VALUES (?, ?, ?, ?)", (actor, scope, target, expires))

    def require(self, actor, scope, now, target):
        grant = self.db.execute(
            "SELECT expires FROM grants WHERE actor=? AND scope=? AND target IN (?, '*') "
            "ORDER BY target=? DESC LIMIT 1", (actor, scope, target, target)).fetchone()
        if grant is None or grant["expires"] <= now:
            raise OperationDenied("permission_denied:" + scope)

    def plan_qos(self, actor, target, policy, now):
        if not isinstance(policy, dict):
            raise OperationDenied("invalid_qos_policy")
        rate = policy.get("rate_mbps")
        limit = (policy.keys() == {"rate_mbps"} and type(rate) is int and 0 < rate <= 10_000)
        priority = (policy.keys() == {"priority"} and policy["priority"] in ("gaming", "video_call"))
        if not (limit or priority):
            raise OperationDenied("invalid_qos_policy")
        with self.write():
            self.require(actor, "qos.write", now, target)
            device = self.device(target)
            version = self.db.execute("SELECT version FROM config").fetchone()["version"]
            plan_id = uuid4().hex
            self.db.execute("INSERT INTO plans VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)",
                            (plan_id, actor, target, device["identity"], version, device["qos"],
                             json.dumps(policy, sort_keys=True)))
        return {"plan_id": plan_id, "target": target, "base_version": version,
                "before": json.loads(device["qos"]) if device["qos"] else None, "after": policy}

    def approve_qos(self, plan_id, approver, now, expires):
        if type(expires) is not int or not now < expires <= now + 300:
            raise OperationDenied("invalid_approval_expiry")
        with self.write():
            plan = self.db.execute("SELECT actor,target FROM plans WHERE id=?", (plan_id,)).fetchone()
            if plan is None or plan["actor"] == approver:
                raise OperationDenied("independent_approval_required")
            self.require(approver, "change.approve", now, plan["target"])
            self.db.execute("UPDATE plans SET approver=?, approval_until=? WHERE id=?",
                            (approver, expires, plan_id))

    def apply_qos(self, actor, plan_id, request_key, now):
        if not isinstance(request_key, str) or not request_key.strip():
            raise OperationDenied("missing_idempotency_key")
        with self.write():
            prior = self.db.execute("SELECT * FROM receipts WHERE actor=? AND request_key=?",
                                    (actor, request_key)).fetchone()
            if prior:
                if prior["plan_id"] != plan_id:
                    raise OperationDenied("idempotency_conflict")
                return json.loads(prior["result"])
            plan = self.db.execute("SELECT * FROM plans WHERE id=? AND actor=?", (plan_id, actor)).fetchone()
            if plan is None or plan["approval_until"] is None or now >= plan["approval_until"]:
                raise OperationDenied("approval_missing_or_expired")
            self.require(actor, "qos.write", now, plan["target"])
            if self.db.execute("SELECT 1 FROM receipts WHERE plan_id=?", (plan_id,)).fetchone():
                raise OperationDenied("plan_already_executed")
            self.require(plan["approver"], "change.approve", now, plan["target"])
            device = self.device(plan["target"])
            if device["identity"] != plan["identity"]:
                raise OperationDenied("target_identity_changed")
            version = self.db.execute("SELECT version FROM config").fetchone()["version"]
            if plan["version"] != version:
                raise OperationDenied("config_version_conflict")
            self.db.execute("SAVEPOINT qos_change")
            self.db.execute("UPDATE devices SET qos=? WHERE id=?", (plan["after_policy"], plan["target"]))
            try:
                observed = self.qos_postcheck(plan["target"], plan["identity"])
            except OSError:
                observed = None
            verified = self.verify_qos(plan, observed, now)
            if verified:
                self.db.execute("UPDATE config SET version=version+1")
            else:
                self.db.execute("ROLLBACK TO qos_change")
            self.db.execute("RELEASE qos_change")
            receipt = {"plan_id": plan_id, "target": plan["target"],
                       "status": "APPLIED" if verified else "ROLLED_BACK",
                       "config_version": version + int(verified),
                       "postcheck_evidence_id": observed.get("id") if verified else None}
            self.db.execute("INSERT INTO receipts VALUES (?, ?, ?, ?)",
                            (actor, request_key, plan_id, json.dumps(receipt)))
            return receipt

    def verify_qos(self, plan, observation, now):
        if not isinstance(observation, dict) or not observation.get("id"):
            return False
        measured_at = observation.get("observed_at")
        # Apply and readback share one simulated tick. Older measurements predate the change.
        if type(measured_at) is not int or measured_at != now:
            return False
        if (observation.get("identity") != plan["identity"]
                or observation.get("target") != plan["target"]
                or observation.get("effective_policy") != json.loads(plan["after_policy"])):
            return False
        if self.device(plan["target"])["qos"] != plan["after_policy"]:
            return False
        readings = [observation.get(key) for key in ("target_before_ms", "target_after_ms",
                                                     "other_before_ms", "other_after_ms")]
        if not all(type(value) in (int, float) and 0 <= value <= 60_000 for value in readings):
            return False
        before, after, other_before, other_after = readings
        return after <= before + 10 and other_after <= other_before + 10

    def schedule_block(self, job_id, actor, target, starts, ends, now):
        if (not isinstance(job_id, str) or not job_id
                or type(starts) is not int or type(ends) is not int or not starts < ends):
            raise OperationDenied("invalid_schedule_window")
        with self.write():
            self.require(actor, "schedule.write", now, target)
            self.require(actor, "access.write", now, target)
            device = self.device(target)
            old = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            payload = (actor, target, device["identity"], starts, ends)
            if old:
                if tuple(old[key] for key in ("actor", "target", "identity", "starts", "ends")) != payload:
                    raise OperationDenied("schedule_id_conflict")
                return old["status"]
            if starts < now:
                raise OperationDenied("schedule_starts_in_past")
            self.db.execute("INSERT INTO jobs VALUES (?, ?, NULL, ?, ?, ?, ?, 'AWAITING_APPROVAL')",
                            (job_id, *payload))
            self.db.execute("INSERT INTO job_events(job_id,status,time) VALUES (?, 'AWAITING_APPROVAL', ?)",
                            (job_id, now))
        return "AWAITING_APPROVAL"

    def approve_schedule(self, job_id, approver, now):
        with self.write():
            job = self.db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            if job is None or job["actor"] == approver:
                raise OperationDenied("independent_approval_required")
            self.require(approver, "change.approve", now, job["target"])
            if job["status"] == "PENDING" and job["approver"] == approver:
                return {"job_id": job_id, "status": "PENDING"}
            if job["status"] != "AWAITING_APPROVAL" or now > job["starts"]:
                raise OperationDenied("schedule_no_longer_approvable")
            self.db.execute("UPDATE jobs SET approver=? WHERE id=?", (approver, job_id))
            return self._transition_job(job_id, "PENDING", now)

    def _transition_job(self, job_id, status, now, reason=None):
        self.db.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
        self.db.execute("INSERT INTO job_events(job_id,status,time,reason) VALUES (?, ?, ?, ?)",
                        (job_id, status, now, reason))
        return {"job_id": job_id, "status": status, "at": now, "reason": reason}

    def check_job_policy(self, job, now):
        self.require(job["actor"], "access.write", now, job["target"])
        self.require(job["actor"], "schedule.write", now, job["target"])
        self.require(job["approver"], "change.approve", now, job["target"])
        if self.device(job["target"])["identity"] != job["identity"]:
            raise OperationDenied("target_identity_changed")

    def tick(self, now):
        """Consume due jobs once. A replay access block is effective only within its window."""
        with self.write():
            jobs = self.db.execute(
                "SELECT * FROM jobs WHERE (status='PENDING' AND starts<=?) OR status='ACTIVE' "
                "OR (status='AWAITING_APPROVAL' AND ends<=?) ORDER BY starts,id", (now, now)).fetchall()
            events = []
            for job in jobs:
                reason = None
                if now >= job["ends"]:
                    status = "EXPIRED" if job["status"] == "ACTIVE" else "MISSED"
                else:
                    try:
                        self.check_job_policy(job, now)
                        status = "ACTIVE"
                    except OperationDenied as exc:
                        status = "BLOCKED"
                        reason = str(exc)
                if status != job["status"]:
                    events.append(self._transition_job(job["id"], status, now, reason))
            return events

    def cancel(self, job_id, actor, now):
        with self.write():
            job = self.db.execute("SELECT * FROM jobs WHERE id=? AND actor=?", (job_id, actor)).fetchone()
            if job is None:
                raise OperationDenied("job_not_owned")
            self.require(actor, "schedule.write", now, job["target"])
            if job["status"] == "ACTIVE":
                self.require(actor, "access.write", now, job["target"])
            if job["status"] not in ("AWAITING_APPROVAL", "PENDING", "ACTIVE"):
                return {"job_id": job_id, "status": job["status"]}
            return self._transition_job(job_id, "CANCELLED", now)

    def internet_blocked(self, target, now):
        jobs = self.db.execute(
            "SELECT * FROM jobs WHERE target=? AND status='ACTIVE' AND starts<=? AND ends>?",
            (target, now, now)).fetchall()
        for job in jobs:
            try:
                self.check_job_policy(job, now)
            except OperationDenied:
                continue
            return True
        return False
