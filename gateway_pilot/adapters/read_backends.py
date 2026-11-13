"""Fixed READ-only conformance providers, not model-callable runtime adapters."""
from __future__ import annotations

import copy
import errno
import platform
import socket
import struct
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from types import MappingProxyType

from .bindings import TargetContext, require
from .results import ToolResult
from ..command_catalog.loader import digest


def observations(function: dict, values: dict, source: str, context: TargetContext) -> ToolResult:
    """Build unverified observations; only Core may later admit evidence."""
    return ToolResult(observations=tuple({
        "id": "sample-" + uuid4().hex, "function_id": function["function_id"],
        "function_version": function["version"], "metadata_function_digest": digest(function),
        "port": pid, "scope": context.scope, "target": context.target_id,
        "environment_id": context.environment_id, "source": source, "status": "OK", "value": copy.deepcopy(value),
        "observed_at": datetime.now(UTC).isoformat(), "age_s": 0, "ttl_s": function["ttl_seconds"],
    } for pid, value in values.items()))


class ReplayReadBackend:
    revision = "1.0.0"
    source = "synthetic_replay/binding_v1"
    probe_ids = MappingProxyType({"clients.resolve": "probe.replay.clients_resolve",
                                  "client.ipv4": "probe.replay.client_ipv4",
                                  "wifi.station": "probe.replay.wifi_station"})

    def __init__(self, values: dict, *, client_id: str):
        self._values = copy.deepcopy(values)
        self.client_id = client_id
        self.environment_id = digest({"kind": "synthetic_replay", "client_id": client_id, "values": self._values})
        TargetContext("client", client_id, self.environment_id)

    def supports(self, function_id: str, context: TargetContext) -> bool:
        return (context == TargetContext("client", self.client_id, self.environment_id)
                and function_id in self._values)

    def sample(self, function: dict, arguments: dict, context: TargetContext) -> ToolResult:
        require(self.supports(function["function_id"], context), "replay_target_or_function")
        return observations(function, self._values[function["function_id"]], self.source, context)


class LinuxClientReadBackend:
    """Local interface identity/IPv4 via kernel APIs; no process or network I/O.

    The seed Wi-Fi contract requires RSSI dBm. This provider deliberately does
    not advertise wifi.station: signal percent is not an equivalent output.
    """
    revision = "1.0.0"
    source = "linux_client/binding_v1"
    functions = frozenset({"clients.resolve", "client.ipv4"})
    probe_ids = MappingProxyType({"clients.resolve": "probe.linux.clients_resolve",
                                  "client.ipv4": "probe.linux.client_ipv4"})

    def __init__(self, interface: str, *, client_id: str = "local-laptop"):
        import re
        require(platform.system() == "Linux", "linux_host_required")
        require(type(interface) is str and re.fullmatch(r"[A-Za-z0-9_.:-]{1,15}", interface), "invalid_interface")
        TargetContext("client", client_id, "0" * 64)
        self.interface, self.client_id = interface, client_id
        # Check existence now and pin interface incarnation alongside boot/netns.
        try:
            self._ifindex = socket.if_nametoindex(interface)
        except OSError as exc:
            from ..core import PlanError
            raise PlanError("binding_v02:linux_interface_unavailable") from exc

    @property
    def environment_id(self) -> str:
        with Path("/proc/sys/kernel/random/boot_id").open(encoding="ascii") as handle:
            boot = handle.read(129).strip()
        require(0 < len(boot) <= 128 and socket.if_nametoindex(self.interface) == self._ifindex,
                "linux_interface_changed")
        return digest({"boot": boot, "kernel": platform.release(), "netns": Path("/proc/self/ns/net").stat().st_ino,
                       "interface": self.interface, "ifindex": self._ifindex})

    def supports(self, function_id: str, context: TargetContext) -> bool:
        return (function_id in self.functions
                and context == TargetContext("client", self.client_id, self.environment_id))

    def _ipv4(self) -> dict:
        import fcntl  # Linux-only import; replay provider remains portable.
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as handle:
                result = fcntl.ioctl(handle.fileno(), 0x8915, struct.pack("256s", self.interface.encode("ascii")))
            return {"address": socket.inet_ntoa(result[20:24]), "configured": True}
        except OSError as exc:
            if exc.errno == errno.EADDRNOTAVAIL:
                return {"address": "", "configured": False}
            raise

    def sample(self, function: dict, arguments: dict, context: TargetContext) -> ToolResult:
        fid = function["function_id"]
        require(self.supports(fid, context), "linux_target_or_function")
        values = ({"client.identity": {"client_id": self.client_id}} if fid == "clients.resolve"
                  else {"client.ipv4": self._ipv4()})
        return observations(function, values, self.source, context)
