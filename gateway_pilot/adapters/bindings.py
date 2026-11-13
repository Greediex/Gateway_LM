"""Trusted startup binding selection, separate from runtime authorization."""
from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from types import MappingProxyType
from collections.abc import Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ..core import ROOT, PlanError
from ..command_catalog.builder import verify_registry
from ..command_catalog.contracts import _json_value
from ..command_catalog.loader import canonical_bytes, digest, read_json


_SCHEMA = json.loads((ROOT / "docs/contracts/catalog-v02/binding.schema.json").read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)
_HASH = re.compile(r"[0-9a-f]{64}")


def require(ok: bool, code: str) -> None:
    if not ok:
        raise PlanError("binding_v02:" + code)


def backend_matches(backend, binding: dict, function: dict) -> bool:
    try:
        probes = getattr(backend, "probe_ids", None)
        return (getattr(backend, "revision", None) == binding["backend_revision"]
                and getattr(backend, "source", None) == binding["source"]
                and isinstance(probes, Mapping) and probes.get(function["function_id"]) == function["capability_probe"])
    except Exception:
        return False  # Broken metadata access never approves or leaks payload.


@dataclass(frozen=True)
class TargetContext:
    scope: str
    target_id: str
    environment_id: str

    def __post_init__(self):
        require(type(self.scope) is str and self.scope in {"client", "gateway"} and type(self.target_id) is str
                and 1 <= len(self.target_id) <= 128 and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in self.target_id)
                and type(self.environment_id) is str and bool(_HASH.fullmatch(self.environment_id)), "invalid_context")


def binding_digest(binding: dict) -> str:
    _json_value(binding)
    require(len(canonical_bytes(binding)) <= 4096, "declaration_bytes")
    try:
        _VALIDATOR.validate(binding)
    except ValidationError as exc:
        raise PlanError("binding_v02:invalid_declaration") from exc
    return digest(binding)


def read_binding_declarations(path) -> list[dict]:
    """Read reviewed local declarations, never approval or backend objects."""
    document = read_json(path, max_bytes=1048576)
    require(set(document) == {"schema_version", "bindings"} and document["schema_version"] == "0.2.0",
            "declaration_file_fields")
    rows = document["bindings"]
    require(type(rows) is list and 1 <= len(rows) <= 10000, "declaration_list")
    for row in rows:
        binding_digest(row)
    return rows


def declare_binding(artifact: dict, function_id: str, binding_id: str,
                    backend_id: str, backend, context: TargetContext) -> dict:
    """Create a declaration for review; does not approve it or invoke backend."""
    function = next((f for f in artifact["functions"] if f["function_id"] == function_id), None)
    require(function is not None, "unknown_function")
    result = {
        "schema_version": "0.2.0", "binding_id": binding_id,
        "function_id": function_id, "function_version": function["version"],
        "function_digest": digest(function), "registry_digest": artifact["content_digest"],
        "backend_id": backend_id, "backend_revision": backend.revision, "source": backend.source,
        "scope": context.scope, "target_id": context.target_id, "environment_id": context.environment_id,
    }
    binding_digest(result)
    return result


class BindingSelection:
    """Pin exactly one approved backend per Function for one target context.

    Python service objects and approved digests must come from trusted startup
    code/configuration, never a declaration, HTTP request, model, or plugin path.
    Construction makes no backend calls and creates no runtime capabilities.
    """

    def __init__(self, artifact: dict, policy: dict, bindings: list[dict], *,
                 approved_digests: frozenset[str], backends: dict, context: TargetContext):
        artifact = copy.deepcopy(artifact)
        verify_registry(artifact, policy)
        require(type(bindings) is list and 1 <= len(bindings) <= 10000, "declaration_list")
        require(type(approved_digests) is frozenset and len(approved_digests) <= 10000
                and all(type(pin) is str and _HASH.fullmatch(pin) for pin in approved_digests), "approval_pins")
        require(type(backends) is dict and isinstance(context, TargetContext), "trusted_startup_context")
        self._artifact = artifact
        self._functions = {f["function_id"]: f for f in self._artifact["functions"]}
        self._ports = {p["port_id"]: p for p in self._artifact["ports"]}
        self._context = context
        selected, owners = {}, set()
        for binding in bindings:
            pin = binding_digest(binding)
            require(pin in approved_digests, "binding_not_approved")
            bid, fid = binding["binding_id"], binding["function_id"]
            require(bid not in selected and fid not in owners, "duplicate_binding_assignment")
            require(fid in self._functions, "unknown_bound_function")
            f = self._functions[fid]
            require(binding["registry_digest"] == self._artifact["content_digest"]
                    and binding["function_version"] == f["version"]
                    and binding["function_digest"] == digest(f), "registry_or_contract_pin_mismatch")
            require(f["risk"] == "READ_ONLY" and f["scope"] == binding["scope"], "read_scope_required")
            require((binding["scope"], binding["target_id"], binding["environment_id"])
                    == (context.scope, context.target_id, context.environment_id), "binding_context_mismatch")
            backend = backends.get(binding["backend_id"])
            require(backend is not None and callable(getattr(backend, "supports", None))
                    and callable(getattr(backend, "sample", None)), "unregistered_backend")
            require(backend_matches(backend, binding, f), "backend_pin_mismatch")
            require(all(binding["source"].startswith(self._ports[pid]["provenance"]) for pid in f["outputs"]),
                    "backend_provenance_mismatch")
            selected[bid] = (copy.deepcopy(binding), backend)
            owners.add(fid)
        self._selected = MappingProxyType(selected)

    def registry_digest(self) -> str:
        return self._artifact["content_digest"]

    def binding_ids(self) -> dict[str, str]:
        return {binding["function_id"]: bid for bid, (binding, _) in self._selected.items()}

    def assignments(self) -> dict[str, str]:
        return {binding["function_id"]: binding["backend_id"] for binding, _ in self._selected.values()}

    def checked_binding(self, binding_id: str, context: TargetContext,
                        permissions: frozenset[str]) -> tuple[dict, dict, dict, object]:
        require(type(binding_id) is str and binding_id in self._selected, "unknown_binding")
        require(isinstance(context, TargetContext) and context == self._context, "target_or_environment_changed")
        require(type(permissions) is frozenset and all(type(p) is str for p in permissions), "trusted_permissions")
        binding, backend = self._selected[binding_id]
        function = self._functions[binding["function_id"]]
        require(function["permission"] in permissions, "permission_denied")
        require(backend_matches(backend, binding, function), "backend_changed_after_selection")
        return copy.deepcopy(binding), copy.deepcopy(function), copy.deepcopy(self._ports), backend
