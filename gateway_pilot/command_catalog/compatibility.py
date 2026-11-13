"""Explicit v0.2 READ view for the existing typed Core; never auto-bind tools."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..core import PlanError, Registry
from ..graph_v3.contracts import Function, Port, Predicate, validate
from ..graph_v3.graphs import GraphRegistry
from .builder import read_registry, verify_registry
from .loader import digest, require


@dataclass
class FunctionV02(Function):
    ttl_seconds: float = 30
    lifecycle: str = "PROPOSED"
    capability_probe: str = ""
    on_unknown: str = "BLOCK_AND_REQUEST_EVIDENCE"
    effects: list[str] = field(default_factory=list)
    metadata_digest: str = ""
    registry_digest: str = ""
    port_versions: dict = field(default_factory=dict)


class CompatibilityView(Registry):
    """Metadata for existing readers. It deliberately cannot run legacy execute()."""
    contract_format = "v0.2"

    def __init__(self, registry):
        self.registry = registry
        data = dict(version="0.2.0", skills=list(registry.skills.values()),
                    functions=[dict(id=f.id, version=f.version, skills=list(f.skills),
                                    requires=list(f.inputs), produces=list(f.outputs), scope=f.scope,
                                    description=f.description, risk=f.risk, ttl_s=f.ttl_seconds)
                               for f in registry.functions.values()],
                    workflow_evidence={}, port_fields={}, conflicts=[], relations=[])
        super().__init__(data=data)

    def bind_and_gate(self, fid, arguments, state):
        function = self.registry.functions.get(fid)
        require(function is not None and state.allowed(function), "runtime_permission_or_capability")
        require(type(arguments) is dict and validate(arguments, function.arguments_schema), "argument_schema")
        require(all(state.fact(pid, port) is not None for pid, port in function.inputs.items()), "missing_input")
        if "client_id" in arguments:
            require(arguments["client_id"] == state.target.get("client_id"), "argument_target")
        require(state.attempts[fid] < function.retry_limit + 1, "duplicate_tool_budget")
        return copy.deepcopy(arguments)


def compile_registry(artifact: dict, policy: dict, *, approved_digest: str) -> GraphRegistry:
    """Trusted startup only. A matching hash is an operator pin, not a signature."""
    artifact = copy.deepcopy(artifact)
    verify_registry(artifact, policy)
    require(artifact["content_digest"] == approved_digest, "unapproved_runtime_registry")
    require(all(f["risk"] == "READ_ONLY" and f["lifecycle"] in {"IMPLEMENTED", "VERIFIED"}
                for f in artifact["functions"]), "runtime_read_lifecycle_required")
    registry = GraphRegistry.__new__(GraphRegistry)
    registry.contract_format, registry.registry_version = "v0.2", "0.2.0"
    registry.catalog_digest = approved_digest
    registry.ports = {p["port_id"]: Port(p["port_id"], p["scope"], copy.deepcopy(p["schema"]),
                                        p["provenance"], p["untrusted_text"]) for p in artifact["ports"]}
    registry.functions = {}
    for f in artifact["functions"]:
        registry.functions[f["function_id"]] = FunctionV02(
            id=f["function_id"], version=f["version"], skills=tuple(s["skill_id"] for s in f["skill_refs"]),
            inputs={pid: registry.ports[pid] for pid in f["inputs"]},
            outputs={pid: registry.ports[pid] for pid in f["outputs"]},
            description=f["description"], scope=f["scope"], cost=f["cost"], latency_ms=f["latency_ms"],
            risk=f["risk"], permission=f["permission"], verifier=f["verifier"],
            predicates=tuple(Predicate(**p) for p in f["preconditions"]), order_after=tuple(f["order_after"]),
            timeout_ms=f["timeout_ms"], retry_limit=f["retry"]["max_attempts"]-1,
            argument_sources={k: tuple(v) for k, v in f["argument_sources"].items()},
            arguments_schema=copy.deepcopy(f["arguments_schema"]), ttl_seconds=f["ttl_seconds"],
            lifecycle=f["lifecycle"], capability_probe=f["capability_probe"], on_unknown=f["on_unknown"],
            effects=copy.deepcopy(f["effects"]), metadata_digest=digest(f), registry_digest=approved_digest,
            port_versions={"inputs": copy.deepcopy(f["inputs"]), "outputs": copy.deepcopy(f["outputs"])})
    registry.skills = {s["skill_id"]: dict(id=s["skill_id"], version=s["version"], name=s["name"],
        description=s["description"], requires=list(s["requires"]), produces=list(s["produces"]),
        completion_ports=list(s["completion_ports"]), depends_on=[]) for s in artifact["skills"]}
    registry.relations, registry.function_conflicts = [], set()
    registry.goal_ports, registry.workflows, registry.fact_assertions = {}, {}, ()
    registry.legacy = CompatibilityView(registry)
    registry.rebuild()
    registry._contract_pins = {fid: f.digest() for fid, f in registry.functions.items()}
    return registry


def load_runtime_registry(path, *, contract_format: str, policy=None, approved_digest=None):
    """Explicit format dispatch; no guessing or fallback after a failed parse."""
    if contract_format == "v0.1":
        from ..graph_v3.registry_v01 import load_registry
        return load_registry(path)
    if contract_format == "v0.2":
        require(type(policy) is dict and type(approved_digest) is str, "trusted_runtime_configuration")
        return compile_registry(read_registry(path, policy), policy, approved_digest=approved_digest)
    raise PlanError("unsupported_contract_format")
