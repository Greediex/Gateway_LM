import tempfile
import unittest
import hashlib
import hmac
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from gateway_pilot.monitor import THRESHOLDS, monitor_window
from gateway_pilot.lifecycle import preflight_artifact
from gateway_pilot.operations import OperationDenied, ReplayOperations


class ReplayOperationsTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "state.sqlite"
        self.ops = self.open_store({"rate_mbps": 50})
        self.addCleanup(self.ops.close)
        self.ops.register_device("client-a", "identity-a")
        self.ops.register_device("client-b", "identity-b")
        for scope in ("qos.write", "access.write", "schedule.write"):
            self.ops.grant("owner", scope, 2_000, target="client-a")
        self.ops.grant("approver", "change.approve", 2_000, target="client-a")

    def open_store(self, policy):
        return ReplayOperations(self.path, qos_postcheck=lambda target, identity: {
            "id": "probe-postchange", "observed_at": 1_005, "target": target, "identity": identity,
            "effective_policy": policy, "target_before_ms": 38, "target_after_ms": 25,
            "other_before_ms": 28, "other_after_ms": 30,
        })

    def plan(self, policy=None):
        plan = self.ops.plan_qos("owner", "client-a", policy or {"rate_mbps": 50}, 1_000)
        return plan["plan_id"]

    def schedule(self, key="job-1", approve=True, starts=1_010, ends=1_060):
        self.ops.schedule_block(key, "owner", "client-a", starts, ends, 1_000)
        if approve:
            self.ops.approve_schedule(key, "approver", 1_001)

    def test_qos_requires_separate_approval_and_target_permission(self):
        plan = self.plan()
        with self.assertRaisesRegex(OperationDenied, "approval_missing"):
            self.ops.apply_qos("owner", plan, "apply-1", 1_005)
        with self.assertRaisesRegex(OperationDenied, "independent_approval"):
            self.ops.approve_qos(plan, "owner", 1_002, 1_050)
        with self.assertRaisesRegex(OperationDenied, "permission_denied"):
            self.ops.plan_qos("owner", "client-b", {"rate_mbps": 50}, 1_000)
        self.assertIsNone(self.ops.device("client-a")["qos"])

    def test_qos_applies_with_postcheck_and_reuses_idempotent_receipt(self):
        plan = self.plan()
        self.ops.approve_qos(plan, "approver", 1_002, 1_050)
        receipt = self.ops.apply_qos("owner", plan, "apply-1", 1_005)
        self.assertEqual(receipt["status"], "APPLIED")
        self.assertEqual(receipt["config_version"], 1)
        self.assertEqual(receipt["postcheck_evidence_id"], "probe-postchange")
        self.assertEqual(self.ops.apply_qos("owner", plan, "apply-1", 1_060), receipt)
        with self.assertRaisesRegex(OperationDenied, "idempotency_conflict"):
            self.ops.apply_qos("owner", self.plan(), "apply-1", 1_005)

    def test_qos_rolls_back_on_scope_time_or_other_client_postcheck_failure(self):
        make_observation = self.ops.qos_postcheck
        for index, patch in enumerate(({"identity": "old-device"}, {"observed_at": 950},
                                       {"other_after_ms": 72})):
            with self.subTest(patch=patch):
                self.ops.qos_postcheck = lambda target, identity: {**make_observation(target, identity), **patch}
                plan = self.plan()
                self.ops.approve_qos(plan, "approver", 1_002, 1_050)
                receipt = self.ops.apply_qos("owner", plan, f"failure-{index}", 1_005)
                self.assertEqual(receipt["status"], "ROLLED_BACK")
                self.assertEqual(receipt["config_version"], 0)
                self.assertIsNone(self.ops.device("client-a")["qos"])

    def test_concurrent_qos_plans_share_the_config_version_lock(self):
        policies = ({"rate_mbps": 50}, {"priority": "gaming"})
        plans = [self.plan(policy) for policy in policies]
        for plan in plans:
            self.ops.approve_qos(plan, "approver", 1_002, 1_050)
        ready = Barrier(2)

        def apply(item):
            index, (plan, policy) = item
            store = self.open_store(policy)
            try:
                ready.wait(timeout=5)
                return store.apply_qos("owner", plan, f"concurrent-{index}", 1_005)["status"]
            except OperationDenied as exc:
                return str(exc)
            finally:
                store.close()

        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(apply, enumerate(zip(plans, policies))))
        self.assertCountEqual(results, ["APPLIED", "config_version_conflict"])

    def test_scheduled_job_survives_restart_and_expires_at_window_end(self):
        self.schedule()
        second = self.open_store({"rate_mbps": 50})
        self.addCleanup(second.close)
        self.assertEqual(second.tick(1_009), [])
        self.assertEqual(second.tick(1_010)[0]["status"], "ACTIVE")
        self.assertEqual(second.tick(1_010), [])
        self.assertTrue(second.internet_blocked("client-a", 1_015))
        self.assertFalse(second.internet_blocked("client-b", 1_015))
        self.assertFalse(second.internet_blocked("client-a", 1_060))
        self.assertEqual(second.tick(1_061)[0]["status"], "EXPIRED")

    def test_schedule_rechecks_permissions_and_identity_at_execution(self):
        self.schedule("revoked")
        self.ops.grant("owner", "access.write", 1_005, target="client-a")
        event = self.ops.tick(1_010)[0]
        self.assertEqual((event["status"], event["reason"]), ("BLOCKED", "permission_denied:access.write"))
        self.assertFalse(self.ops.internet_blocked("client-a", 1_011))
        self.ops.grant("owner", "access.write", 2_000, target="client-a")
        self.schedule("changed")
        self.ops.register_device("client-a", "identity-replaced")
        event = self.ops.tick(1_010)[0]
        self.assertEqual((event["status"], event["reason"]), ("BLOCKED", "target_identity_changed"))

    def test_unapproved_and_cancelled_jobs_cannot_execute(self):
        self.schedule("unapproved", approve=False)
        self.schedule("cancelled")
        self.assertEqual(self.ops.cancel("cancelled", "owner", 1_005)["status"], "CANCELLED")
        self.assertEqual(self.ops.tick(1_010), [])
        self.assertFalse(self.ops.internet_blocked("client-a", 1_011))
        self.assertEqual(self.ops.tick(1_061)[0]["status"], "MISSED")

    def test_reboot_after_window_records_missed_without_effect(self):
        self.schedule()
        self.assertEqual(self.ops.tick(1_100)[0]["status"], "MISSED")
        self.assertFalse(self.ops.internet_blocked("client-a", 1_100))


class MonitorTests(unittest.TestCase):
    def samples(self):
        metrics = {name: 50 for name in THRESHOLDS}
        metrics.update(cpu_pct=96, dhcp_success_pct=88, radio_busy_pct=92, dhcp_pool_free_pct=3)
        return [{"id": f"window-{i}", "target": "gateway-01", "source": "replay",
                 "boot_id": "boot-1", "config_version": "cfg-1", "observed_at": 1_000 + i * 60,
                 "metrics": dict(metrics)} for i in range(3)]

    def test_alerts_for_sustained_thresholds_cite_window(self):
        result = monitor_window(self.samples(), 1_120)
        self.assertEqual(result["case_status"], "RESOLVED")
        self.assertEqual({alert["metric"] for alert in result["alerts"]},
                         {"cpu_pct", "dhcp_success_pct", "radio_busy_pct", "dhcp_pool_free_pct"})
        self.assertEqual(result["alerts"][0]["evidence_ids"], ["window-0", "window-1", "window-2"])

    def test_partial_or_transient_data_does_not_become_an_alert(self):
        rows = self.samples()
        del rows[0]["metrics"]["dhcp_success_pct"]
        rows[-1]["metrics"]["cpu_pct"] = 30
        result = monitor_window(rows, 1_120)
        self.assertEqual(result["case_status"], "PARTIAL")
        self.assertEqual(result["missing_metrics"], ["dhcp_success_pct"])
        self.assertNotIn("cpu_pct", [alert["metric"] for alert in result["alerts"]])

    def test_mixed_boots_and_backward_time_are_inconclusive(self):
        rows = self.samples()
        rows[1]["boot_id"] = "boot-other"
        self.assertEqual(monitor_window(rows, 1_120)["case_status"], "INCONCLUSIVE")
        rows = self.samples()
        rows[2]["observed_at"] = 1_050
        self.assertEqual(monitor_window(rows, 1_120)["reason"], "stale_or_unordered_window")


class LifecyclePreflightTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.path = Path(folder.name) / "artifact.bin"
        self.path.write_bytes(b"replay-test-artifact")
        self.key = b"fixture-only"

    def manifest(self, kind):
        contents = self.path.read_bytes()
        metadata = {"kind": kind, "platform": "board-replay", "revision": 2,
                    "size_bytes": len(contents), "sha256": hashlib.sha256(contents).hexdigest()}
        payload = json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return {**metadata, "signature": hmac.digest(self.key, payload, "sha256")}

    def check(self, manifest, **overrides):
        options = {
            "platform": "board-replay", "current_revision": 1, "free_bytes": 10_000,
            "capabilities": {"lifecycle.firmware.preflight", "lifecycle.model.preflight"},
            "recovery_verified": True,
            "verify_signature": lambda message, signature: hmac.compare_digest(
                hmac.digest(self.key, message, "sha256"), signature),
        }
        return preflight_artifact(self.path, manifest, **{**options, **overrides})

    def test_signed_model_and_firmware_pass_read_only_preflight(self):
        for kind, workflow in (("model", "WF-047"), ("firmware", "WF-081")):
            with self.subTest(kind=kind):
                manifest = self.manifest(kind)
                result = self.check(manifest)
                self.assertEqual((result["status"], result["workflow_id"]), ("PREFLIGHT_OK", workflow))
                self.assertEqual(result["sha256"], manifest["sha256"])

    def test_incompatible_unverified_or_oversize_artifacts_block(self):
        manifest = self.manifest("firmware")
        for options, reason in (
            ({"platform": "other-board"}, "incompatible_platform"),
            ({"recovery_verified": False}, "recovery_unverified"),
            ({"free_bytes": 1}, "insufficient_storage"),
            ({"current_revision": 2}, "revision_not_newer"),
            ({"verify_signature": None}, "signature_verification_unavailable"),
        ):
            with self.subTest(reason=reason):
                self.assertEqual(self.check(manifest, **options)["reason"], reason)

    def test_modified_manifest_or_same_size_payload_cannot_pass(self):
        manifest = self.manifest("model")
        self.assertEqual(self.check({**manifest, "revision": 3})["reason"], "signature_invalid")
        self.path.write_bytes(b"x" * manifest["size_bytes"])
        self.assertEqual(self.check(manifest)["reason"], "artifact_digest_mismatch")


if __name__ == "__main__":
    unittest.main()
