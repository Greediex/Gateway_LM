"""Snapshots consume real Core-verified replay facts with explicit test opt-in."""
import unittest

from gateway_pilot.core import PlanError
from gateway_pilot.observability.snapshot import VerifiedSnapshot
from tests.catalog import test_runtime_v02 as fixtures


class VerifiedSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.RuntimeV02Tests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.runtime.probe()
        self.runner, _ = self.fixture.runtime.execute(["client.ipv4"])
        self.valid = True

    def snapshot(self, **kwargs):
        return VerifiedSnapshot.from_state(self.runner.state, ["client.ipv4"],
                                          context_valid=lambda: self.valid, allow_replay=True, **kwargs)

    def test_raw_dictionary_is_not_verified_state(self):
        with self.assertRaises(PlanError):
            VerifiedSnapshot.from_state({"facts": {}}, [], context_valid=lambda: True)

    def test_replay_requires_explicit_opt_in_and_exports_evidence(self):
        denied = VerifiedSnapshot.from_state(self.runner.state, ["client.ipv4"], context_valid=lambda: True)
        self.assertEqual(denied.export()["missing_ports"], ["client.ipv4"])
        row = self.snapshot().export()["facts"]["client.ipv4"]
        self.assertEqual(row["evidence_id"], self.runner.state.fact("client.ipv4")["id"])
        self.assertEqual(row["value"]["address"], "192.0.2.10")

    def test_snapshot_and_export_are_isolated_from_mutation(self):
        snapshot = self.snapshot()
        self.runner.state.fact("client.ipv4")["value"]["address"] = "203.0.113.20"
        exported = snapshot.export()
        exported["facts"]["client.ipv4"]["value"]["address"] = "mutated"
        self.assertEqual(snapshot.export()["facts"]["client.ipv4"]["value"]["address"], "192.0.2.10")

    def test_stale_facts_excluded_at_creation_and_consumption(self):
        snapshot = self.snapshot()
        self.fixture.time += 31
        for result in (snapshot.export(), self.snapshot().export()):
            self.assertEqual(result["facts"], {})
            self.assertEqual(result["missing_ports"], ["client.ipv4"])

    def test_context_invalidation_and_clock_rollback_fail_closed(self):
        snapshot = self.snapshot()
        self.valid = False
        self.assertFalse(snapshot.export()["context_valid"])
        self.assertEqual(snapshot.export()["facts"], {})
        self.valid = True
        self.fixture.time -= 1
        self.assertEqual(snapshot.export()["facts"], {})

    def test_wrong_target_or_provenance_is_not_exported(self):
        fact = self.runner.state.fact("client.ipv4")
        for key, bad in (("target", "other-client"), ("source", "linux_client/forged"), ("contract_digest", "0"*64)):
            old = fact[key]
            fact[key] = bad
            with self.subTest(key=key):
                self.assertEqual(self.snapshot().export()["facts"], {})
            fact[key] = old

    def test_slow_environment_recheck_cannot_extend_expired_evidence(self):
        def slow_context():
            self.fixture.time += 31
            return True
        snapshot = VerifiedSnapshot.from_state(self.runner.state, ["client.ipv4"],
                                               context_valid=slow_context, allow_replay=True)
        result = snapshot.export()
        self.assertEqual(result["facts"], {})
        self.assertEqual(result["expires_in_s"], 0)
