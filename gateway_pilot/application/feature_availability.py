"""Advisory Feature availability from a trusted, short-lived Core view.

No backend calls, probes, tool execution, evidence admission or permission
issuance occur here. A conformance report is not a Core capability snapshot.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass

from ..adapters.bindings import TargetContext
from ..command_catalog.indexes import dependency_witness
from ..command_catalog.loader import digest
from ..features.registry import FeatureRegistry, _SCHEMA, require


_ID = re.compile(_SCHEMA["$defs"]["id"]["pattern"])
_VERSION = re.compile(_SCHEMA["$defs"]["version"]["pattern"])
_HASH = re.compile(r"[0-9a-f]{64}")
_STATUSES = frozenset({"AVAILABLE", "UNSUPPORTED", "UNVERIFIED", "PERMISSION_DENIED", "TEMPORARILY_UNAVAILABLE"})


def _hash(value) -> bool:
    return type(value) is str and bool(_HASH.fullmatch(value))


def _permissions(value) -> bool:
    return (type(value) is frozenset and len(value) <= 128
            and all(type(p) is str and 1 <= len(p) <= 128 for p in value))


def _time(value) -> bool:
    # Range checks reject bool, NaN/Infinity and huge integers without float overflow.
    return type(value) in (int, float) and 0 <= value <= 1e12


@dataclass(frozen=True)
class FunctionCapability:
    function_id: str
    version: str
    metadata_digest: str
    status: str

    def __post_init__(self):
        require(type(self.function_id) is str and len(self.function_id) <= 100 and bool(_ID.fullmatch(self.function_id))
                and type(self.version) is str and len(self.version) <= 128 and bool(_VERSION.fullmatch(self.version))
                and _hash(self.metadata_digest) and type(self.status) is str and self.status in _STATUSES,
                "invalid_function_capability")


@dataclass(frozen=True)
class CapabilitySnapshot:
    """Trusted Core advisory input, not a serializable bearer token.

    policy_context_id is the server identity of principal/ACL revision. Only a
    Core integration may populate AVAILABLE; metadata or conformance cannot.
    """
    registry_digest: str
    context: TargetContext
    permissions: frozenset[str]
    policy_context_id: str
    checked_at: float
    expires_at: float
    functions: tuple[FunctionCapability, ...]

    def __post_init__(self):
        require(_hash(self.registry_digest) and isinstance(self.context, TargetContext)
                and _permissions(self.permissions) and _hash(self.policy_context_id), "invalid_snapshot_context")
        require(_time(self.checked_at) and _time(self.expires_at)
                and 0 < self.expires_at - self.checked_at <= 60, "invalid_snapshot_ttl")
        require(type(self.functions) is tuple and len(self.functions) <= 10000
                and all(type(f) is FunctionCapability for f in self.functions), "invalid_snapshot_functions")
        require(len({f.function_id for f in self.functions}) == len(self.functions), "duplicate_snapshot_function")


class AvailabilityService:
    def __init__(self, registry: FeatureRegistry, *, clock=time.monotonic):
        require(isinstance(registry, FeatureRegistry) and callable(clock), "availability_configuration")
        self._registry, self._clock = registry, clock
        catalog = registry.catalog_view()
        self._digest = catalog["registry_digest"]
        self._functions = {f["function_id"]: f for f in catalog["functions"]}
        self._function_digests = {fid: digest(f) for fid, f in self._functions.items()}

    def evaluate(self, feature_id: str, *, context: TargetContext, permissions: frozenset[str],
                 policy_context_id: str, capabilities: CapabilitySnapshot | None = None) -> dict:
        require(isinstance(context, TargetContext) and _permissions(permissions) and _hash(policy_context_id), "trusted_access_context")
        feature = self._registry.get(feature_id)
        report = {"feature_id": feature_id, "version": feature["version"], "status": "UNAVAILABLE",
                  "reason": None, "required": [], "optional": [],
                  "authorizes_execution": False, "health_evaluated": False}
        def stop(reason, status="UNAVAILABLE"):
            report.update(status=status, reason=reason)
            return report
        if not self._registry.enabled(feature_id):
            return stop("FEATURE_DISABLED", "DISABLED")
        if feature["scope"] != context.scope:
            return stop("TARGET_SCOPE_MISMATCH")
        if feature["permission"] not in permissions:
            return stop("PERMISSION_DENIED")
        if capabilities is None:
            return stop("RUNTIME_NOT_CONNECTED")
        if type(capabilities) is not CapabilitySnapshot:
            return stop("INVALID_CAPABILITY_SNAPSHOT")
        if (capabilities.registry_digest != self._digest or capabilities.context != context
                or capabilities.permissions != permissions or capabilities.policy_context_id != policy_context_id):
            return stop("CAPABILITY_CONTEXT_MISMATCH")
        now = self._clock()
        if not _time(now) or not capabilities.checked_at <= now < capabilities.expires_at:
            return stop("CAPABILITY_EXPIRED_OR_FUTURE")
        for entry in capabilities.functions:
            if (entry.function_id not in self._functions or self._functions[entry.function_id]["version"] != entry.version
                    or self._function_digests[entry.function_id] != entry.metadata_digest):
                return stop("CAPABILITY_CONTRACT_MISMATCH")
        decisions = {entry.function_id: entry.status for entry in capabilities.functions}
        for fid, function in self._functions.items():
            if function["scope"] != context.scope:
                decisions[fid] = "TARGET_SCOPE_MISMATCH"
            elif function["permission"] not in permissions:
                decisions[fid] = "PERMISSION_DENIED"
            elif fid not in decisions:
                decisions[fid] = "UNVERIFIED"
        eligible = {(fid, f["version"]): f for fid, f in self._functions.items() if decisions[fid] == "AVAILABLE"}
        order, _ = dependency_witness(eligible, allow_partial=True)
        reachable = {key[0] for key in order}

        def port_report(pid, version):
            candidates = sorted(fid for fid, f in self._functions.items() if f["outputs"].get(pid) == version)
            available = any(fid in reachable for fid in candidates)
            reasons = {fid: ("DEPENDENCY_UNAVAILABLE" if decisions[fid] == "AVAILABLE" and fid not in reachable
                             else decisions[fid]) for fid in candidates}
            reason = "AVAILABLE" if available else ("NO_PRODUCER" if not candidates else
                      (next(iter(reasons.values())) if len(set(reasons.values())) == 1 else "PRODUCERS_UNAVAILABLE"))
            return {"port_id": pid, "version": version, "available": available, "reason": reason,
                    "function_reasons": reasons}
        report["required"] = [port_report(pid, version) for pid, version in sorted(feature["required_ports"].items())]
        report["optional"] = [port_report(pid, version) for pid, version in sorted(feature["optional_ports"].items())]
        if not all(port["available"] for port in report["required"]):
            return stop("REQUIRED_PORT_UNAVAILABLE")
        if not all(port["available"] for port in report["optional"]):
            return stop("OPTIONAL_PORT_UNAVAILABLE", "DEGRADED")
        return stop("ALL_PORTS_AVAILABLE", "READY")
