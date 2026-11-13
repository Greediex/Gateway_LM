"""READ-only Feature metadata registered against a pinned Catalog snapshot."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from ..core import ROOT, PlanError
from ..command_catalog.builder import verify_registry
from ..command_catalog.contracts import _json_value
from ..command_catalog.loader import canonical_bytes, read_json


_SCHEMA = json.loads((ROOT / "docs/contracts/catalog-v02/feature.schema.json").read_text())
_VALIDATOR = Draft202012Validator(_SCHEMA)


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise PlanError("feature_v02:" + reason)


def _validate_manifest(manifest: dict) -> None:
    _json_value(manifest)
    require(len(canonical_bytes(manifest)) <= 16384, "manifest_byte_limit")
    try:
        _VALIDATOR.validate(manifest)
    except ValidationError as exc:
        raise PlanError("feature_v02:invalid_manifest") from exc
    require(not set(manifest["required_ports"]).intersection(manifest["optional_ports"]), "overlapping_port_roles")


def read_feature_manifests(path: str | Path) -> list[dict]:
    document = read_json(path, max_bytes=1048576)
    require(set(document) == {"schema_version", "features"} and document["schema_version"] == "0.2.0", "manifest_file_fields")
    rows = document["features"]
    require(type(rows) is list and 1 <= len(rows) <= 128, "feature_count")
    for row in rows:
        _validate_manifest(row)
    return rows


def read_feature_flags(path: str | Path) -> dict[str, bool]:
    document = read_json(path, max_bytes=1048576)
    require(set(document) == {"schema_version", "enabled"} and document["schema_version"] == "0.2.0", "flags_file_fields")
    flags = document["enabled"]
    require(type(flags) is dict and len(flags) <= 128
            and all(type(key) is str and type(value) is bool for key, value in flags.items()), "invalid_flags")
    return flags


class FeatureRegistry:
    """One Feature version per ID; metadata/flags never register Functions."""
    def __init__(self, artifact: dict, policy: dict, manifests: list[dict], flags: dict[str, bool]):
        artifact, manifests, flags = copy.deepcopy((artifact, manifests, flags))
        verify_registry(artifact, policy)
        require(type(manifests) is list and 1 <= len(manifests) <= 128, "feature_count")
        _json_value(manifests)
        require(type(flags) is dict and len(flags) <= 128
                and all(type(key) is str and type(value) is bool for key, value in flags.items()), "invalid_flags")
        ports = {port["port_id"]: port for port in artifact["ports"]}
        registered = {}
        for manifest in manifests:
            _validate_manifest(manifest)
            fid = manifest["feature_id"]
            require(fid not in registered, "duplicate_feature_id")
            for pid, version in {**manifest["required_ports"], **manifest["optional_ports"]}.items():
                require(pid in ports and ports[pid]["version"] == version, "unknown_feature_port_version")
                require(ports[pid]["scope"] == manifest["scope"], "feature_port_scope_mismatch")
            registered[fid] = manifest
        require(set(flags) <= registered.keys(), "unknown_feature_flag")
        self._features, self._flags, self._artifact = registered, flags, artifact

    def describe(self) -> list[dict]:
        return [copy.deepcopy(self._features[fid]) for fid in sorted(self._features)]

    def get(self, feature_id: str) -> dict:
        require(type(feature_id) is str and feature_id in self._features, "unknown_feature")
        return copy.deepcopy(self._features[feature_id])

    def enabled(self, feature_id: str) -> bool:
        self.get(feature_id)
        return self._flags.get(feature_id, False)

    def catalog_view(self) -> dict:
        return copy.deepcopy({"registry_digest": self._artifact["content_digest"],
                              "functions": self._artifact["functions"], "ports": self._artifact["ports"]})
