"""Cross-document validation for the closed READ metadata profile."""
from __future__ import annotations

from jsonschema import Draft202012Validator

from .contracts import _SCHEMA, _json_value, validate_contract
from .indexes import GROUP_KEYS, dependency_witness, index_documents
from .loader import MAX_FILES, require
from ..graph_v3.contracts import schema_subset, validate


def validate_policy(policy: dict) -> None:
    """Only trusted operator vocabulary, never capability/probe approval."""
    _json_value(policy)
    require(type(policy) is dict and set(policy) == {"schema_version", "allowed_probe_ids"}, "policy_fields")
    require(policy["schema_version"] == "0.2.0", "policy_version")
    ids = policy["allowed_probe_ids"]
    require(type(ids) is list and 1 <= len(ids) <= 10000, "policy_probe_ids")
    checker = Draft202012Validator(_SCHEMA["$defs"]["id"])
    require(all(checker.is_valid(pid) for pid in ids), "policy_probe_id")
    require(len(ids) == len(set(ids)), "duplicate_policy_probe")


def _resolve(index: dict, identity: str, version: str, kind: str) -> dict:
    require((identity, version) in index, "unknown_" + kind + ":" + identity + "@" + version)
    return index[identity, version]


def _field(schema: dict, path: str, *, required: bool = False) -> dict:
    for name in path.split("."):
        require(schema.get("type") == "object" and name in schema.get("properties", {}), "unknown_source_field")
        if required:
            require(name in schema.get("required", ()), "optional_required_argument_source")
        schema = schema["properties"][name]
    return schema


def _argument_compatible(source: dict, target: dict) -> bool:
    if not schema_subset(source, target):
        return False
    # Core's structural subset proof does not compare string formats. Do not
    # claim an unrestricted source string guarantees an IPv4/date-time value.
    if "const" in source or "enum" in source:
        return True  # schema_subset already validates every possible value.
    if "format" in target and source.get("format") != target["format"]:
        return False
    if target["type"] == "object":
        return all(_argument_compatible(source["properties"][name], child)
                   for name, child in target["properties"].items() if name in source["properties"])
    if target["type"] == "array":
        return _argument_compatible(source["items"], target["items"])
    return True


def validate_catalog(catalog: dict, policy: dict) -> dict:
    """Check all versions. Returns typed identity indexes, not runtime objects."""
    validate_policy(policy)
    references = 0
    documents = 0
    for group, identity in GROUP_KEYS.items():
        rows = catalog.get(group)
        require(type(rows) is list and 1 <= len(rows) <= MAX_FILES, "catalog_group:" + group)
        documents += len(rows)
        require(documents <= MAX_FILES, "catalog_document_limit")
        for row in rows:
            validate_contract(row)
            require(row["kind"] + "_id" == identity, "catalog_group_kind")
            fields = ("inputs", "outputs", "skill_refs", "order_after") if group == "functions" else (
                ("requires", "produces", "function_refs") if group == "skills" else ())
            references += sum(len(row[field]) for field in fields)
            require(references <= 100000, "catalog_reference_limit")
    indexed = index_documents(catalog)
    functions, ports, skills = (indexed[group] for group in ("functions", "ports", "skills"))
    known_ids = {key[0] for key in functions}
    producers = {(pid, version) for f in functions.values() for pid, version in f["outputs"].items()}
    probes = set(policy["allowed_probe_ids"])
    for f in functions.values():
        require(f["risk"] == "READ_ONLY", "read_metadata_profile_only")
        require(f["capability_probe"] in probes, "unknown_probe_id")
        for pid, version in f["inputs"].items():
            port = _resolve(ports, pid, version, "port")
            require(port["scope"] == f["scope"], "input_scope_mismatch")
            require((pid, version) in producers, "dependency_missing_producer:" + pid)
        for pid, version in f["outputs"].items():
            port = _resolve(ports, pid, version, "port")
            require(port["scope"] == f["scope"], "output_scope_mismatch")
        for ref in f["skill_refs"]:
            skill = _resolve(skills, ref["skill_id"], ref["version"], "skill")
            require(skill["function_refs"].get(f["function_id"]) == f["version"], "skill_membership_mismatch")
        for argument, (pid, field) in f["argument_sources"].items():
            port = ports[pid, f["inputs"][pid]]
            source = _field(port["schema"], field, required=argument in f["arguments_schema"]["required"])
            require(_argument_compatible(source, f["arguments_schema"]["properties"][argument]), "argument_schema_mismatch")
        for predicate in f["preconditions"]:
            port = ports[predicate["port"], f["inputs"][predicate["port"]]]
            if predicate["field"]:
                field = _field(port["schema"], predicate["field"])
                if predicate["op"] in {"gt", "ge", "lt", "le"}:
                    require(field["type"] in {"number", "integer"}, "predicate_field_not_numeric")
                elif predicate["op"] == "eq":
                    require(validate(predicate["value"], field), "predicate_value_schema")
        require(set(f["order_after"]) <= known_ids, "unknown_order_function")
    for skill in skills.values():
        member_inputs, member_outputs = set(), set()
        for fid, version in skill["function_refs"].items():
            f = _resolve(functions, fid, version, "skill_function")
            require({"skill_id": skill["skill_id"], "version": skill["version"]} in f["skill_refs"],
                    "function_membership_mismatch")
            member_inputs.update(f["inputs"].items())
            member_outputs.update(f["outputs"].items())
        for field in ("requires", "produces", "completion_ports"):
            for pid, version in skill[field].items():
                _resolve(ports, pid, version, "skill_port")
        require(set(skill["requires"].items()) <= member_inputs, "skill_required_port_not_consumed")
        require(set(skill["produces"].items()) <= member_outputs, "skill_produced_port_not_produced")
    dependency_witness(functions)
    return indexed


def select_catalog(selection: dict, indexed: dict) -> dict:
    validate_contract(selection)
    require(selection["kind"] == "selection", "selection_kind")
    selected = {"functions": [], "ports": [], "skills": []}
    for group in ("functions", "ports"):
        for identity, version in sorted(selection[group].items()):
            selected[group].append(_resolve(indexed[group], identity, version, "selected_" + group))
    skill_versions = {}
    for f in selected["functions"]:
        require(f["lifecycle"] not in {"DEPRECATED", "RETIRED"}, "inactive_selected_function")
        for ref in f["skill_refs"]:
            sid, version = ref["skill_id"], ref["version"]
            require(sid not in skill_versions or skill_versions[sid] == version, "multiple_selected_skill_versions")
            skill_versions[sid] = version
    for sid, version in sorted(skill_versions.items()):
        selected["skills"].append(indexed["skills"][sid, version])
    return selected
