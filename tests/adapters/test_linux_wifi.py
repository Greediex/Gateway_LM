"""Linux parsing and fixed READ command contracts, without live OS probes."""
import json
import subprocess
import unittest
from unittest.mock import PropertyMock, patch

from gateway_pilot.adapters.bindings import TargetContext
from gateway_pilot.adapters.linux_wifi import LinuxWifiBackend, parse_ping, parse_wifi, split_nmcli
from gateway_pilot.adapters.read_backends import LinuxClientReadBackend
from gateway_pilot.core import PlanError


class LinuxWifiTests(unittest.TestCase):
    def test_nmcli_escaped_colon_and_backslash(self):
        self.assertEqual(split_nmcli(r"a\:b:c\\d:"), ["a:b", "c\\d", ""])
        row = parse_wifi(r"*:Lab\:West\\5:aa\:bb:73:36:5180 MHz:1201 Mbit/s",
                         interface="wlan0", radio_enabled=True)
        self.assertEqual((row["ssid"], row["bssid"], row["signal_pct"]), ("Lab:West\\5", "aa:bb", 73))
        self.assertEqual((row["frequency_mhz"], row["ap_rate_mbps"]), (5180, 1201))
        self.assertNotIn("rssi_dbm", row)

    def test_missing_metrics_are_unknown(self):
        row = parse_wifi("*:Lab:ap:--::--:", interface="wlan0", radio_enabled=True)
        self.assertTrue(row["associated"])
        self.assertEqual([row[k] for k in ("signal_pct", "channel", "frequency_mhz", "ap_rate_mbps")], [-1, 0, 0, -1])

    def test_radio_off_and_disconnected(self):
        for enabled in (True, False):
            row = parse_wifi(":Other:ap:90:1:2412:54", interface="wlan0", radio_enabled=enabled)
            self.assertFalse(row["associated"])
            self.assertEqual(row["radio_enabled"], enabled)
            self.assertEqual(row["signal_pct"], -1)

    def test_malformed_wifi_fails_closed(self):
        for raw in ("*:short", "*:Lab:ap:101:1:2412:54", "*:Lab:ap:bad:1:2412:54",
                    "*:Lab:ap:70:1:2412:54\\", "*:A:ap:70:1:2412:54\n*:B:ap:60:1:2412:54"):
            with self.subTest(raw=raw), self.assertRaises(PlanError):
                parse_wifi(raw, interface="wlan0", radio_enabled=True)
        with self.assertRaises(PlanError):
            parse_wifi("*:Lab:ap:70:1:2412:54", interface="wlan0", radio_enabled=False)

    def test_ping_loss_and_latency(self):
        result = parse_ping("4 packets transmitted, 3 received, 25% packet loss\nrtt min/avg/max/mdev = 1.0/2.5/4.0/1.0 ms",
                            destination="1.1.1.1", interface="eth0")
        self.assertEqual((result["loss_pct"], result["latency_ms"], result["interface"]), (25, 2.5, "eth0"))
        failed = parse_ping("4 packets transmitted, 0 received, 100% packet loss", destination="1.1.1.1", interface="eth0")
        self.assertEqual((failed["received"], failed["latency_ms"]), (0, -1))
        for raw in ("timeout", "4 packets transmitted, 4 received, 100% packet loss", "4 packets transmitted, 4 received, 0% packet loss"):
            with self.subTest(raw=raw), self.assertRaises(PlanError):
                parse_ping(raw, destination="1.1.1.1", interface="eth0")

    def make_backend(self):
        self.calls, self.gateway, self.dns = [], "192.0.2.1", "192.0.2.53"
        def run(argv, **kwargs):
            self.calls.append((argv, kwargs))
            args = argv[1:]
            if args[-2:] == ["device", "status"]:
                output = "wlan0:wifi:connected\neth0:ethernet:connected"
            elif args == ["radio", "wifi"]:
                output = "enabled"
            elif "--rescan" in args:
                output = "*:Lab:ap:70:36:5180:1201"
            elif args[:3] == ["-j", "route", "get"]:
                output = json.dumps([{"dev": "eth0", "prefsrc": "192.0.2.10", "gateway": self.gateway}])
            elif args[0] == "dns":
                output = self.dns
            elif args[0] == "domain":
                output = "~."
            else:
                raise AssertionError(argv)
            return subprocess.CompletedProcess(argv, 0, output, "")
        for target, kwargs in (("gateway_pilot.adapters.linux_wifi.shutil.which", {"side_effect": lambda n: "/bin/"+n}),
                               ("gateway_pilot.adapters.read_backends.socket.if_nametoindex", {"return_value": 3}),
                               ("gateway_pilot.adapters.read_backends.platform.system", {"return_value": "Linux"})):
            p = patch(target, **kwargs); p.start(); self.addCleanup(p.stop)
        p = patch.object(LinuxClientReadBackend, "environment_id", new_callable=PropertyMock, return_value="kernel")
        p.start(); self.addCleanup(p.stop)
        p = patch.object(LinuxClientReadBackend, "_ipv4", return_value={"configured": True, "address": "198.51.100.2"})
        p.start(); self.addCleanup(p.stop)
        return LinuxWifiBackend(runner=run)

    def test_wifi_uses_no_rescan_and_bounded_command(self):
        backend = self.make_backend()
        self.assertTrue(backend.wifi()["associated"])
        argv, options = self.calls[-1]
        self.assertEqual(argv[-5:], ["list", "--rescan", "no", "ifname", "wlan0"])
        self.assertEqual(options["timeout"], 3)
        self.assertFalse(options["check"])
        self.assertEqual(options["env"]["LC_ALL"], "C")

    def test_route_resolver_change_invalidates_bound_context(self):
        backend = self.make_backend()
        context = TargetContext("client", backend.client_id, backend.environment_id)
        self.assertTrue(backend.supports("laptop.route", context))
        self.gateway = "192.0.2.254"
        self.assertFalse(backend.supports("laptop.route", context))
        self.gateway = "192.0.2.1"
        self.dns = "192.0.2.54"
        self.assertFalse(backend.supports("laptop.route", context))
        with self.assertRaises(PlanError):
            backend.sample({"function_id": "laptop.route"}, {}, context)

    def test_timeout_and_bad_route_never_return_observations(self):
        backend = self.make_backend()
        backend._run = lambda *a, **k: (_ for _ in ()).throw(subprocess.TimeoutExpired("ping", 6))
        with self.assertRaisesRegex(TimeoutError, "linux_read_timeout"):
            backend._command("ping", "fixed", timeout=6)
        backend._run = lambda *a, **k: subprocess.CompletedProcess(a[0], 0, '[{"dev":"eth0","prefsrc":"not-an-ip"}]', "")
        with self.assertRaises(PlanError):
            backend.route()
