"""Conservative schema compatibility, tri-state predicates, versioned contracts.

Schema subsumption is proven only for the explicit supported subset. Unknown
keywords/combinators are rejected rather than guessed compatible.
"""
from __future__ import annotations
import copy
import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from jsonschema import Draft202012Validator, FormatChecker

from ..core import PlanError, Registry


class Truth(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


def validate(value, schema):
    return Draft202012Validator(schema, format_checker=FormatChecker()).is_valid(value)


def schema_subset(producer, consumer):
    """Sufficient (not complete) proof that producer instances satisfy consumer."""
    if not isinstance(producer, dict) or not isinstance(consumer, dict):
        return False
    supported = {"$schema", "title", "description", "type", "properties", "required", "additionalProperties",
                 "enum", "const", "minimum", "maximum", "minLength", "maxLength", "items", "minItems", "maxItems", "format"}
    if (set(producer) | set(consumer)) - supported:
        return False
    pt, ct = producer.get("type"), consumer.get("type")
    known_types = {"object", "array", "string", "number", "integer", "boolean", "null"}
    if not isinstance(pt, str) or not isinstance(ct, str) or pt not in known_types or ct not in known_types:
        return False
    if any("additionalProperties" in s and not isinstance(s["additionalProperties"], bool)
           for s in (producer, consumer)):
        return False
    if pt != ct and (pt, ct) != ("integer", "number"):
        return False
    if ct is None:
        return False
    if "const" in producer:
        return validate(producer["const"], consumer)
    if "const" in consumer:
        return False
    if "enum" in producer:
        return all(validate(v, consumer) for v in producer["enum"])
    if "enum" in consumer:
        return False
    for low in ("minimum", "minLength", "minItems"):
        if low in consumer and producer.get(low, float("-inf")) < consumer[low]:
            return False
    for high in ("maximum", "maxLength", "maxItems"):
        if high in consumer and producer.get(high, float("inf")) > consumer[high]:
            return False
    if "format" in consumer and producer.get("format") != consumer["format"]:
        return False
    if ct == "object":
        pp, cp = producer.get("properties", {}), consumer.get("properties", {})
        if not set(consumer.get("required", [])).issubset(producer.get("required", [])):
            return False
        for name, cs in cp.items():
            if name in pp:
                if not schema_subset(pp[name], cs):
                    return False
            elif producer.get("additionalProperties", True) is not False:
                return False
        if consumer.get("additionalProperties", True) is False:
            if producer.get("additionalProperties", True) is not False or set(pp) - set(cp):
                return False
    if ct == "array":
        if "items" in consumer and not schema_subset(producer.get("items", {}), consumer["items"]):
            return False
    return True


@dataclass(frozen=True)
class Port:
    name: str
    scope: str
    schema: dict
    provenance: str = "synthetic_replay/"
    # Free text written by the device (logs): data for display only, never part of a
    # retrieval query, plan input or instruction (T8).
    untrusted_text: bool = False

    def accepts(self, output):
        return (self.name == output.name and self.scope == output.scope
                and output.provenance.startswith(self.provenance)
                and schema_subset(output.schema, self.schema))


NUMERIC_OPS = {"gt": lambda a, b: a > b, "ge": lambda a, b: a >= b,
               "lt": lambda a, b: a < b, "le": lambda a, b: a <= b}


@dataclass(frozen=True)
class Predicate:
    port: str
    field: str = ""
    op: str = "exists"
    value: object = True

    def evaluate(self, state):
        evidence = state.fact(self.port)
        if evidence is None:
            return Truth.UNKNOWN
        if self.op == "exists":
            return Truth.TRUE
        value = evidence["value"]
        for part in self.field.split("."):
            if not isinstance(value, dict) or part not in value:
                return Truth.UNKNOWN
            value = value[part]
        if self.op == "eq":
            result = type(value) is type(self.value) and value == self.value
        elif self.op in NUMERIC_OPS:
            result = (isinstance(value, (int, float)) and not isinstance(value, bool)
                      and NUMERIC_OPS[self.op](value, self.value))
        else:
            raise PlanError("unknown_predicate_operator")
        return Truth.TRUE if result else Truth.FALSE


@dataclass
class Function:
    id: str
    skills: tuple
    inputs: dict[str, Port]
    outputs: dict[str, Port]
    description: str
    scope: str
    cost: float = 1.0
    latency_ms: float = 1.0
    risk: str = "READ"
    permission: str = "network.read"
    version: str = "3.0.0"
    verifier: str = "schema_scope_provenance_freshness/v3"
    predicates: tuple[Predicate, ...] = ()
    order_after: tuple[str, ...] = ()
    timeout_ms: float = 2000
    retry_limit: int = 0
    argument_sources: dict = field(default_factory=dict)
    arguments_schema: dict = field(default_factory=lambda: {
        "type": "object", "properties": {key: {"type": "string", "maxLength": 128} for key in
        ("client_id", "interface", "resolver", "domain")}, "additionalProperties": False})

    def digest(self):
        return hashlib.sha256(json.dumps(self, default=lambda o: o.__dict__, sort_keys=True).encode()).hexdigest()


LEGACY_UNTRUSTED_TEXT = {"system.logs"}  # the v1 data has no flag; v0.1 declares it per port


def from_legacy(legacy=None, *, provenance="synthetic_replay/"):
    """Explicit migration, not edits to the frozen v1 data files."""
    legacy = legacy or Registry()
    scopes = {port: f["scope"] for f in legacy.functions.values() for port in f["produces"]}
    ports = {}
    types = {"str": "string", "bool": "boolean", "number": "number", "list": "array"}
    for name, fields in legacy.data["port_fields"].items():
        schema = {"type": "object", "properties": {k: {"type": types[t]} for k, t in fields.items()},
                  "required": sorted(fields), "additionalProperties": True}
        ports[name] = Port(name, scopes[name], schema, provenance=provenance,
                           untrusted_text=name in LEGACY_UNTRUSTED_TEXT)
    functions = {}
    for fid, f in legacy.functions.items():
        functions[fid] = Function(fid, tuple(f["skills"]), {p: ports[p] for p in f["requires"]},
                                  {p: ports[p] for p in f["produces"]}, f["description"], f["scope"],
                                  risk=f["risk"], permission="system.read" if fid.startswith("system.") else "network.read")
        if f['scope'] == 'client' and fid != 'clients.resolve':
            functions[fid].inputs["client.identity"] = ports["client.identity"]
            functions[fid].argument_sources['client_id'] = ('client.identity', 'client_id')
        if fid == 'dns.probe':
            functions[fid].argument_sources['resolver'] = ('dns.config', 'resolver')
        functions[fid].arguments_schema['required'] = sorted(functions[fid].argument_sources)
    # A probe needs an observed route, not an assumed implication of link up.
    functions["wan.probe"].predicates = (Predicate("wan.routes", "default_route", "eq", True),)
    functions["client.probe"].predicates = (Predicate("client.ipv4", "configured", "eq", True),)
    if "client.dns" in functions:
        functions["client.dns"].predicates = functions["client.probe"].predicates
    return legacy, ports, functions
