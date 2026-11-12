"""Two-phase trusted WRITE transaction: approval, durable nonce, rollback."""
from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.core import PlanError
from gateway_pilot.graph_v3.change_transaction import (
    ApprovalAuthority, DurableApprovalLedger, SafeWriteTransaction,
)
from gateway_pilot.graph_v3.contracts import Function
from gateway_pilot.graph_v3.graphs import GraphRegistry


class Driver:
    def __init__(self):
        self.state = {"profile": "balanced"}
        self.calls = []
        self.probed = True
        self.corrupt = False
        self.rollback_bad = False

    def probe(self, fid):
        self.calls.append("probe")
        return self.probed

    def snapshot(self):
        self.calls.append("snapshot")
        return copy.deepcopy(self.state)

    def preview(self, fid, arguments, snapshot):
        self.calls.append("preview")
        return {"profile": arguments["profile"]}

    def apply(self, fid, arguments):
        self.calls.append("apply")
        self.state = {"profile": "wrong"} if self.corrupt else {
            "profile": arguments["profile"],
        }

    def readback(self):
        self.calls.append("readback")
        return copy.deepcopy(self.state)

    def rollback(self, snapshot):
        self.calls.append("rollback")
        self.state = {"profile": "still-wrong"} if self.rollback_bad else copy.deepcopy(snapshot)


class WriteTransactionTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.registry = GraphRegistry()
        self.fid = "gateway.qos.set_profile"
        f = Function(
            self.fid, ("SK04",), {}, {"wan.status": self.registry.ports["wan.status"]},
            "Trusted staged QoS profile change", "gateway", risk="WRITE",
            permission="network.write",
            arguments_schema={
                "type": "object", "properties": {
                    "profile": {"type": "string", "enum": ["gaming", "balanced"]}
                }, "required": ["profile"], "additionalProperties": False,
            }
        )
        self.registry.functions[self.fid] = f
        self.driver = Driver()
        self.time = [100.0]
        self.auth = ApprovalAuthority(b"0123456789abcdef" * 2, clock=lambda: self.time[0])
        self.dbpath = Path(self.directory.name) / "used.db"
        self.ledger = DurableApprovalLedger(self.dbpath)
        self.controller = SafeWriteTransaction(
            self.registry, self.driver, self.auth, self.ledger,
            allowlist=[self.fid], enabled=True,
        )
        self.kwargs = dict(
            target="gateway_01", revision="config-v1", operator="admin-1",
            permissions={"network.write"}, capabilities={self.fid},
        )

    def token(self, **kwargs):
        return self.auth.issue(
            function_id=self.fid, arguments={"profile": "gaming"},
            target="gateway_01", revision="config-v1", operator="admin-1",
            **kwargs,
        )

    def test_successful_write_has_verified_readback_and_exactly_one_nonce(self):
        token = self.token()
        result = self.controller.commit(token, **self.kwargs)
        self.assertEqual(result["status"], "COMMITTED")
        self.assertEqual(self.driver.state, {"profile": "gaming"})
        self.assertEqual(self.driver.calls, [
            "probe", "snapshot", "preview", "apply", "readback",
        ])
        # A new controller process with the same DB still rejects the nonce.
        fresh = SafeWriteTransaction(
            self.registry, self.driver, self.auth,
            DurableApprovalLedger(self.dbpath),
            allowlist=[self.fid], enabled=True,
        )
        with self.assertRaisesRegex(PlanError, "already_used"):
            fresh.commit(token, **self.kwargs)

    def test_invalid_signature_context_expired_or_permission_rejects_before_apply(self):
        modified = copy.deepcopy(self.token())
        modified["payload"]["arguments"]["profile"] = "balanced"
        cases = [
            (modified, self.kwargs, "invalid_write_approval_signature"),
            (self.token(), {**self.kwargs, "target": "other-gateway"},
             "write_approval_context_mismatch"),
            (self.token(), {**self.kwargs, "permissions": set()},
             "write_function_not_authorized"),
            (self.token(), {**self.kwargs, "capabilities": set()},
             "write_function_not_authorized"),
        ]
        for token, params, reason in cases:
            with self.subTest(reason=reason), self.assertRaisesRegex(PlanError, reason):
                self.controller.commit(token, **params)
            self.assertEqual(self.driver.state, {"profile": "balanced"})
        expired = self.token(ttl_seconds=1)
        self.time[0] += 61
        with self.assertRaisesRegex(PlanError, "write_approval_expired"):
            self.controller.commit(expired, **self.kwargs)

    def test_backend_probe_missing_or_change_disabled(self):
        self.driver.probed = False
        with self.assertRaisesRegex(PlanError, "write_backend_not_probed"):
            self.controller.commit(self.token(), **self.kwargs)
        self.driver.probed = True
        disabled = SafeWriteTransaction(
            self.registry, self.driver, self.auth, self.ledger,
            allowlist=[self.fid], enabled=False,
        )
        with self.assertRaisesRegex(PlanError, "write_transactions_disabled"):
            disabled.commit(self.token(), **self.kwargs)
        self.assertNotIn("apply", self.driver.calls)

    def test_bad_arguments_are_schema_rejected(self):
        token = self.auth.issue(
            function_id=self.fid, arguments={"profile": "unsafe; reboot"},
            target="gateway_01", revision="config-v1", operator="admin-1",
        )
        with self.assertRaisesRegex(PlanError, "write_arguments_schema_invalid"):
            self.controller.commit(token, **self.kwargs)
        self.assertEqual(self.driver.state["profile"], "balanced")

    def test_wrong_readback_triggers_rollback_and_verifies_restoration(self):
        self.driver.corrupt = True
        result = self.controller.commit(self.token(), **self.kwargs)
        self.assertEqual(result["status"], "ROLLED_BACK")
        self.assertEqual(self.driver.state, {"profile": "balanced"})
        self.assertIn("rollback", self.driver.calls)

    def test_failed_rollback_requires_manual_recovery_not_false_success(self):
        self.driver.corrupt = True
        self.driver.rollback_bad = True
        result = self.controller.commit(self.token(), **self.kwargs)
        self.assertEqual(result["status"], "MANUAL_RECOVERY_REQUIRED")
        self.assertEqual(result["evidence"], "NO_VERIFIED_POSTCONDITION")
        self.assertNotEqual(self.driver.state, {"profile": "balanced"})

    def test_manifest_can_never_promote_unverified_write_to_probed(self):
        f = self.registry.functions[self.fid]
        f.risk = "READ"
        with self.assertRaisesRegex(PlanError, "write_function_not_authorized"):
            self.controller.commit(self.token(), **self.kwargs)


if __name__ == "__main__":
    unittest.main()
