"""GATEWAY_DESIGN: bounded Function Resolver and Contract 0 (HTML 08/04).

Joint retrieval / typed deficit expansion takes ideas from Tool-to-Agent
Retrieval, HyperAgent and TGR; no code from those papers is used. Retrieval
uses the existing GoS lexical-seed adapter. This module never executes tools
or emits commands. Costs and latency are declared catalog estimates.
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass

from .contracts import Truth
from .graphs import fold


@dataclass(frozen=True)
class ResolverBudget:
    max_depth: int = 6
    max_nodes: int = 32
    max_latency_ms: float = 1000

    def __post_init__(self):
        if (type(self.max_depth) is not int or type(self.max_nodes) is not int
                or min(self.max_depth, self.max_nodes) < 0
                or type(self.max_latency_ms) not in (int, float)
                or not math.isfinite(self.max_latency_ms) or self.max_latency_ms < 0):
            raise ValueError("invalid_resolver_budget")


def resolve(registry, state, request, *, selected_skills=(), goals=(), actor=None,
            budget=None, method="gos", intent=None):
    """Select safe functions and prerequisites, returning only Contract 0.

    Missing inputs include resolved deficits as well as unresolved ones: they
    explain every cross-skill insertion. Failed branches are transactional;
    their orphan producers never enter the returned shortlist. UNKNOWN guards
    request evidence, FALSE guards reject. A link-down fact does not imply a
    false default-route predicate; the route must itself be observed.

    actor may restrict the case ACL via its permissions field; it can never
    grant permissions absent from CaseState. Budgets bound examined expansion
    nodes, depth and summed declared latency (not host execution time).
    """
    budget = budget or ResolverBudget()
    goals = tuple(dict.fromkeys(goals))
    retrieval = registry.retrieve(request, goals, state, method=method)
    scores = retrieval["scores"]
    rerank = retrieval["rerank_scores"]
    selected = list(dict.fromkeys(selected_skills))
    if not selected:
        # Retrieval establishes initial affinity. Typed goal fallback applies
        # only without lexical seeds; do not force every workflow goal into
        # the shortlist independently of retrieval (the original G1 gap).
        members = {n[2:] for n in retrieval["seeds"] if n.startswith("s:")}
        members.update(s for fid in retrieval["functions"] for s in registry.functions[fid].skills)
        if not retrieval["seeds"]:
            members.update(s for g in goals for fid in registry.hf.outputs.get(g, ())
                           for s in registry.functions[fid].skills)
        # A skill that another selected skill depends on (per G_S) is a
        # prerequisite, not a selection: its functions enter only as producers.
        prerequisites = {dep for sid in members for dep in registry.gs.dependencies(sid)}
        selected = sorted(members - prerequisites) or sorted(members)

    def context(fid):
        members = registry.gsf.by_function[fid]
        return next((sid for sid in selected if sid in members), None) or min(
            members, key=lambda sid: (-scores.get("s:" + sid, 0), sid))

    missing, rejected = [], []
    used = {"depth": 0, "nodes": 0, "latency_ms": 0.0}
    eligible = registry.eligible(state)
    actor_permissions = (actor.get("permissions") if isinstance(actor, dict)
                         else getattr(actor, "permissions", None))

    def reject(fid, reason):
        row = {"function_id": fid, "reason": reason}
        if row not in rejected:
            rejected.append(row)

    def deficit(fid, name):
        row = {"function_id": fid, "input": name}
        if row not in missing:
            missing.append(row)

    def gate(fid):
        f = registry.functions[fid]
        if f.risk == "WRITE":
            reason = "policy:WRITE"
        elif not registry.contract_allowed(f):
            reason = "policy:status_or_risk"
        elif fid not in eligible or not state.allowed(f):
            reason = "policy:capability_or_acl"
        elif actor_permissions is not None and f.permission not in actor_permissions:
            reason = "policy:actor_acl"
        elif f.scope == "client" and state.fact("client.identity") is None and not (
                state.target.get("selector") or state.target.get("client_id")):
            reason = "target:client.identity"
        else:
            return True
        reject(fid, reason)
        return False

    missing_goals = {g for g in goals if state.fact(g) is None}
    candidates = set(retrieval["functions"])
    candidates.update(fid for sid in selected for fid in registry.gsf.by_skill.get(sid, ()))
    # With no lexical seeds, typed goal deficits are still retrievable through
    # H_F. Global hits outside affinity are considered only as deficit producers.
    if not retrieval["seeds"]:
        candidates.update(fid for g in missing_goals if g in registry.ports
                          for fid in registry.hf.producers(registry.ports[g]))
    if intent == "CHANGE":
        # retrieve() correctly hides WRITE before ranking. Keep a rejected
        # catalog match for the Contract 0 audit, without authorizing a read
        # workflow as a substitute for the requested configuration change.
        tokens = set(re.findall(r"[a-z0-9]+", fold(request).lower()))
        candidates = {fid for fid, f in registry.functions.items() if f.risk == "WRITE"
                      and tokens.intersection(fid.split("."))}
    elif goals:
        candidates = {fid for fid in candidates if missing_goals.intersection(registry.functions[fid].outputs)}

    def priority(fid):
        return (-len(missing_goals.intersection(registry.functions[fid].outputs)),
                -rerank.get("f:" + fid, 0), registry.objective(fid), fid)

    roots = sorted(candidates, key=priority)
    policy_removed, target_missing = set(), set()
    safe_roots = []
    for fid in roots:
        if not gate(fid):
            if rejected[-1]["reason"].startswith("policy:"):
                policy_removed.add(fid)
            else:
                target_missing.add(fid)
                deficit(fid, "client.identity")
        elif not state.completed(registry.functions[fid]):
            safe_roots.append(fid)

    def conflict(fid, chosen):
        return any(frozenset((fid, other)) in registry.function_conflicts or
                   registry.gs.conflicts({context(fid)}, {context(other)}) for other in chosen if other != fid)

    def expand(fid, chosen, depth, stack, reason=None, *, exact_producer=False):
        if fid in stack:
            reject(fid, "dependency_cycle")
            return None
        if fid in chosen or state.completed(registry.functions[fid], exact_producer=exact_producer):
            return chosen
        if not gate(fid):
            return None
        if conflict(fid, chosen):
            reject(fid, "conflict")
            return None
        f = registry.functions[fid]
        for p in f.predicates:
            if p.evaluate(state) == Truth.FALSE:
                reject(fid, "false_precondition:" + p.port + ("." + p.field if p.field else ""))
                return None
        for exhausted in ("max_depth" if depth > budget.max_depth else None,
                          "max_nodes" if used["nodes"] >= budget.max_nodes else None,
                          "max_latency_ms" if used["latency_ms"] + f.latency_ms > budget.max_latency_ms else None):
            if exhausted:
                reject(fid, "budget_exhausted:" + exhausted)
                return None
        used["nodes"] += 1
        used["depth"] = max(used["depth"], depth)
        used["latency_ms"] += f.latency_ms
        chosen = {**chosen, fid: reason}
        required = dict(f.inputs)
        for sid in registry.gs.dependencies(context(fid)):
            for name in registry.skills[sid].get("completion_ports", ()):
                required.setdefault(name, registry.ports[name])
        for p in f.predicates:
            if p.evaluate(state) == Truth.UNKNOWN:
                required.setdefault(p.port, registry.ports[p.port])
        for name, port in required.items():
            if state.fact(name, port) is not None:
                # A known port with an UNKNOWN field cannot be repaired by
                # pretending that existence proves the predicate.
                if any(p.port == name and p.evaluate(state) == Truth.UNKNOWN for p in f.predicates):
                    deficit(fid, name)
                    reject(fid, "unknown_precondition:" + name)
                    return None
                continue
            deficit(fid, name)
            if any(name in registry.functions[other].outputs and port.accepts(registry.functions[other].outputs[name])
                   for other in chosen if other != fid and other not in stack):
                continue
            expanded = None
            for producer in sorted(registry.hf.producers(port), key=priority):
                expanded = expand(producer, chosen, depth + 1, stack + (fid,), "producer_for:" + name)
                if expanded is not None:
                    break
            if expanded is None:
                reject(fid, "missing_input:" + name)
                return None
            chosen = expanded
        for prior in f.order_after:
            if state.completed(registry.functions[prior], exact_producer=True):
                continue
            # ORDER prerequisites are explicit contract dependencies, not a
            # license to add unrelated cross-skill hits.
            name = next(iter(registry.functions[prior].outputs))
            deficit(fid, name)
            expanded = expand(prior, chosen, depth + 1, stack + (fid,), "producer_for:" + name,
                              exact_producer=True)
            if expanded is None:
                reject(fid, "missing_order:" + prior)
                return None
            chosen = expanded
        return chosen

    chosen = {}
    for fid in safe_roots:
        if all(state.fact(name, port) is not None or any(
                name in registry.functions[other].outputs and port.accepts(registry.functions[other].outputs[name])
                for other in chosen) for name, port in registry.functions[fid].outputs.items()):
            continue
        if not set(registry.functions[fid].skills).intersection(selected):
            # Keep global hits available to H_F; a cross-skill function enters
            # only through an actual consumer's missing input. Do not invent a
            # self-input just to relabel an unrelated global hit as a producer.
            continue
        expanded = expand(fid, chosen, 0, ())
        if expanded is not None:
            chosen = expanded

    # UNKNOWN is a request for evidence, never a negative observation. Return
    # the prerequisite batch first and defer guarded consumers until the next
    # resolution sees a TRUE predicate. In particular link_up=false does not
    # prove default_route=false: propose wan.routes, not a speculative probe.
    planned_outputs = {name for fid in chosen for name in registry.functions[fid].outputs}
    deferred = set()
    for fid in chosen:
        for p in registry.functions[fid].predicates:
            if p.evaluate(state) == Truth.UNKNOWN:
                deferred.add(fid)
                reject(fid, "deferred_unknown_precondition:" + p.port + ("." + p.field if p.field else ""))
    while True:
        removed = set()
        for fid in set(chosen) - deferred:
            f = registry.functions[fid]
            if any(state.fact(name, port) is None and not any(
                    other not in deferred and other != fid and name in registry.functions[other].outputs
                    and port.accepts(registry.functions[other].outputs[name]) for other in chosen)
                   for name, port in f.inputs.items()) or any(prior in deferred for prior in f.order_after):
                removed.add(fid)
                reject(fid, "deferred_prerequisite")
        if not removed:
            break
        deferred.update(removed)
    functions = sorted(set(chosen) - deferred, key=priority)
    cross = [{"function_id": fid, "from_skill": context(fid), "reason": chosen[fid]}
             for fid in functions if not set(registry.functions[fid].skills).intersection(selected)]
    unfulfilled = missing_goals - planned_outputs
    identity_needed = any(row["input"] == "client.identity" for row in missing)
    identity_possible = (state.fact("client.identity") is not None or
                         (bool(state.target.get("selector") or state.target.get("client_id"))
                          and any(fid in eligible and registry.functions[fid].permission in
                                  (actor_permissions if actor_permissions is not None else state.permissions)
                                  for fid in registry.hf.producers(registry.ports["client.identity"]))))
    if intent == "CHANGE" or (roots and policy_removed == set(roots)):
        decision = "BLOCKED"
    elif (target_missing or identity_needed) and not identity_possible:
        decision = "ASK_USER"
    elif unfulfilled or (not functions and any(not state.completed(registry.functions[fid]) for fid in safe_roots)):
        decision = "INCOMPLETE"
    elif any(reason is not None for reason in chosen.values()):
        decision = "EXPAND_PREREQUISITES"
    elif functions or (goals and not missing_goals):
        decision = "READY_TO_COMPILE"
    else:
        decision = "INCOMPLETE"
    snapshot = {name: {"status": "KNOWN" if state.fact(name) is not None else "UNKNOWN", "predicates": []}
                for name in registry.ports}
    for fid in roots + functions:
        for p in registry.functions[fid].predicates:
            row = {"field": p.field, "op": p.op, "value": p.value, "truth": p.evaluate(state).value}
            if row not in snapshot[p.port]["predicates"]:
                snapshot[p.port]["predicates"].append(row)
    return {"query": retrieval["query"], "selected_skills": selected, "case_state": snapshot,
            "function_candidates": functions, "missing_inputs": missing, "cross_skill_candidates": cross,
            "decision": decision, "policy": {"acl": ",".join(sorted(state.permissions.intersection(
                actor_permissions if actor_permissions is not None else state.permissions))), "write_approval": False},
            "catalog_version": getattr(registry, "registry_version", registry.legacy.data.get("version", "unknown")),
            "skill_graph_version": registry.gs.version, "plan_revision": 1 + len(cross),
            "skill_context": {fid: context(fid) for fid in functions}, "rejected": rejected,
            "budget": {"used": used, "limits": asdict(budget)}}
