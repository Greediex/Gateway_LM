"""Conformance providers: source separation and Linux kernel-only reads."""
import errno
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, PropertyMock

from gateway_pilot.core import ROOT, PlanError
from gateway_pilot.command_catalog.builder import build_registry
from gateway_pilot.command_catalog.loader import load_catalog, read_json
from gateway_pilot.adapters.bindings import BindingSelection, TargetContext, declare_binding, binding_digest
from gateway_pilot.adapters.conformance import ConformanceHarness
from gateway_pilot.adapters.read_backends import LinuxClientReadBackend, ReplayReadBackend


class ReadBackendTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.policy = read_json(ROOT / "config/catalog_policy.laptop.example.json")
        self.artifact = build_registry(load_catalog(ROOT / "examples/catalog_laptop"),
                                      read_json(ROOT / "config/catalog_selection.laptop.example.json"),
                                      self.policy, Path(self.tmp.name) / "linux.json")

    def provider(self):
        platform_patch = patch("gateway_pilot.adapters.read_backends.platform.system", return_value="Linux")
        index_patch = patch("gateway_pilot.adapters.read_backends.socket.if_nametoindex", return_value=7)
        environment_patch = patch.object(LinuxClientReadBackend, "environment_id", new_callable=PropertyMock, return_value="a" * 64)
        for item in (platform_patch, index_patch, environment_patch):
            item.start(); self.addCleanup(item.stop)
        return LinuxClientReadBackend("wlan0")

    def test_laptop_sample_conforms_and_does_not_claim_rssi_support(self):
        provider = self.provider()
        context = TargetContext("client", "local-laptop", provider.environment_id)
        rows = [declare_binding(self.artifact, fid, "linux." + fid, "linux.local", provider, context)
                for fid in ("clients.resolve", "client.ipv4")]
        selection = BindingSelection(self.artifact, self.policy, rows,
                                     approved_digests=frozenset(binding_digest(row) for row in rows),
                                     backends={"linux.local": provider}, context=context)
        with patch.object(provider, "_ipv4", return_value={"configured": True, "address": "192.0.2.20"}):
            report = ConformanceHarness(selection).check("linux.client.ipv4", {"client_id": "local-laptop"}, context, frozenset({"network.read"}))
        self.assertEqual(report["status"], "CONFORMANT")
        self.assertEqual(report["source"], "linux_client/binding_v1")
        self.assertNotIn("192.0.2.20", str(report))
        self.assertFalse(provider.supports("wifi.station", context))
        self.assertFalse(report["execution_enabled"])

    def test_replay_cannot_satisfy_linux_port_provenance(self):
        provider = ReplayReadBackend({"clients.resolve": {"client.identity": {"client_id": "test"}}}, client_id="test")
        provider.probe_ids = {"clients.resolve": "probe.linux.clients_resolve"}
        context = TargetContext("client", "test", provider.environment_id)
        row = declare_binding(self.artifact, "clients.resolve", "test.identity", "replay.seed", provider, context)
        with self.assertRaisesRegex(PlanError, "provenance_mismatch"):
            BindingSelection(self.artifact, self.policy, [row], approved_digests=frozenset({binding_digest(row)}),
                             backends={"replay.seed": provider}, context=context)

    def test_wrong_probe_implementation_and_environment_are_rejected(self):
        provider = self.provider()
        context = TargetContext("client", "local-laptop", provider.environment_id)
        row = declare_binding(self.artifact, "clients.resolve", "test.identity", "linux.local", provider, context)
        provider.probe_ids = {"clients.resolve": "wrong.probe"}
        with self.assertRaisesRegex(PlanError, "backend_pin_mismatch"):
            BindingSelection(self.artifact, self.policy, [row], approved_digests=frozenset({binding_digest(row)}),
                             backends={"linux.local": provider}, context=context)
        self.assertFalse(provider.supports("clients.resolve", TargetContext("client", "local-laptop", "b" * 64)))

    def test_linux_invalid_platform_interface_and_missing_device(self):
        with patch("gateway_pilot.adapters.read_backends.platform.system", return_value="Windows"):
            with self.assertRaises(PlanError):
                LinuxClientReadBackend("wlan0")
        with patch("gateway_pilot.adapters.read_backends.platform.system", return_value="Linux"):
            for interface in ("../wlan0", "wlan0;id", "x" * 16):
                with self.subTest(interface=interface), self.assertRaises(PlanError):
                    LinuxClientReadBackend(interface)
            with patch("gateway_pilot.adapters.read_backends.socket.if_nametoindex", side_effect=OSError("gone")):
                with self.assertRaisesRegex(PlanError, "interface_unavailable"):
                    LinuxClientReadBackend("wlan0")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux SIOCGIFADDR read")
    def test_linux_ipv4_ioctl_and_unconfigured_error_normalization(self):
        provider = self.provider()
        raw = b"\0" * 20 + socket.inet_aton("192.0.2.30") + b"\0" * 232
        with patch("fcntl.ioctl", return_value=raw):
            self.assertEqual(provider._ipv4(), {"configured": True, "address": "192.0.2.30"})
        with patch("fcntl.ioctl", side_effect=OSError(errno.EADDRNOTAVAIL, "no address")):
            self.assertEqual(provider._ipv4(), {"configured": False, "address": ""})
        with patch("fcntl.ioctl", side_effect=OSError(errno.ENODEV, "gone")):
            with self.assertRaises(OSError):
                provider._ipv4()


if __name__ == "__main__":
    unittest.main()
