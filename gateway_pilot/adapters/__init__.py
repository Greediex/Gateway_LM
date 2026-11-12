"""GATEWAY_DESIGN: the adapter boundary (T8).

An adapter accepts only typed actions: a registered Function id and arguments
already validated against that Function's argument schema. There is no generic
command or shell path. ``probe()`` reports which Functions the adapter can
actually serve; the hard gate drops every Function whose probe is not
``PROBE_OK`` before planning. Adapter output is untrusted data: it is parsed
against the port schema by ``core.execute`` and never used as an instruction.
"""
from __future__ import annotations

import os

from ..core import PlanError, execute

PROBE_OK = "PROBE_OK"
PROBE_FAILED = "PROBE_FAILED"
NOT_VERIFIED = "PROPOSED_NOT_VERIFIED"


class Adapter:
    """Interface: ``probe() -> {function_id: status}``; ``call(fid, arguments, state, case) -> observation``."""

    name = "adapter"

    def probe(self):
        raise NotImplementedError

    def call(self, function_id, arguments, state, case):
        raise NotImplementedError

    def _check(self, function_id, arguments):
        if not isinstance(function_id, str) or not isinstance(arguments, dict):
            raise PlanError("adapter_requires_typed_action")
        if self.probe().get(function_id) != PROBE_OK:
            raise PlanError("adapter_function_not_probed:" + str(function_id))


class ReplayAdapter(Adapter):
    """Synthetic replay through the existing ``core.execute``; every listed capability probes OK."""

    name = "synthetic_replay"

    def __init__(self, registry, capabilities):
        self.registry, self.capabilities = registry, tuple(capabilities)

    def probe(self):
        return {fid: PROBE_OK if fid in self.registry.functions else PROBE_FAILED for fid in self.capabilities}

    def call(self, function_id, arguments, state, case):
        self._check(function_id, arguments)
        return execute(function_id, arguments, state, case, self.registry.legacy)


class WindowsLiveAdapter(Adapter):
    """Read-only measurements from the host through ``windows_live.read_observation``."""

    name = "windows_live"

    def __init__(self, registry, functions):
        self.registry, self.functions = registry, tuple(functions)

    def probe(self):
        status = PROBE_OK if os.name == "nt" else PROBE_FAILED
        return {fid: status for fid in self.functions}

    def call(self, function_id, arguments, state, case):
        from ..windows_live import read_observation
        self._check(function_id, arguments)
        return execute(function_id, arguments, state, {**case, "live_reader": read_observation}, self.registry.legacy)


# Function -> (ubus object, method). Every entry is unknown until the board,
# firmware and read-only access are provided; names are never guessed.
OPENWRT_UBUS_MAP = {
    "clients.resolve": None, "client.ipv4": None, "wifi.station": None, "wan.status": None,
    "wan.routes": None, "wan.probe": None, "dns.config": None, "dns.probe": None,
    "dhcp.leases": None, "dhcp.pool": None, "dhcp.service": None, "system.resources": None,
    "system.logs": None, "client.probe": None, "client.dns": None,
}


class OpenWrtUbusAdapter(Adapter):
    """Skeleton only (BLOCKED on board access). Probes fail, calls are refused."""

    name = "openwrt_ubus"
    mapping = OPENWRT_UBUS_MAP

    def probe(self):
        return {fid: PROBE_FAILED for fid in self.mapping}

    def status(self):
        return {fid: NOT_VERIFIED for fid in self.mapping}

    def call(self, function_id, arguments, state, case):
        raise PlanError("openwrt_adapter_not_verified:" + str(function_id))


def gate_capabilities(capabilities, probe):
    """Split capabilities into probed-OK and failed {function_id: reason}."""
    allowed = [fid for fid in capabilities if probe.get(fid) == PROBE_OK]
    failed = {fid: probe.get(fid, "NOT_PROBED") for fid in capabilities if probe.get(fid) != PROBE_OK}
    return allowed, failed


# Expose composite dispatch while retaining the legacy Adapter API.
from .composite import CompositeAdapter  # noqa: E402,F401
from .results import ToolResult  # noqa: E402,F401
from .ubus_read import UbusReadAdapter, UbusReadBinding  # noqa: E402,F401
