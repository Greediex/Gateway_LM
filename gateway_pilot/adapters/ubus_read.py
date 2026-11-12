"""Explicit read-only OpenWrt ubus Function binding (transport injected).

No firmware mapping or object/method is guessed. A trusted firmware-specific
transport must implement probe(object_name, method_name) -> bool and
read(object_name, method_name, arguments) -> mapping, with its own deadline.
This does not include a shell executor or imply board-backed validation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from collections.abc import Mapping
from uuid import uuid4

from ..core import PlanError
from . import Adapter, PROBE_FAILED, PROBE_OK
from .results import ToolResult


_IDENTIFIER = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")


@dataclass(frozen=True)
class UbusReadBinding:
    object_name: str
    method_name: str

    def __post_init__(self):
        if (not isinstance(self.object_name, str) or not _IDENTIFIER.fullmatch(self.object_name)
                or not isinstance(self.method_name, str) or not _IDENTIFIER.fullmatch(self.method_name)):
            raise ValueError("invalid_ubus_binding_name")


class UbusReadAdapter(Adapter):
    """Fail-closed adapter for explicitly mapped gateway READ-only Functions."""

    name = "openwrt_ubus_verified"

    def __init__(self, registry, bindings: Mapping[str, UbusReadBinding], transport):
        if not isinstance(bindings, Mapping) or not bindings:
            raise ValueError("ubus_bindings_required")
        if not callable(getattr(transport, "probe", None)) or not callable(
            getattr(transport, "read", None)
        ):
            raise ValueError("ubus_transport_required")
        self.registry, self.transport = registry, transport
        self.bindings = {}
        for fid, binding in bindings.items():
            f = registry.functions.get(fid)
            if (f is None or not isinstance(binding, UbusReadBinding)
                    or f.risk not in {"READ", "READ_ONLY"} or f.scope != "gateway"
                    or len(f.outputs) != 1 or f.inputs):
                raise ValueError("ubus_requires_registered_gateway_read_function")
            port = next(iter(f.outputs.values()))
            if port.scope != "gateway" or port.provenance != "ubus/":
                raise ValueError("ubus_requires_verified_port_provenance")
            if getattr(registry, "contract_format", None) == "v0.1" and (
                getattr(f, "adapter", None) != "openwrt_ubus"
                or getattr(f, "status", None) != "PROBED_OK"
            ):
                raise ValueError("ubus_requires_explicit_firmware_contract")
            self.bindings[fid] = binding

    def probe(self):
        discovered = {}
        for fid, binding in self.bindings.items():
            try:
                ok = self.transport.probe(binding.object_name, binding.method_name)
            except (OSError, RuntimeError, ValueError, TimeoutError):
                ok = False
            discovered[fid] = PROBE_OK if ok is True else PROBE_FAILED
        return discovered

    def call(self, function_id, arguments, state, case):
        self._check(function_id, arguments)
        binding = self.bindings[function_id]
        try:
            raw = self.transport.read(
                binding.object_name, binding.method_name, dict(arguments)
            )
        except (OSError, RuntimeError, ValueError, TimeoutError, TypeError) as exc:
            raise PlanError("ubus_transport_failed") from exc
        if not isinstance(raw, Mapping):
            raise PlanError("ubus_unstructured_response")
        f = self.registry.functions[function_id]
        output_port = next(iter(f.outputs))
        evidence = {
            "id": "ubus-" + uuid4().hex,
            "function_id": function_id,
            "port": output_port,
            "scope": "gateway",
            "target": state.gateway_id,
            "source": "ubus/verified",
            "status": "OK",
            "value": dict(raw),
            "age_s": 0,
            "ttl_s": 0,  # verifier replaces with the Function contract TTL
            "observed_at": datetime.now(timezone.utc).isoformat(),
        }
        return ToolResult(observations=(evidence,))
