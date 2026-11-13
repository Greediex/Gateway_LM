"""Fixed, bounded READ collection for one local Linux laptop. Never rescan/write."""
from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import subprocess
from types import MappingProxyType

from .bindings import TargetContext, require
from .read_backends import LinuxClientReadBackend, observations
from ..command_catalog.loader import digest
from ..core import PlanError

PROBE_IP = "1.1.1.1"
DOMAIN = "example.com"
FUNCTIONS = ("clients.resolve", "client.ipv4", "laptop.route", "laptop.wifi",
             "laptop.gateway_probe", "laptop.internet_probe", "laptop.dns")


def split_nmcli(line: str) -> list[str]:
    fields, value, escaped = [], "", False
    for char in line:
        if escaped:
            value += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ":":
            fields.append(value); value = ""
        else:
            value += char
    require(not escaped, "nmcli_trailing_escape")
    return fields + [value]


def parse_wifi(text: str, *, interface: str, radio_enabled: bool) -> dict:
    result = dict(interface=interface, radio_enabled=radio_enabled, associated=False, ssid="", bssid="",
                  signal_pct=-1, channel=0, frequency_mhz=0, ap_rate_mbps=-1)
    active = []
    for line in text.splitlines():
        if not line:
            continue
        row = split_nmcli(line)
        require(len(row) == 7, "nmcli_wifi_columns")
        if row[0] in {"*", "yes"}:
            active.append(row)
    require(len(active) <= 1, "nmcli_multiple_active_wifi")
    if not active:
        return result
    require(radio_enabled, "wifi_active_while_radio_off")
    _, ssid, bssid, signal, channel, frequency, rate = active[0]
    require(len(ssid) <= 128 and len(bssid) <= 128, "wifi_text_limit")
    def metric(value, unit, missing, maximum):
        if value in {"", "--"}:
            return missing
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)" + unit, value)
        require(match is not None, "wifi_metric_format")
        number = float(match[1])
        require(0 <= number <= maximum, "wifi_metric_range")
        return number
    result.update(associated=True, ssid=ssid, bssid=bssid,
                  signal_pct=metric(signal, "", -1, 100), channel=metric(channel, "", 0, 1000),
                  frequency_mhz=metric(frequency, r"(?: MHz)?", 0, 100000),
                  ap_rate_mbps=metric(rate, r"(?: Mbit/s)?", -1, 100000))
    return result


def parse_ping(text: str, *, destination: str, interface: str) -> dict:
    summary = re.search(r"(\d+) packets transmitted, (\d+) (?:packets )?received,.*?([0-9.]+)% packet loss", text)
    require(summary is not None, "ping_summary")
    sent, received, loss = int(summary[1]), int(summary[2]), float(summary[3])
    require(sent == 4 and 0 <= received <= sent and 0 <= loss <= 100
            and abs(loss-100*(sent-received)/sent) <= 0.1, "ping_counts")
    timing = re.search(r"(?:rtt|round-trip) [^=]+ = [0-9.]+/([0-9.]+)/[0-9.]+/[0-9.]+ ms", text)
    require(received == 0 or timing is not None, "ping_timing_missing")
    return dict(destination=destination, interface=interface, sent=sent, received=received, loss_pct=loss,
                latency_ms=float(timing[1]) if timing else -1)


class LinuxWifiBackend(LinuxClientReadBackend):
    source = "linux_client/laptop_v1"
    revision = "1.0.0"
    probe_ids = MappingProxyType({fid: "probe.linux."+fid.replace(".", "_") for fid in FUNCTIONS})

    def __init__(self, interface: str | None = None, *, runner=subprocess.run):
        self._run = runner
        self._tools = {name: shutil.which(name) for name in ("ip", "nmcli", "ping", "resolvectl")}
        require(self._tools["ip"] is not None and self._tools["nmcli"] is not None, "linux_tools_missing")
        devices = self._command("nmcli", "-t", "-f", "DEVICE,TYPE,STATE", "device", "status").stdout
        rows = [split_nmcli(line) for line in devices.splitlines() if line]
        wifi = [row for row in rows if len(row) == 3 and row[1] == "wifi"]
        if interface is None:
            wifi.sort(key=lambda row: row[2] != "connected")
            require(bool(wifi), "wifi_interface_unavailable")
            interface = wifi[0][0]
        require(interface in {row[0] for row in wifi}, "not_wifi_interface")
        super().__init__(interface, client_id="local-laptop")

    def _command(self, tool: str, *args: str, timeout: float = 3, codes=(0,)):
        require(self._tools.get(tool) is not None, "linux_tool_unavailable")
        try:
            result = self._run([self._tools[tool], *args], stdin=subprocess.DEVNULL,
                               capture_output=True, text=True, timeout=timeout, check=False,
                               env={**os.environ, "LC_ALL": "C", "LANG": "C"})
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("linux_read_timeout") from exc
        require(result.returncode in codes and len(result.stdout.encode()) <= 65536, "linux_read_failed")
        return result

    def route(self) -> dict:
        result = self._command("ip", "-j", "route", "get", PROBE_IP, codes=(0, 2))
        if result.returncode != 0:
            require("Network is unreachable" in result.stderr or "No route to host" in result.stderr, "route_read_unavailable")
            return dict(has_route=False, interface="", source_ipv4="", gateway="", resolver_fingerprint="")
        try:
            rows = json.loads(result.stdout)
            require(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, "route_shape")
            row = rows[0]
            interface, source, gateway = row["dev"], row.get("prefsrc", row.get("src", "")), row.get("gateway", "")
            require(type(interface) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", interface), "route_interface")
            ipaddress.IPv4Address(source)
            if gateway:
                ipaddress.IPv4Address(gateway)
        except (ValueError, KeyError, TypeError) as exc:
            raise PlanError("binding_v02:malformed_route") from exc
        resolver = self._resolver(interface)
        return dict(has_route=True, interface=interface, source_ipv4=source, gateway=gateway,
                    resolver_fingerprint=digest(resolver) if resolver is not None else "")

    def _resolver(self, interface):
        if self._tools["resolvectl"] is None:
            return None
        dns = self._command("resolvectl", "dns", interface, codes=(0, 1))
        domains = self._command("resolvectl", "domain", interface, codes=(0, 1))
        return (dns.stdout, domains.stdout) if dns.returncode == domains.returncode == 0 else None

    def wifi(self):
        radio = self._command("nmcli", "radio", "wifi").stdout.strip()
        require(radio in {"enabled", "disabled"}, "wifi_radio_status")
        output = self._command("nmcli", "-t", "--escape", "yes", "-f", "IN-USE,SSID,BSSID,SIGNAL,CHAN,FREQ,RATE",
                               "device", "wifi", "list", "--rescan", "no", "ifname", self.interface).stdout
        return parse_wifi(output, interface=self.interface, radio_enabled=radio == "enabled")

    @property
    def environment_id(self):
        # Association/IPv4/route/resolver changes invalidate the whole sample batch.
        wifi = self.wifi()
        stable_wifi = {k: wifi[k] for k in ("interface", "radio_enabled", "associated", "ssid", "bssid")}
        return digest({"kernel": super().environment_id, "route": self.route(),
                       "wifi": stable_wifi, "wifi_ipv4": self._ipv4()})

    def supports(self, fid: str, context: TargetContext) -> bool:
        if fid not in FUNCTIONS or context != TargetContext("client", self.client_id, self.environment_id):
            return False
        if fid.endswith("_probe"):
            route = self.route()
            return bool(self._tools["ping"] and route["has_route"]
                        and (fid != "laptop.gateway_probe" or route["gateway"]))
        if fid == "laptop.dns":
            return bool(self.route()["resolver_fingerprint"])
        return True

    def sample(self, function: dict, arguments: dict, context: TargetContext):
        fid = function["function_id"]
        require(self.supports(fid, context), "linux_network_context_changed")
        if fid == "clients.resolve":
            value, port = {"client_id": self.client_id}, "client.identity"
        elif fid == "client.ipv4":
            value, port = self._ipv4(), "client.ipv4"
        elif fid == "laptop.route":
            value, port = self.route(), fid
        elif fid == "laptop.wifi":
            value, port = self.wifi(), fid
        elif fid.endswith("_probe"):
            route = self.route()
            destination = route["gateway"] if fid == "laptop.gateway_probe" else PROBE_IP
            raw = self._command("ping", "-n", "-c", "4", "-i", "0.2", "-W", "1", "-w", "5",
                                "-I", route["source_ipv4"], "--", destination, timeout=6, codes=(0, 1)).stdout
            value, port = parse_ping(raw, destination=destination, interface=route["interface"]), fid
        elif fid == "laptop.dns":
            route = self.route()
            result = self._command("resolvectl", "--interface="+route["interface"], "--legend=no",
                                   "--cache=no", "query", "--type=A", DOMAIN, timeout=6, codes=(0, 1))
            value, port = dict(query=DOMAIN, resolved=result.returncode == 0, interface=route["interface"]), fid
        else:
            raise PlanError("binding_v02:unregistered_linux_network_function")
        require(context.environment_id == self.environment_id, "linux_environment_changed_during_sample")
        return observations(function, {port: value}, self.source, context)
