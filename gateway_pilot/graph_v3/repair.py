"""GATEWAY_DESIGN: typed verifier events and bounded local repair on G_run.

The operator registry, the per-failure ordering table and the L_max/E_max/R_max
bounds follow the unofficial GraSP reproduction
(third_party/grasp-reproduction/grasp-spec.md, sections 3.4-3.5). This module
is not a reproduction of GraSP. Gateway limits are stricter than that sketch:
every substitute or inserted producer passes the same hard gate as the compiler,
DATA/STATE/hard ORDER edges are never removed, the patch only touches nodes
within ``HOPS`` of the failed node, and no model selects or edits an operator.
"""
from __future__ import annotations

import copy
from dataclasses import asdict

from ..core import PlanError
from .contracts import Truth
from .planner import Binding, Compiler, Edge, NodeState

DEFAULT_ORDER = {
    "precondition": ("INSERT_PREREQ", "REBIND", "SUBSTITUTE", "REWIRE", "BYPASS"),
    "postcondition": ("SUBSTITUTE", "REBIND", "REWIRE", "BYPASS", "INSERT_PREREQ"),
    "execution": ("SUBSTITUTE", "REBIND", "REWIRE", "BYPASS"),
    "timeout": ("SUBSTITUTE", "BYPASS"),
}
L_MAX, E_MAX, R_MAX, HOPS, P_MAX = 3, 5, 2, 2, 1
FAILED_STATES = (NodeState.FAILED, NodeState.INCONCLUSIVE, NodeState.SKIPPED)


def classify(status):
    """Map a verifier/adapter status to one of the four repair event types."""
    if status == "TIMEOUT":
        return "timeout"
    if status in ("VERIFICATION_FAILED", "PARSE_ERROR", "STALE"):
        return "postcondition"
    return "execution"


class RepairContext:
    def __init__(self, runner, plan, node_id, event):
        self.runner, self.plan, self.node_id, self.event = runner, plan, node_id, event
        self.registry = runner.registry

    @property
    def node(self):
        return self.plan.nodes[self.node_id]

    @property
    def function(self):
        return self.registry.functions[self.node.function_id]

    @property
    def view(self):
        return self.runner.node_state(self.node)

    @property
    def excluded(self):
        return set(self.runner.excluded) | {self.node.function_id}

    def compiler(self, extra_nodes, *, exclude_failed=False):
        budget = max(0, self.runner.cost_budget - self.runner.spent)
        compiler = Compiler(self.registry, max_nodes=len(self.plan.nodes) + extra_nodes,
                            max_cost=self.plan.cost + budget,
                            excluded=self.excluded if exclude_failed else self.runner.excluded,
                            max_repairs=R_MAX)
        compiler.state, compiler.skill_context = self.view, {}
        compiler.searched, compiler.rejections = 0, []
        return compiler


def consumers(plan, node_id):
    return [(nid, name) for nid, n in plan.nodes.items() for name, b in n.bindings.items()
            if b.kind == "node" and b.ref == node_id]


def goal_needed(plan, node):
    return (any(b.kind == "node" and b.ref == node.id for b in plan.goal_bindings)
            or node.function_id in plan.requested)


def _required(registry, plan, consumer_id, name):
    f = registry.functions[plan.nodes[consumer_id].function_id]
    return f.inputs.get(name, registry.ports[name])


def _best(plans):
    return min(plans, key=lambda p: (p.cost, len(p.nodes), tuple(sorted(p.nodes))))


def bypass(ctx):
    """Skip a node when every consumer's port already has a usable fact."""
    plan, node = ctx.plan, ctx.node
    if goal_needed(plan, node):
        return None
    rebound = []
    for cid, name in consumers(plan, node.id):
        fact = ctx.runner.node_state(plan.nodes[cid]).fact(name, _required(ctx.registry, plan, cid, name))
        if fact is None:
            return None
        rebound.append((cid, name, fact["id"]))
    for cid, name, eid in rebound:
        plan.nodes[cid].bindings[name] = Binding("evidence", eid, name)
    node.transition(NodeState.SKIPPED, "repair_bypass_downstream_facts_present")
    return dict(operator="BYPASS", skipped=[node.id], touched=[cid for cid, _, _ in rebound])


def rebind(ctx):
    """Re-attach stale evidence bindings (or an unresolved client) to fresh facts."""
    node, f, view, registry = ctx.node, ctx.function, ctx.view, ctx.registry
    if not view.allowed(f):
        return None
    changes = {}
    for name, b in node.bindings.items():
        if b.kind != "evidence":
            continue
        port = f.inputs.get(name, registry.ports[name])
        if view.by_id(b.ref, port) is not None:
            continue
        fact = view.fact(name, port)
        if fact is not None and fact["id"] != b.ref:
            changes[name] = Binding("evidence", fact["id"], name)
    target = None
    identity = registry.ports.get("client.identity")
    if f.scope == "client" and identity is not None and not node.target.get("client_id"):
        fact = view.fact("client.identity", identity)
        client_id = fact and fact["value"].get("client_id")
        # Validate against the Case target; never adopt a different client.
        if client_id and view.target.get("client_id", client_id) == client_id:
            target = {**node.target, "client_id": client_id}
    if not changes and target is None:
        return None
    node.bindings.update(changes)
    if target is not None:
        node.target = target
    return dict(operator="REBIND", rebound=sorted(changes) + (["target"] if target else []), touched=[node.id])


def insert_prereq(ctx):
    """Add at most L_MAX producers (E_MAX edges) for unverified preconditions."""
    plan, node, f, view, registry = ctx.plan, ctx.node, ctx.function, ctx.view, ctx.registry
    truths = [(p, p.evaluate(view)) for p in f.predicates]
    if any(t == Truth.FALSE for _, t in truths):
        return None  # A FALSE guard is a finding, not a missing prerequisite.
    missing = list(dict.fromkeys(p.port for p, t in truths if t != Truth.TRUE))
    for name, b in node.bindings.items():
        port = f.inputs.get(name, registry.ports[name])
        usable = (view.by_id(b.ref, port) is not None if b.kind == "evidence" else
                  b.ref in plan.nodes and plan.nodes[b.ref].state not in FAILED_STATES)
        if not usable and name not in missing:
            missing.append(name)
    if not missing:
        return None
    work = copy.deepcopy(plan)
    failed = {nid for nid, n in work.nodes.items() if n.state in FAILED_STATES}
    work.providers = {port: [nid for nid in ids if nid not in failed] for port, ids in work.providers.items()}
    compiler = ctx.compiler(L_MAX)
    try:
        for name in missing:
            options = compiler.need(registry.ports[name], work, ())
            if not options:
                return None
            work = _best(options)
        added = [nid for nid in work.nodes if nid not in plan.nodes]
        if not added or len(added) > L_MAX:
            return None
        consumer = work.nodes[node.id]
        for name in missing:
            binding = compiler.binding(registry.ports[name], work)
            consumer.bindings[name] = binding
            if binding.kind == "node":
                edge = Edge(binding.ref, node.id, "DATA" if name in f.inputs else "STATE", name)
                if edge not in work.edges:
                    work.edges.append(edge)
    except PlanError:
        return None
    if len([e for e in work.edges if e not in plan.edges]) > E_MAX:
        return None  # Abort the whole patch; nothing was written to the plan.
    for nid in added:
        work.nodes[nid].repair_budget = R_MAX
    plan.__dict__.update(work.__dict__)
    return dict(operator="INSERT_PREREQ", touched=[node.id])


def substitute(ctx):
    """Replace with a whitelisted Function: same ports, accepted schema, same scope, gated."""
    plan, node, f, view, registry = ctx.plan, ctx.node, ctx.function, ctx.view, ctx.registry
    users = consumers(plan, node.id)
    needs = {name: _required(registry, plan, cid, name) for cid, name in users}
    for b in plan.goal_bindings:
        if b.kind == "node" and b.ref == node.id:
            needs.setdefault(b.port, registry.ports[b.port])
    if node.function_id in plan.requested:
        for name in f.outputs:
            needs.setdefault(name, registry.ports[name])
    if not needs:
        return None
    for g in sorted(registry.functions.values(), key=lambda g: (registry.objective(g.id), g.id)):
        if (g.id in ctx.excluded or g.scope != f.scope
                or getattr(g, "evidence_scope", None) != getattr(f, "evidence_scope", None)
                or not (registry.contract_allowed(g) and view.allowed(g))
                or not all(name in g.outputs and port.accepts(g.outputs[name]) for name, port in needs.items())):
            continue
        work = copy.deepcopy(plan)
        del work.nodes[node.id]
        work.edges = [e for e in work.edges if e.target != node.id]
        work.providers = {port: [nid for nid in ids if nid != node.id] for port, ids in work.providers.items()}
        try:
            options = ctx.compiler(1, exclude_failed=True).function(g.id, work, ())
        except PlanError:
            continue
        options = [p for p in options if len(set(p.nodes) - set(work.nodes)) == 1]
        if not options:
            continue
        work = _best(options)
        new_id = next(iter(set(work.nodes) - set(plan.nodes) - {node.id}), None)
        if new_id is None:
            continue
        for cid, name in users:
            work.nodes[cid].bindings[name] = Binding("node", new_id, name)
        work.edges = [Edge(new_id, e.target, e.kind, e.port, e.hard) if e.source == node.id else e
                      for e in work.edges]
        work.goal_bindings = [Binding("node", new_id, b.port) if b.kind == "node" and b.ref == node.id else b
                              for b in work.goal_bindings]
        work.requested = tuple(g.id if fid == f.id else fid for fid in work.requested)
        work.nodes[new_id].repair_budget = node.repair_budget
        plan.__dict__.update(work.__dict__)
        return dict(operator="SUBSTITUTE", replaced={node.id: new_id}, touched=[cid for cid, _ in users])
    return None


def rewire(ctx):
    """Remove one soft ORDER edge into the node; never DATA, STATE or hard ORDER."""
    for index, edge in enumerate(ctx.plan.edges):
        if edge.target == ctx.node_id and edge.kind == "ORDER" and not edge.hard:
            del ctx.plan.edges[index]
            return dict(operator="REWIRE", touched=[edge.source])
    return None


OPERATORS = {"BYPASS": bypass, "REBIND": rebind, "INSERT_PREREQ": insert_prereq,
             "SUBSTITUTE": substitute, "REWIRE": rewire}


def _hops(edges, start):
    distance, frontier = {start: 0}, [start]
    while frontier:
        current = frontier.pop(0)
        for e in edges:
            for a, b in ((e.source, e.target), (e.target, e.source)):
                if a == current and b not in distance:
                    distance[b] = distance[current] + 1
                    frontier.append(b)
    return distance


def local_repair(runner, plan, node, event, *, order=None):
    """Try operators in the event's order; patch the same DAG as revision + 1.

    Returns the audit record of the applied patch, or ``{"escalate": ...}``
    with ``local-exhausted`` (no budget left) or ``local-failed``.
    """
    node_id = node.id
    if node.repair_budget <= 0:
        return {"escalate": "local-exhausted"}
    node.repair_budget -= 1
    ctx = RepairContext(runner, plan, node_id, event)
    for name in order or DEFAULT_ORDER.get(event["type"], DEFAULT_ORDER["precondition"]):
        snapshot = copy.deepcopy(plan.__dict__)
        distance = _hops(plan.edges, node_id)
        try:
            patch = OPERATORS[name](ctx)
            if patch is not None:
                if any(distance.get(t, HOPS + 1) > HOPS for t in patch.get("touched", ()) if t in snapshot["nodes"]):
                    raise PlanError("repair_outside_neighbourhood")
                plan.connect_terminals()
                plan.validate_structure()
        except PlanError:
            patch = None
        if patch is None:
            plan.__dict__.clear()
            plan.__dict__.update(snapshot)
            continue
        current = plan.nodes.get(node_id)
        if current is not None and current.state in (NodeState.FAILED, NodeState.INCONCLUSIVE):
            current.transition(NodeState.PENDING, "local_repair:" + name)
        before = set(snapshot["edges"])
        audit = dict(revision=plan.revision + 1, previous_revision=plan.revision, operator=name, node=node_id,
                     failure=event["type"], added_nodes=sorted(set(plan.nodes) - set(snapshot["nodes"])),
                     removed_nodes=sorted(set(snapshot["nodes"]) - set(plan.nodes)),
                     added_edges=[asdict(e) for e in plan.edges if e not in before],
                     removed_edges=[asdict(e) for e in snapshot["edges"] if e not in plan.edges],
                     invalidated_evidence=list(event.get("invalidated", ())))
        for key in ("skipped", "replaced", "rebound"):
            if key in patch:
                audit[key] = patch[key]
        plan.revision += 1
        plan.audit.append(audit)
        return audit
    return {"escalate": "local-failed"}
