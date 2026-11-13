"""Validate one v0.2 metadata contract without loading a registry or backend.

This establishes the document boundary only. Cross-document references,
bindings, capability attestations and execution policy belong to later gates.
"""
from __future__ import annotations

import json
import math
import re

from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import SchemaError, ValidationError

from ..core import ROOT, PlanError


SCHEMA_PATH = ROOT / "docs/contracts/catalog-v02/contract.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(_SCHEMA)
_FIELD = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*")


def _require(ok, reason):
    if not ok:
        raise PlanError("invalid_contract_v02:" + reason)


def _json_value(value, depth=0, count=None):
    """Bound Python document trees before serialization/schema recursion."""
    count = [0, 0] if count is None else count
    count[0] += 1
    _require(depth <= 20 and count[0] <= 50000, "document_complexity")
    _require(type(value) in (dict, list, str, int, float, bool, type(None)), "json_type")
    if type(value) is str:
        count[1] += len(value)
        _require(count[1] <= 1048576, "document_characters")
    if type(value) is float:
        _require(math.isfinite(value), "nonfinite_number")
    if type(value) is dict:
        for key, child in value.items():
            _require(type(key) is str, "json_key")
            _json_value(key, depth + 1, count)
            _json_value(child, depth + 1, count)
    elif type(value) is list:
        for child in value:
            _json_value(child, depth + 1, count)


def _payload_schema(schema):
    """Check meaning within the Core-compatible schema keyword subset."""
    Draft202012Validator.check_schema(schema)
    kind = schema["type"]
    groups = (
        ({"properties", "required", "additionalProperties"}, {"object"}),
        ({"items", "minItems", "maxItems"}, {"array"}),
        ({"minLength", "maxLength", "format"}, {"string"}),
        ({"minimum", "maximum"}, {"integer", "number"}),
    )
    for keywords, kinds in groups:
        _require(not keywords.intersection(schema) or kind in kinds, "schema_keyword_type")
    for low, high in (("minimum", "maximum"), ("minLength", "maxLength"), ("minItems", "maxItems")):
        if low in schema and high in schema:
            _require(schema[low] <= schema[high], "schema_range")
    properties = schema.get("properties", {})
    _require(set(schema.get("required", ())) <= properties.keys(), "schema_required_field")
    for child in properties.values():
        _payload_schema(child)
    if "items" in schema:
        _payload_schema(schema["items"])
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    for value in schema.get("enum", ()):
        _require(validator.is_valid(value), "schema_enum_value")
    if "const" in schema:
        _require(validator.is_valid(schema["const"]), "schema_const_value")


def validate_contract(document: dict) -> None:
    """Raise PlanError for invalid metadata; success grants no capability.

    Accepts an already parsed document. Strict file parsing (including duplicate
    JSON keys) and cross-catalog validation are deliberately not implemented here.
    """
    _json_value(document)
    _require(type(document) is dict, "document_object")
    limit = 1048576 if document.get("kind") == "selection" else 65536
    try:
        size = len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise PlanError("invalid_contract_v02:json_encoding") from exc
    _require(size <= limit, "document_bytes")
    try:
        _VALIDATOR.validate(document)
        if document["kind"] == "port":
            _payload_schema(document["schema"])
        elif document["kind"] == "skill":
            _require(all(document["produces"].get(pid) == version
                         for pid, version in document["completion_ports"].items()),
                     "skill_completion_port")
        elif document["kind"] == "function":
            _payload_schema(document["arguments_schema"])
            properties = document["arguments_schema"]["properties"]
            sources = document["argument_sources"]
            _require(set(sources) <= properties.keys(), "argument_name")
            _require(set(document["arguments_schema"]["required"]) <= sources.keys(), "argument_source_missing")
            _require(all(port in document["inputs"] for port, _ in sources.values()), "argument_input")
            skill_ids = [ref["skill_id"] for ref in document["skill_refs"]]
            _require(len(skill_ids) == len(set(skill_ids)), "multiple_skill_versions")
            _require(document["function_id"] not in document["order_after"], "self_order")
            _require(set(document["effects"]) <= document["outputs"].keys(), "effect_output")
            for predicate in document["preconditions"]:
                _require(predicate["port"] in document["inputs"], "predicate_input")
                field = predicate["field"]
                _require(bool(_FIELD.fullmatch(field)) or (not field and predicate["op"] == "exists"), "predicate_field")
                if predicate["op"] in {"gt", "ge", "lt", "le"}:
                    _require(type(predicate["value"]) in (int, float), "predicate_numeric_value")
    except (SchemaError, ValidationError) as exc:
        raise PlanError("invalid_contract_v02:schema:" + exc.message) from exc
