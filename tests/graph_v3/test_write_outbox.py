"""Durable no-blind-replay WRITE reconciliation under crash injection."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from gateway_pilot.core import PlanError
from gateway_pilot.graph_v3.change_transaction import (
    ApprovalAuthority, DurableApprovalLedger, SafeWriteTransaction,
)
from gateway_pilot.graph_v3.contracts import Function
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.write_outbox import DurableWriteOutbox
from tests.graph_v3.test_change_transaction import Driver


class CrashDriver(Driver):
    def __init__(self, *, apply_before_crash):
        super().__init__()
        self.apply_before_crash = apply_before_crash

    def apply(self, fid, arguments):
        self.calls.append("apply")
        if self.apply_before_crash:
            self.state = {"profile": arguments["profile"]}
        raise SystemExit("simulated_unclean_process_exit")


class WriteOutboxTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.registry = GraphRegistry()
        self.fid = "gateway.qos.set_profile"
        self.registry.functions[self.fid] = Function(
            self.fid, ("SK04",), {},
            {"wan.status": self.registry.ports["wan.status"]},
            "Trusted QoS driver stub", "gateway", risk="WRITE",
            permission="network.write",
            arguments_schema={
                "type": "object",
                "properties": {"profile": {"type": "string",
                                           "enum": ["gaming", "balanced"]}},
                "required": ["profile"], "additionalProperties": False,
            },
        )
        self.auth = ApprovalAuthority(b"0123456789abcdef" * 2, clock=lambda: 100.0)
        self.kwargs = {
            "target": "gateway_01", "revision": "config-r1", "operator": "admin",
            "permissions": {"network.write"}, "capabilities": {self.fid},
        }
        self.outbox_path = self.root / "outbox.sqlite"
        self.ledger_path = self.root / "approvals.sqlite"

    def token(self):
        return self.auth.issue(
            function_id=self.fid, arguments={"profile": "gaming"},
            target="gateway_01", revision="config-r1", operator="admin",
        )

    def controller(self, driver):
        return SafeWriteTransaction(
            self.registry, driver, self.auth,
            DurableApprovalLedger(self.ledger_path),
            allowlist=[self.fid], enabled=True,
            outbox=DurableWriteOutbox(self.outbox_path),
        )

    def test_success_receipt_then_no_second_execution(self):
        driver = Driver()
        token = self.token()
        result = self.controller(driver).commit(token, **self.kwargs)
        self.assertEqual(result["status"], "COMMITTED")
        row = DurableWriteOutbox(self.outbox_path).inspect(token["payload"]["nonce"])
        self.assertEqual(row["status"], "COMMITTED")
        self.assertEqual(len(row["before_hash"]), 64)
        self.assertNotIn("balanced", str(row))
        count = driver.calls.count("apply")
        with self.assertRaisesRegex(PlanError, "already_used"):
            self.controller(driver).commit(token, **self.kwargs)
        self.assertEqual(driver.calls.count("apply"), count)

    def test_unclean_exit_after_apply_reconciles_without_replaying(self):
        driver = CrashDriver(apply_before_crash=True)
        token = self.token()
        with self.assertRaises(SystemExit):
            self.controller(driver).commit(token, **self.kwargs)
        storage = DurableWriteOutbox(self.outbox_path)
        nonce = token["payload"]["nonce"]
        self.assertEqual(storage.inspect(nonce)["status"], "IN_FLIGHT")
        count = driver.calls.count("apply")
        result = DurableWriteOutbox(self.outbox_path).reconcile(
            nonce, driver=driver, target="gateway_01", revision="config-r1"
        )
        self.assertEqual(result["status"], "COMMITTED_OBSERVED")
        self.assertEqual(driver.calls.count("apply"), count)
        with self.assertRaises(PlanError):
            self.controller(driver).commit(token, **self.kwargs)

    def test_unclean_exit_before_apply_requires_new_operator_approval(self):
        driver = CrashDriver(apply_before_crash=False)
        token = self.token()
        with self.assertRaises(SystemExit):
            self.controller(driver).commit(token, **self.kwargs)
        nonce = token["payload"]["nonce"]
        result = DurableWriteOutbox(self.outbox_path).reconcile(
            nonce, driver=driver, target="gateway_01", revision="config-r1"
        )
        self.assertEqual(result["status"], "NOT_APPLIED_OBSERVED")
        self.assertEqual(driver.state["profile"], "balanced")
        with self.assertRaisesRegex(PlanError, "already_used"):
            self.controller(driver).commit(token, **self.kwargs)

    def test_context_mismatch_and_uncertain_state_refuse_replay(self):
        driver = CrashDriver(apply_before_crash=True)
        token = self.token()
        with self.assertRaises(SystemExit):
            self.controller(driver).commit(token, **self.kwargs)
        outbox = DurableWriteOutbox(self.outbox_path)
        nonce = token["payload"]["nonce"]
        with self.assertRaisesRegex(PlanError, "context_mismatch"):
            outbox.reconcile(nonce, driver=driver, target="other",
                             revision="config-r1")
        driver.state["profile"] = "unexpected"
        result = outbox.reconcile(nonce, driver=driver, target="gateway_01",
                                  revision="config-r1")
        self.assertEqual(result["status"], "MANUAL_RECOVERY_REQUIRED")

    def test_invalid_phase_transition_and_nonce_replay_blocked(self):
        outbox = DurableWriteOutbox(self.outbox_path)
        outbox.prepare(
            nonce="test-nonce", target="gateway_01", revision="r1",
            function_id=self.fid,
            before={"profile": "balanced"},
            desired={"profile": "gaming"},
        )
        with self.assertRaisesRegex(PlanError, "duplicate_nonce"):
            outbox.prepare(
                nonce="test-nonce", target="gateway_01", revision="r1",
                function_id=self.fid,
                before={"profile": "balanced"},
                desired={"profile": "gaming"},
            )
        with self.assertRaisesRegex(PlanError, "invalid_transition"):
            outbox.transition("test-nonce", from_status="PREPARED",
                              to_status="COMMITTED")


if __name__ == "__main__":
    unittest.main()
