"""Bounded, data-only catalog input. Never imports code from catalog paths."""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path

from ..core import PlanError


MAX_FILE_BYTES = 65536
MAX_CATALOG_BYTES = 32 * 1048576
MAX_FILES = 20000


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise PlanError("catalog_v02:" + reason)


def canonical_bytes(value: object) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                           separators=(",", ":")) + "\n").encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise PlanError("catalog_v02:invalid_json_value") from exc


def digest(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _pairs(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate_json_key")
        result[key] = value
    return result


def _number(value: str) -> float:
    result = float(value)
    require(math.isfinite(result), "nonfinite_json_number")
    return result


def _constant(value: str) -> None:
    raise PlanError("catalog_v02:nonfinite_json_constant")


def _read_bytes(path: Path, max_bytes: int) -> bytes:
    require(type(max_bytes) is int and 1 <= max_bytes <= MAX_CATALOG_BYTES, "invalid_byte_limit")
    try:
        require(not path.is_symlink() and path.is_file(), "regular_file_required")
        with path.open("rb") as handle:
            raw = handle.read(max_bytes + 1)
        require(len(raw) <= max_bytes, "file_too_large")
        return raw
    except OSError as exc:
        raise PlanError("catalog_v02:file_unavailable") from exc


def _parse(raw: bytes) -> dict:
    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                              parse_constant=_constant, parse_float=_number)
        require(type(document) is dict, "document_object_required")
        return document
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, PlanError):
            raise
        raise PlanError("catalog_v02:invalid_json_or_depth") from exc


def read_json(path: str | Path, *, max_bytes: int = MAX_FILE_BYTES) -> dict:
    """Read one operator-selected local JSON object, rejecting duplicate keys."""
    return _parse(_read_bytes(Path(path), max_bytes))


def load_catalog(source: str | Path) -> dict:
    """Read Function/Port/Skill documents; validation is a separate step."""
    source = Path(source)
    require(not source.is_symlink() and source.is_dir(), "catalog_directory_required")
    catalog = {"functions": [], "ports": [], "skills": [], "source_digests": {},
               "record_digests": {}, "source_root": str(source.resolve())}
    total = 0
    def walk_error(error):
        raise PlanError("catalog_v02:catalog_walk_failed") from error
    try:
        folders = 0
        for folder, dirs, files in os.walk(source, followlinks=False, onerror=walk_error):
            folders += 1
            require(folders <= MAX_FILES and len(Path(folder).relative_to(source).parts) <= 2,
                    "catalog_directory_limit")
            dirs.sort()
            require(all(not (Path(folder) / name).is_symlink() for name in dirs), "symlink_directory")
            for name in sorted(files):
                path = Path(folder) / name
                require(not path.is_symlink(), "symlink_file")
                if path.suffix != ".json":
                    continue
                relative = path.relative_to(source)
                group = relative.parts[0]
                require(group in ("functions", "ports", "skills"), "unsupported_catalog_layout")
                require(len(relative.parts) == (3 if group == "functions" else 2), "invalid_catalog_layout")
                require(len(catalog["source_digests"]) < MAX_FILES, "catalog_file_limit")
                raw = _read_bytes(path, MAX_FILE_BYTES)
                total += len(raw)
                require(total <= MAX_CATALOG_BYTES, "catalog_byte_limit")
                row = _parse(raw)
                kind = {"functions": "function", "ports": "port", "skills": "skill"}[group]
                require(row.get("kind") == kind, "document_kind_path_mismatch")
                identity = row.get(kind + "_id")
                require(name in (f"{identity}.json", f"{identity}@{row.get('version')}.json"), "document_filename")
                if group == "functions":
                    require(relative.parts[1] == row.get("domain"), "function_domain_path")
                catalog[group].append(row)
                catalog["source_digests"][relative.as_posix()] = hashlib.sha256(raw).hexdigest()
                catalog["record_digests"][f"{kind}:{identity}@{row.get('version')}"] = digest(row)
    except OSError as exc:
        raise PlanError("catalog_v02:catalog_read_failed") from exc
    require(bool(catalog["source_digests"]), "empty_catalog")
    return catalog
