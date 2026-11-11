"""GATEWAY_DESIGN: validated, opt-in v0.1 contracts and replay compatibility view.

Only data/ files are needed at runtime. No legacy migration rules or catalog in
runs/ are consulted. The compatibility Registry serves the existing read-only
adapter; GraphRegistry and CaseState enforce the richer v0.1 policy first.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from ..core import ROOT, PlanError, Registry, read_json
from .contracts import NUMERIC_OPS, Function, Port, Predicate
from .graphs import GraphRegistry, Relation


REGISTRY_PATH = ROOT / "data/registry_v01.json"
REQUIREMENTS_PATH = ROOT / "data/requirements_v01.json"
CATALOG_PATH = ROOT / "data/workflow_catalog_v01.json"
SKILL_RELATIONS = {"depends_on", "composes_with", "similar_to", "specializes", "conflicts_with"}
EXTENSION_RELATIONS = {"produces_for", "workflow", "alternative_to"}


def _object(properties, required=None):
    return {"type": "object", "properties": properties,
            "required": list(properties) if required is None else required, "additionalProperties": False}


TEXT = {"type": "string", "minLength": 1}
STRINGS = {"type": "array", "items": TEXT, "uniqueItems": True}
SCOPE = {"enum": ["gateway", "client"]}
PREDICATE = _object({"port": TEXT, "field": {"type": "string"},
                     "op": {"enum": ["exists", "eq", "gt", "ge", "lt", "le"]}, "value": {}})
FACT_SCHEMA = _object({"fact": {"type": "string", "pattern": "^(router|client)_[a-z_]+$"}, "scope": SCOPE,
                      "port": TEXT, "field": {"type": "string"},
                      "op": {"enum": ["exists", "eq", "gt", "ge", "lt", "le"]}, "value": {}},
                     required=["fact", "scope", "port", "op"])
PORT_MAP = {"type": "object", "additionalProperties": TEXT}
FUNCTION_SCHEMA = _object({
    "function_id": TEXT, "version": TEXT,
    "status": {"enum": ["PROPOSED_NOT_VERIFIED", "REPLAY_ONLY", "PROBED_OK", "PROBE_FAILED"]},
    "adapter": TEXT, "skill_ids": {**STRINGS, "minItems": 1}, "requirement_refs": STRINGS,
    "description": TEXT, "inputs": PORT_MAP, "outputs": {**PORT_MAP, "minProperties": 1},
    "preconditions": {"type": "array", "items": PREDICATE}, "effects": STRINGS,
    "risk": {"enum": ["READ_ONLY", "PROBE", "WRITE"]}, "permission": TEXT,
    "capability_probe": TEXT, "verifier": TEXT, "evidence_scope": SCOPE,
    "ttl_seconds": {"type": "number", "exclusiveMinimum": 0},
    "timeout_ms": {"type": "number", "exclusiveMinimum": 0},
    "retry": _object({"max_attempts": {"type": "integer", "minimum": 1}}),
    "cost": {"type": "number", "minimum": 0}, "latency_ms": {"type": "number", "minimum": 0},
    "order_after": STRINGS,
    "argument_sources": {"type": "object", "additionalProperties": {
        "type": "array", "prefixItems": [TEXT, TEXT], "items": False, "minItems": 2}},
    "arguments_schema": {"type": "object"},
    "on_unknown": {"const": "BLOCK_AND_REQUEST_EVIDENCE"},
})
SKILL_SCHEMA = _object({
    "skill_id": TEXT, "version": TEXT, "name": TEXT, "description": TEXT,
    **{key: STRINGS for key in ("tags", "requires", "produces", "completion_ports", "read_set",
                                "write_set", "required_capabilities")},
})
WORKFLOW_SCHEMA = _object({
    "workflow_id": TEXT, "title": TEXT, "symptoms": STRINGS,
    "kind": {"enum": ["LOOKUP", "DIAGNOSE", "CHANGE", "MONITOR", "OTHER"]},
    "target_scope": SCOPE, "skill_ids": STRINGS, "goal_ports": STRINGS,
    "minimal_goals": STRINGS, "claims": STRINGS,
    "status": {"enum": ["SUPPORTED", "PARTIAL", "CATALOG_ONLY"]},
    "html_workflow_id": TEXT,
    "covered_by": TEXT,
    "tags": STRINGS,
    "partial_claims": STRINGS,
}, required=["workflow_id", "title", "symptoms", "kind", "target_scope", "skill_ids",
             "goal_ports", "minimal_goals", "claims", "status"])
SHA256 = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
CATALOG_SCHEMA = _object({
    "version": {"const": "0.1.0"}, "source": TEXT, "source_sha256": SHA256,
    "html_source": TEXT, "html_source_sha256": SHA256,
    "skills": {"type": "array", "minItems": 22, "maxItems": 22,
               "items": _object({"skill_id": TEXT, "title": TEXT})},
    "workflows": {"type": "array", "minItems": 101, "maxItems": 101,
                  "items": _object({"workflow_id": TEXT, "title": TEXT,
                                    "symptoms": STRINGS, "skill_ids": STRINGS})},
})
# C1 reference vocabulary from workflow.py / dynamic_policy.py. These are
# diagnosis identifiers, not executable claim predicates (the latter is C4).
WORKFLOW_CLAIMS = {
    "wan_link_down", "wan_no_route", "wan_packet_loss", "gateway_dns_failure",
    "gateway_ip_reachable_dns_unverified", "no_fault_observed", "dhcp_pool_exhausted",
    "dhcp_service_down", "client_no_lease", "system_memory_pressure", "system_cpu_load",
    "system_storage_full", "client_not_associated", "wifi_weak_signal",
    "client_ipv4_unconfigured", "client_path_loss", "client_dns_failure",
    "client_ip_reachable", "client_path_unverified",
}


def _relation_schema(kinds):
    return _object({"source": TEXT, "target": TEXT, "type": {"enum": sorted(kinds)},
                    "weight": {"type": "number", "exclusiveMinimum": 0}, "origin": TEXT, "reason": TEXT})


REGISTRY_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    **_object({
        "version": {"const": "0.1.0"},
        "ports": {"type": "object", "minProperties": 1, "additionalProperties": _object({
            "schema_id": TEXT, "scope": SCOPE, "schema": {"type": "object"}, "provenance": TEXT,
            "untrusted_text": {"type": "boolean"}}, required=["schema_id", "scope", "schema", "provenance"])},
        "skills": {"type": "array", "minItems": 1, "items": SKILL_SCHEMA},
        "functions": {"type": "array", "minItems": 1, "items": FUNCTION_SCHEMA},
        "relations": {"type": "array", "items": _relation_schema(SKILL_RELATIONS)},
        "extension_relations": {"type": "array", "items": _relation_schema(EXTENSION_RELATIONS)},
        "conflicts": {"type": "array", "items": {**STRINGS, "minItems": 2, "maxItems": 2}},
        "workflow_evidence": {"type": "object", "additionalProperties": STRINGS},
        "workflows": {"type": "array", "items": WORKFLOW_SCHEMA},
        "facts": {"type": "array", "items": FACT_SCHEMA},
        "claims": {"type": "array", "items": {"type": "object"}},
    }),
}
REQUIREMENTS_SCHEMA = _object({
    "version": {"const": "0.1.0"}, "source": TEXT,
    "source_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "requirements": {"type": "array", "minItems": 270, "maxItems": 270, "items": _object({
        "requirement_id": {"type": "string", "pattern": "^F[0-9]{3}$"},
        "title": {"type": ["string", "null"], "minLength": 1}, "title_missing": {"type": "boolean"},
    })},
})


@dataclass
class FunctionV01(Function):
    """New metadata participates in digests without changing legacy Function."""
    status: str = "PROPOSED_NOT_VERIFIED"
    adapter: str = ""
    requirement_refs: list[str] = field(default_factory=list)
    effects: list[str] = field(default_factory=list)
    capability_probe: str = ""
    evidence_scope: str = ""
    ttl_seconds: float = 30
    on_unknown: str = "BLOCK_AND_REQUEST_EVIDENCE"


@dataclass(frozen=True)
class RelationV01(Relation):
    origin: str = ""
    reason: str = ""


def _finite_json(value):
    # json.loads accepts NaN/Infinity, which are not JSON numbers. Reject them
    # even in nested predicate values, not just cost/deadline fields.
    if isinstance(value, float) and not math.isfinite(value):
        raise PlanError("nonfinite_registry_number")
    if isinstance(value, dict):
        for child in value.values():
            _finite_json(child)
    elif isinstance(value, list):
        for child in value:
            _finite_json(child)


@dataclass(frozen=True)
class FactAssertion:
    """Declared observation -> scoped fact mapping (T7). Evaluated on verified facts only."""
    fact: str
    scope: str
    predicate: Predicate


def fact_assertions(rows, ports):
    """Validate the registry's fact block against typed ports.

    A fact's scope must equal its port's scope, so a gateway observation can
    never yield a client fact; names carry the scope (router_*/client_*).
    """
    result, seen = [], set()
    for row in rows:
        _validate(row, FACT_SCHEMA)
        name, port = row["fact"], ports.get(row["port"])
        if name in seen:
            raise PlanError("duplicate_fact:" + name)
        if port is None:
            raise PlanError("unknown_fact_port:" + name)
        if row["scope"] != port.scope or name.split("_", 1)[0] != {"gateway": "router", "client": "client"}[port.scope]:
            raise PlanError("fact_scope_mismatch:" + name)
        if row["op"] != "exists":
            if row.get("field", "") not in port.schema.get("properties", {}):
                raise PlanError("unknown_fact_field:" + name)
            if row["op"] in NUMERIC_OPS and type(row["value"]) not in (int, float):
                raise PlanError("invalid_numeric_fact:" + name)
        seen.add(name)
        result.append(FactAssertion(name, row["scope"], Predicate(row["port"], row.get("field", ""), row["op"],
                                                                  row.get("value", True))))
    return tuple(result)


def default_fact_assertions(ports, path=None):
    """Fact block of the shipped v0.1 registry, restricted to ports that exist.

    Lets a legacy-contract registry use the same declared mapping without
    loading the full v0.1 contract set.
    """
    rows = [row for row in read_json(path or REGISTRY_PATH).get("facts", ()) if row["port"] in ports]
    return fact_assertions(rows, ports)


def _validate(data, schema):
    _finite_json(data)
    try:
        Draft202012Validator(schema).validate(data)
    except ValidationError as exc:
        location = ".".join(map(str, exc.absolute_path))
        raise PlanError(f"invalid_registry_v01:{location}:{exc.message}") from exc


def _index(rows, key):
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise PlanError("duplicate_registry_id:" + key)
    return result


def _known(names, candidates, error):
    if not set(names).issubset(candidates):
        raise PlanError(error)


def load_registry(path=REGISTRY_PATH, *, requirements_path=REQUIREMENTS_PATH,
                  catalog_path=CATALOG_PATH, registry_class=GraphRegistry):
    """Build all four registry views from validated data, without legacy defaults.

    requirements_path defaults to the shipped data/ copy, including when path
    points to a temporary candidate contract. No schema uses remote references.
    """
    data, requirements, catalog = read_json(path), read_json(requirements_path), read_json(catalog_path)
    _validate(data, REGISTRY_SCHEMA)
    _validate(requirements, REQUIREMENTS_SCHEMA)
    _validate(catalog, CATALOG_SCHEMA)
    design_skills = _index(catalog["skills"], "skill_id")
    design_workflows = _index(catalog["workflows"], "workflow_id")
    if (set(design_skills) != {f"SK{i:02}" for i in range(1, 23)} or
            set(design_workflows) != {f"WF-{i:03}" for i in range(1, 102)}):
        raise PlanError("incomplete_workflow_catalog")
    for row in design_workflows.values():
        _known(row["skill_ids"], design_skills, "unknown_workflow_skill")
    requirement_rows = _index(requirements["requirements"], "requirement_id")
    if set(requirement_rows) != {f"F{i:03}" for i in range(1, 271)}:
        raise PlanError("incomplete_requirement_catalog")
    if any(r["title_missing"] != (r["title"] is None) for r in requirement_rows.values()):
        raise PlanError("invalid_requirement_title_missing")
    skills = _index(data["skills"], "skill_id")
    rows = _index(data["functions"], "function_id")
    schema_ids = [p["schema_id"] for p in data["ports"].values()]
    if len(set(schema_ids)) != len(schema_ids):
        raise PlanError("duplicate_port_schema_id")
    ports = {name: Port(name, p["scope"], p["schema"], p["provenance"], p.get("untrusted_text", False))
             for name, p in data["ports"].items()}
    try:
        for port in ports.values():
            Draft202012Validator.check_schema(port.schema)
        for row in rows.values():
            Draft202012Validator.check_schema(row["arguments_schema"])
    except SchemaError as exc:
        raise PlanError("invalid_contract_schema") from exc

    def typed_ports(mapping):
        _known(mapping, ports, "unknown_contract_port")
        if any(data["ports"][p]["schema_id"] != ref for p, ref in mapping.items()):
            raise PlanError("unknown_port_schema_ref")
        return {p: ports[p] for p in mapping}

    functions = {}
    for fid, row in rows.items():
        _known(row["skill_ids"], skills, "unknown_skill_membership")
        _known(row["requirement_refs"], requirement_rows, "unknown_requirement_ref")
        _known(row["order_after"], rows, "unknown_order_function")
        _known(row["effects"], ports, "unknown_effect_port")
        inputs, outputs = typed_ports(row["inputs"]), typed_ports(row["outputs"])
        if any(port.scope != row["evidence_scope"] for port in outputs.values()):
            raise PlanError("output_evidence_scope_mismatch")
        for predicate in row["preconditions"]:
            _known([predicate["port"]], inputs, "unknown_predicate_input")
            if predicate["op"] in NUMERIC_OPS and (type(predicate["value"]) not in (int, float)):
                raise PlanError("invalid_numeric_predicate")
        for argument, (port, _) in row["argument_sources"].items():
            _known([port], inputs, "unknown_argument_input")
            _known([argument], row["arguments_schema"].get("properties", {}), "unknown_argument_name")
        functions[fid] = FunctionV01(
            id=fid, version=row["version"], skills=tuple(row["skill_ids"]), inputs=inputs, outputs=outputs,
            description=row["description"], scope=row["evidence_scope"], cost=row["cost"],
            latency_ms=row["latency_ms"], risk=row["risk"], permission=row["permission"],
            verifier=row["verifier"], predicates=tuple(Predicate(**p) for p in row["preconditions"]),
            timeout_ms=row["timeout_ms"], retry_limit=row["retry"]["max_attempts"] - 1,
            order_after=tuple(row["order_after"]), arguments_schema=row["arguments_schema"],
            argument_sources={k: tuple(v) for k, v in row["argument_sources"].items()},
            **{key: row[key] for key in ("status", "adapter", "requirement_refs", "effects", "capability_probe",
                                         "evidence_scope", "ttl_seconds", "on_unknown")})
    registry = registry_class.__new__(registry_class)
    registry.contract_format, registry.registry_version = "v0.1", data["version"]
    registry.ports, registry.functions = ports, functions
    workflows = _index(data["workflows"], "workflow_id")
    _known(design_workflows, workflows, "missing_catalog_workflow")
    for wid, row in workflows.items():
        if "covered_by" in row:
            if (row["status"] != "CATALOG_ONLY" or row["covered_by"] not in workflows
                    or workflows[row["covered_by"]]["status"] != "SUPPORTED"):
                raise PlanError("invalid_workflow_covered_by:" + wid)
        _known(row["goal_ports"], ports, "unknown_goal_port")
        _known(row["claims"], WORKFLOW_CLAIMS, "unknown_workflow_claim")
        _known(row["skill_ids"], design_skills if row["status"] == "CATALOG_ONLY" else skills,
               "unknown_workflow_skill")
        if "html_workflow_id" in row:
            _known([row["html_workflow_id"]], design_workflows, "unknown_html_workflow")
        if row["status"] == "SUPPORTED":
            if not row["goal_ports"]:
                raise PlanError("supported_workflow_without_goals:" + wid)
            if not row["claims"]:
                raise PlanError("supported_workflow_without_claims:" + wid)
        if row["status"] == "CATALOG_ONLY" or row["kind"] == "CHANGE":
            if row["goal_ports"] or row["minimal_goals"]:
                raise PlanError("nonplannable_workflow_goals:" + wid)
        _known(row["minimal_goals"], row["goal_ports"], "minimal_goal_outside_workflow")
        for goal in row["goal_ports"]:
            # Feasibility only: a real case must still pass all capability,
            # permission, target and evidence gates before execution.
            if not any(registry.contract_allowed(f) and goal in f.outputs and
                       ports[goal].accepts(f.outputs[goal]) for f in functions.values()):
                raise PlanError("goal_without_eligible_producer:" + goal)
    for wid, goals in data["workflow_evidence"].items():
        _known([wid], workflows, "unknown_workflow_evidence")
        if goals != workflows[wid]["goal_ports"]:
            raise PlanError("workflow_evidence_goal_mismatch:" + wid)
    registry.workflows = copy.deepcopy(workflows)
    registry.fact_assertions = fact_assertions(data.get("facts", ()), ports)
    from .claims import ClaimBook
    registry.claim_book = ClaimBook.from_data(data, ports)
    registry.workflow_catalog = copy.deepcopy(catalog)
    for skill in skills.values():
        for key in ("requires", "produces", "completion_ports", "read_set", "write_set"):
            _known(skill[key], ports, "unknown_skill_port")
        _known(skill["required_capabilities"], rows, "unknown_skill_capability")
    for goals in data["workflow_evidence"].values():
        _known(goals, ports, "unknown_goal_port")
    for pair in data["conflicts"]:
        _known(pair, rows, "unknown_function_conflict")

    def relations(key):
        result = []
        for row in data[key]:
            _known([row["source"], row["target"]], skills, "unknown_relation_skill")
            result.append(RelationV01(row["source"], row["target"], row["type"], row["weight"],
                                      row["origin"], row["reason"]))
        return result

    registry.relations, registry.extension_relations = relations("relations"), relations("extension_relations")
    registry.skills = copy.deepcopy(skills)
    for sid, skill in registry.skills.items():
        # Compatibility keys consumed by the current graph/compiler, derived
        # solely from the declared relations, never from naming heuristics.
        skill["id"] = sid
        skill["depends_on"] = [e.target for e in registry.relations if e.source == sid and e.kind == "depends_on"]
    registry.goal_ports = {wid: list(row["goal_ports"]) for wid, row in workflows.items()}
    registry.function_conflicts = {frozenset(pair) for pair in data["conflicts"]}
    registry.legacy = _replay_view(registry)
    registry.rebuild()
    return registry


def _replay_view(registry):
    """Translate typed data into the existing adapter's coarse READ interface."""
    types = {"string": "str", "boolean": "bool", "number": "number", "array": "list"}
    try:
        port_fields = {name: {key: types[value["type"]] for key, value in port.schema["properties"].items()}
                       for name, port in registry.ports.items()}
    except (KeyError, TypeError) as exc:
        raise PlanError("unsupported_replay_port_schema") from exc
    data = {
        "version": registry.registry_version, "skills": list(registry.skills.values()),
        "functions": [{"id": f.id, "version": f.version, "skills": list(f.skills),
                       "requires": list(f.inputs), "produces": list(f.outputs), "scope": f.scope,
                       "description": f.description, "risk": "WRITE" if f.risk == "WRITE" else "READ",
                       "adapter": f.adapter, "ttl_s": f.ttl_seconds} for f in registry.functions.values()],
        "port_fields": port_fields, "workflow_evidence": registry.goal_ports,
        "conflicts": [sorted(pair) for pair in registry.function_conflicts],
        "relations": [{"from": e.source, "to": e.target, "type": e.kind, "weight": e.weight}
                      for e in registry.relations if e.kind != "depends_on"],
    }
    return Registry(data=data)
