"""Deterministic READ metadata artifacts; no GraphRegistry or adapter binding."""
from __future__ import annotations

import copy
import os
import re
import tempfile
from pathlib import Path, PurePosixPath
from jsonschema import Draft202012Validator

from ..core import ROOT, PlanError
from .contracts import _SCHEMA
from .indexes import GROUP_KEYS, build_indexes
from .loader import MAX_CATALOG_BYTES, MAX_FILES, canonical_bytes, digest, read_json, require
from .validator import select_catalog, validate_catalog, validate_policy


FORMAT = "gateway-lm.catalog-registry"
BUILDER_VERSION = "0.2.0"
_HASH = re.compile(r"[0-9a-f]{64}")
_IDENTIFIERS = {"function": Draft202012Validator(_SCHEMA["$defs"]["id"]),
                "port": Draft202012Validator(_SCHEMA["$defs"]["id"]),
                "skill": Draft202012Validator({"$defs": _SCHEMA["$defs"], "$ref": "#/$defs/skill_id"})}
_VERSION = Draft202012Validator(_SCHEMA["$defs"]["version"])


def _record_digests(catalog: dict) -> dict:
    return {f"{row['kind']}:{row[key]}@{row['version']}": digest(row)
            for group, key in GROUP_KEYS.items() for row in catalog[group]}


def _publish(output: Path, content: bytes) -> None:
    """One file contains records, manifest and indexes: no partial sidecars."""
    require(len(content) <= MAX_CATALOG_BYTES, "artifact_byte_limit")
    temporary = None
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        require(not output.is_symlink(), "artifact_symlink_output")
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".catalog-", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, output)
    except OSError as exc:
        raise PlanError("catalog_v02:artifact_publication_failed") from exc
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def build_registry(catalog: dict, selection: dict, policy: dict,
                   output: str | Path) -> dict:
    """Publish a validated metadata snapshot. Success never grants execution."""
    output = Path(output)
    require(not output.is_symlink(), "artifact_symlink_output")
    try:
        resolved = output.resolve()
    except (OSError, RuntimeError) as exc:
        raise PlanError("catalog_v02:artifact_output_path") from exc
    require(not any(resolved.is_relative_to(ROOT / folder) for folder in ("data", "benchmarks")),
            "protected_baseline_output")
    require(not resolved.is_relative_to(Path(catalog["source_root"])), "output_inside_source_catalog")
    indexed = validate_catalog(catalog, policy)
    require(_record_digests(catalog) == catalog["record_digests"], "source_records_changed_after_load")
    selected = copy.deepcopy(select_catalog(selection, indexed))
    validate_catalog(selected, policy)
    for group, key in GROUP_KEYS.items():
        selected[group].sort(key=lambda row: (row[key], row["version"]))
    artifact = {
        "format": FORMAT, "schema_version": "0.2.0", "execution_enabled": False,
        "selection": copy.deepcopy(selection), **selected,
        "indexes": build_indexes(selected["functions"]),
        "manifest": {
            "builder_version": BUILDER_VERSION,
            "contract_schema_digest": digest(_SCHEMA), "policy_digest": digest(policy),
            "selection_digest": digest(selection),
            "source_digests": copy.deepcopy(catalog["source_digests"]),
            "record_digests": copy.deepcopy(catalog["record_digests"]),
            "catalog_counts": {group: len(catalog[group]) for group in GROUP_KEYS},
        },
    }
    artifact["content_digest"] = digest(artifact)
    verify_registry(artifact, policy)
    _publish(output, canonical_bytes(artifact))
    return artifact


def verify_registry(artifact: dict, policy: dict) -> None:
    """Verify a metadata object against trusted policy, without enabling it."""
    fields = {"format", "schema_version", "execution_enabled", "selection", "functions",
              "ports", "skills", "indexes", "manifest", "content_digest"}
    require(set(artifact) == fields and artifact["format"] == FORMAT
            and artifact["schema_version"] == "0.2.0" and artifact["execution_enabled"] is False,
            "artifact_format_or_execution_flag")
    require(digest({k: v for k, v in artifact.items() if k != "content_digest"}) == artifact["content_digest"],
            "artifact_digest_mismatch")
    validate_policy(policy)
    manifest = artifact["manifest"]
    require(type(manifest) is dict and set(manifest) == {
        "builder_version", "contract_schema_digest", "policy_digest", "selection_digest",
        "source_digests", "record_digests", "catalog_counts"}, "artifact_manifest_fields")
    require(manifest["builder_version"] == BUILDER_VERSION
            and manifest["contract_schema_digest"] == digest(_SCHEMA), "artifact_schema_or_builder_changed")
    require(manifest["policy_digest"] == digest(policy), "artifact_policy_changed")
    require(manifest["selection_digest"] == digest(artifact["selection"]), "artifact_selection_changed")
    indexed = validate_catalog(artifact, policy)
    selected = select_catalog(artifact["selection"], indexed)
    for group, key in GROUP_KEYS.items():
        expected = sorted(selected[group], key=lambda row: (row[key], row["version"]))
        require(expected == artifact[group], "artifact_selection_records_mismatch")
    require(build_indexes(artifact["functions"]) == artifact["indexes"], "artifact_index_mismatch")
    sources, records, counts = (manifest[key] for key in ("source_digests", "record_digests", "catalog_counts"))
    require(type(sources) is dict and type(records) is dict and type(counts) is dict
            and set(counts) == set(GROUP_KEYS), "artifact_source_manifest")
    require(all(type(n) is int and 1 <= n <= MAX_FILES for n in counts.values()), "artifact_catalog_counts")
    require(all(counts[group] >= len(artifact[group]) for group in GROUP_KEYS), "artifact_selected_count")
    require(sum(counts.values()) == len(sources) == len(records) <= MAX_FILES, "artifact_source_count")
    source_counts = {group: 0 for group in GROUP_KEYS}
    for name, checksum in sources.items():
        require(type(name) is str and type(checksum) is str and _HASH.fullmatch(checksum), "artifact_source_hash")
        path = PurePosixPath(name)
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in name
                and path.parts and path.parts[0] in GROUP_KEYS and path.suffix == ".json"
                and path.as_posix() == name
                and len(path.parts) == (3 if path.parts[0] == "functions" else 2), "artifact_source_path")
        source_counts[path.parts[0]] += 1
    require(source_counts == counts, "artifact_source_group_counts")
    require(all(type(k) is str and type(v) is str and _HASH.fullmatch(v) for k, v in records.items()),
            "artifact_record_hash")
    record_counts = {group: 0 for group in GROUP_KEYS}
    for key in records:
        require(key.count(":") == 1 and key.count("@") == 1, "artifact_record_identity")
        kind, reference = key.split(":")
        identity, version = reference.split("@")
        require(kind in _IDENTIFIERS and _IDENTIFIERS[kind].is_valid(identity)
                and _VERSION.is_valid(version), "artifact_record_version")
        record_counts[kind + "s"] += 1
    require(record_counts == counts, "artifact_record_group_counts")
    for key, value in _record_digests(artifact).items():
        require(records.get(key) == value, "artifact_record_digest_mismatch")


def read_registry(path: str | Path, policy: dict) -> dict:
    """Read and revalidate metadata integrity. Hashes are not signatures."""
    artifact = read_json(path, max_bytes=MAX_CATALOG_BYTES)
    verify_registry(artifact, policy)
    return artifact


def report_registry(artifact: dict) -> dict:
    """Summarize a previously verified artifact; never count metadata as tools."""
    return {
        "protocol": "catalog-report/v1", "execution_enabled": False,
        "declared_function_version_count": artifact["manifest"]["catalog_counts"]["functions"],
        "selected_function_count": len(artifact["functions"]),
        "selected_port_count": len(artifact["ports"]), "selected_skill_count": len(artifact["skills"]),
        "target_verified_executable_count": 0, "binding_count": 0,
        "lifecycle_counts": {state: sum(f["lifecycle"] == state for f in artifact["functions"])
                             for state in sorted({f["lifecycle"] for f in artifact["functions"]})},
        "domains": {domain: len(ids) for domain, ids in sorted(artifact["indexes"]["by_domain"].items())},
        "content_digest": artifact["content_digest"],
        "warning": "Metadata only; no registered runtime Functions, bindings or device acceptance.",
    }
