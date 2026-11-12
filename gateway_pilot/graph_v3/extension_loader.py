"""Transactional read-only extension overlay for typed Gateway Function registries.

A trusted JSON manifest declares data contracts only, never executable code,
a probe result, a new permission, or shell access. It does not modify frozen
data/registry_v01.json or the 22-Skill/270-requirement product catalog.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

from ..core import PlanError, Registry
from .contracts import Function, Port
from .graphs import Relation


_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{2,100}$")
_TYPES = {"string": "str", "boolean": "bool", "number": "number", "array": "list"}
_PERMISSIONS = {"network.read", "system.read"}


def _require(ok, code):
    if not ok:
        raise PlanError(code)


def _valid_schema(schema):
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise PlanError("extension_port_requires_object_schema")
    properties = schema.get("properties")
    required = schema.get("required")
    if (not isinstance(properties, dict) or not properties
            or not isinstance(required, list)
            or any(name not in properties for name in required)):
        raise PlanError("extension_invalid_port_fields")
    if schema.get("additionalProperties") is not False:
        raise PlanError("extension_requires_closed_schema")
    for key, value in properties.items():
        if (not isinstance(key, str) or not isinstance(value, dict)
                or value.get("type") not in _TYPES
                or "$ref" in value):
            raise PlanError("extension_requires_primitive_port_fields")
    if _has_remote_reference(schema):
        raise PlanError("extension_remote_schema_references_forbidden")
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise PlanError("extension_invalid_json_schema") from exc


def _has_remote_reference(value):
    if isinstance(value, dict):
        return any(k.startswith("$") or _has_remote_reference(v) for k, v in value.items())
    if isinstance(value, list):
        return any(_has_remote_reference(v) for v in value)
    return False


def _finite_json(value):
    if isinstance(value, float) and not math.isfinite(value):
        raise PlanError("extension_nonfinite")
    if isinstance(value, dict):
        for x in value.values():
            _finite_json(x)
    if isinstance(value, list):
        for x in value:
            _finite_json(x)


def _unique(rows, field, existing=()):
    result = {}
    for row in rows:
        _require(isinstance(row, dict), "extension_invalid_item")
        name = row.get(field)
        _require(isinstance(name, str) and _NAME.fullmatch(name) is not None,
                 "extension_invalid_id")
        _require(name not in result and name not in existing,
                 "extension_duplicate_or_overwrite")
        result[name] = row
    return result


def _require_keys(row, expected, optional=()):
    _require(set(row).issubset(set(expected) | set(optional))
             and set(expected).issubset(row), "extension_invalid_fields")


def _strings(values, *, max_items=32):
    return (isinstance(values, list) and len(values) <= max_items
            and len(values) == len(set(map(repr, values)))
            and all(isinstance(x, str) and _NAME.fullmatch(x) for x in values))


def install_extension(registry, manifest: dict | str | Path):
    """Install an audited **in-memory** metadata overlay, or do nothing.

    A failed or malformed extension never partially mutates the source
    Registry. `PROBED_OK` cannot be declared from manifest; v0.1 Functions
    start PROPOSED_NOT_VERIFIED and need separately verified provisioning.
    """
    if isinstance(manifest, (str, Path)):
        # Trusted startup path only; never forward paths from HTTP/LLM.
        manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))
    _require(isinstance(manifest, dict), "extension_invalid_manifest")
    _require_keys(manifest, {"version", "ports", "skills", "functions"})
    _require(manifest["version"] == "1.0", "extension_invalid_version")
    _finite_json(manifest)
    ports = _unique(manifest["ports"], "id", registry.ports)
    skills = _unique(manifest["skills"], "id", registry.skills)
    functions = _unique(manifest["functions"], "id", registry.functions)
    _require(bool(ports) and bool(skills) and bool(functions), "extension_empty_overlay")

    staged = copy.copy(registry)
    staged.ports = dict(registry.ports)
    staged.skills = copy.deepcopy(registry.skills)
    staged.functions = dict(registry.functions)
    staged.relations = list(registry.relations)
    staged.function_conflicts = set(registry.function_conflicts)
    staged.goal_ports = copy.deepcopy(registry.goal_ports)

    for pid, row in ports.items():
        _require_keys(row, {"id", "schema"}, {"scope", "provenance", "untrusted_text"})
        _require(row.get("scope", "gateway") == "gateway"
                 and row.get("provenance", "ubus/") == "ubus/"
                 and row.get("untrusted_text", False) is False,
                 "extension_only_gateway_read_port")
        _valid_schema(row["schema"])
        staged.ports[pid] = Port(pid, "gateway", copy.deepcopy(row["schema"]),
                                 provenance="ubus/")

    for sid, row in skills.items():
        _require_keys(row, {"id", "name", "description", "produces"},
                      {"tags", "requires", "depends_on"})
        _require(isinstance(row["name"], str) and 1 <= len(row["name"]) <= 120
                 and isinstance(row["description"], str)
                 and 1 <= len(row["description"]) <= 1000,
                 "extension_invalid_skill_text")
        requires = row.get("requires", [])
        produces = row["produces"]
        depends_on = row.get("depends_on", [])
        _require(all(_strings(x) for x in (requires, produces, depends_on)),
                 "extension_invalid_skill_lists")
        _require(bool(produces)
                 and set(requires + produces) <= set(staged.ports)
                 and set(depends_on) <= set(staged.skills) | set(skills),
                 "extension_unknown_skill_reference")
        tags = row.get("tags", [])
        _require(isinstance(tags, list) and len(tags) <= 32
                 and all(isinstance(x, str) and 1 <= len(x) <= 50 for x in tags),
                 "extension_invalid_tags")
        staged.skills[sid] = {
            "id": sid, "name": row["name"], "description": row["description"],
            "tags": copy.deepcopy(tags), "requires": list(requires),
            "produces": list(produces), "depends_on": list(depends_on),
            "completion_ports": list(produces), "read_set": list(requires + produces),
            "write_set": [], "required_capabilities": [],
        }
        for dependency in depends_on:
            staged.relations.append(Relation(sid, dependency, "depends_on"))

    for fid, row in functions.items():
        _require_keys(row, {
            "id", "skills", "description", "outputs", "permission",
        }, {"scope", "inputs", "cost", "latency_ms", "timeout_ms", "ttl_seconds"})
        _require(row.get("scope", "gateway") == "gateway",
                 "extension_only_gateway_read_function")
        _require(isinstance(row["description"], str)
                 and 1 <= len(row["description"]) <= 1000,
                 "extension_invalid_function_text")
        _require(row["permission"] in _PERMISSIONS,
                 "extension_permission_not_allowlisted")
        skills_used = row["skills"]
        _require(_strings(skills_used) and bool(skills_used)
                 and set(skills_used) <= set(staged.skills),
                 "extension_unknown_skill_membership")
        inputs, outputs = row.get("inputs", []), row["outputs"]
        _require(_strings(inputs) and _strings(outputs) and len(outputs) == 1
                 and not inputs and all(name in staged.ports for name in outputs),
                 "extension_requires_zero_input_single_output")
        output = staged.ports[outputs[0]]
        _require(output.scope == "gateway" and output.provenance == "ubus/",
                 "extension_function_output_requires_ubus_port")
        for num_key, default in (("cost", 1), ("latency_ms", 1),
                                 ("timeout_ms", 2000), ("ttl_seconds", 30)):
            value = row.get(num_key, default)
            _require(type(value) in (int, float) and math.isfinite(value)
                     and (value > 0 if num_key.endswith(("ms", "seconds")) else value >= 0),
                     "extension_invalid_budget")
        common = dict(
            id=fid, skills=tuple(skills_used), inputs={}, outputs={output.name: output},
            description=row["description"], scope="gateway",
            permission=row["permission"], cost=row.get("cost", 1),
            latency_ms=row.get("latency_ms", 1), timeout_ms=row.get("timeout_ms", 2000),
            arguments_schema={"type": "object", "properties": {},
                              "required": [], "additionalProperties": False},
        )
        if getattr(registry, "contract_format", None) == "v0.1":
            from .registry_v01 import FunctionV01
            function = FunctionV01(
                **common, version="0.1.0", risk="READ_ONLY",
                status="PROPOSED_NOT_VERIFIED", adapter="openwrt_ubus",
                capability_probe="extension.probe." + fid,
                evidence_scope="gateway", ttl_seconds=row.get("ttl_seconds", 30),
            )
        else:
            function = Function(**common, version="0.1.0", risk="READ")
        staged.functions[fid] = function

    # Validate *all* cross-references and graph cycles on a separate object.
    if getattr(registry, "contract_format", None) == "v0.1":
        from .registry_v01 import _replay_view
        staged.legacy = _replay_view(staged)
    else:
        data = copy.deepcopy(registry.legacy.data)
        data["skills"].extend(copy.deepcopy(list(staged.skills[sid] for sid in skills)))
        for f in functions.values():
            data["functions"].append({
                "id": f["id"], "skills": list(f["skills"]),
                "description": f["description"], "requires": [],
                "produces": list(f["outputs"]), "risk": "READ",
                "scope": "gateway", "ttl_s": f.get("ttl_seconds", 30),
            })
        for pid, p in ports.items():
            schema = p["schema"]
            data["port_fields"][pid] = {
                key: _TYPES[value["type"]]
                for key, value in schema["properties"].items()
                if key in schema["required"]
            }
        staged.legacy = Registry(data=data)
    staged.rebuild()  # Cycle/graph/membership/schema validation; may raise.

    manifest_digest = hashlib.sha256(json.dumps(
        manifest, sort_keys=True, ensure_ascii=False, allow_nan=False
    ).encode("utf-8")).hexdigest()
    history = list(getattr(registry, "extension_history", ()))
    history.append({
        "digest_sha256": manifest_digest,
        "ports": sorted(ports), "skills": sorted(skills),
        "functions": sorted(functions), "status": "METADATA_ONLY",
    })
    # Atomic publication after validation. No third-party backend activation.
    for field in ("ports", "functions", "skills", "relations", "legacy",
                  "gs", "gsf", "hf", "_retrieval_graph",
                  "_retrieval_identity", "_registry_revision"):
        setattr(registry, field, getattr(staged, field))
    registry.extension_history = tuple(history)
    return history[-1]
