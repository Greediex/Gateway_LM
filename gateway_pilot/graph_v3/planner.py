"""G_run compiler: bounded AND/OR search over admissible producer alternatives.

Enumerates feasible dependency choices within explicit search/node/cost bounds;
selects minimum summed contract cost+latency of the completed plans. This is not
a universal optimal network planner or a reproduction of GraSP repair learning.
"""
from __future__ import annotations
import copy
from dataclasses import dataclass, field, asdict
from enum import Enum
from ..core import PlanError
from .contracts import Truth


class NodeState(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    INCONCLUSIVE = "INCONCLUSIVE"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class Binding:
    kind: str  # evidence or node
    ref: str
    port: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    kind: str  # DATA / STATE / ORDER
    port: str = ""


@dataclass
class Invocation:
    id: str
    function_id: str
    skill_context: str
    target: dict
    bindings: dict[str, Binding]
    verifier: str
    contract_digest: str
    state: NodeState = NodeState.PENDING
    arguments: dict = field(default_factory=dict)
    output_evidence: dict = field(default_factory=dict)
    retries: int = 0
    reason: str = ""
    history: list = field(default_factory=list)
    order_evidence: list = field(default_factory=list)

    def transition(self, value, reason=""):
        allowed = {
            NodeState.PENDING: {NodeState.READY, NodeState.BLOCKED, NodeState.SKIPPED},
            NodeState.BLOCKED: {NodeState.READY, NodeState.SKIPPED},
            NodeState.READY: {NodeState.RUNNING, NodeState.BLOCKED},
            NodeState.RUNNING: {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.INCONCLUSIVE},
            NodeState.FAILED: {NodeState.PENDING}, NodeState.INCONCLUSIVE: {NodeState.PENDING},
        }
        if value not in allowed.get(self.state, set()):
            raise PlanError("illegal_node_transition:" + self.state + "->" + value)
        self.history.append({"from": self.state, "to": value, "reason": reason})
        self.state, self.reason = value, reason


@dataclass
class ExecutionDAG:
    goals: tuple
    requested: tuple = ()
    skill_graph_version: int = 1
    revision: int = 1
    nodes: dict[str, Invocation] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    providers: dict[str, list[str]] = field(default_factory=dict)
    cost: float = 0
    searched: int = 0
    audit: list = field(default_factory=list)

    def topological(self):
        if any(e.kind not in {"DATA", "STATE", "ORDER"} or e.source not in self.nodes or e.target not in self.nodes for e in self.edges):
            raise PlanError("invalid_execution_edge")
        pending, ordered = set(self.nodes), []
        while pending:
            ready = sorted(n for n in pending if all(e.source not in pending for e in self.edges if e.target == n))
            if not ready:
                raise PlanError("execution_cycle")
            for node in ready:
                pending.remove(node)
                ordered.append(node)
        return ordered

    def descendants(self, node_id):
        result, todo = set(), [node_id]
        while todo:
            current = todo.pop()
            for e in self.edges:
                if e.source == current and e.kind in ("DATA", "STATE") and e.target not in result:
                    result.add(e.target)
                    todo.append(e.target)
        return result

    def export(self):
        return asdict(self)


class Compiler:
    def __init__(self, registry, *, max_nodes=12, max_cost=100, max_search=2000, excluded=()):
        self.registry = registry
        self.max_nodes, self.max_cost, self.max_search = max_nodes, max_cost, max_search
        self.excluded, self.searched, self.rejections = set(excluded), 0, []

    def tick(self):
        self.searched += 1
        if self.searched > self.max_search:
            raise PlanError("planner_search_budget")

    def compile(self, goals, state, *, requested=(), revision=1):
        self.searched, self.rejections = 0, []
        self.state = state
        plans = [ExecutionDAG(tuple(goals), requested=tuple(requested), revision=revision,
                              skill_graph_version=self.registry.gs.version)]
        for name in goals:
            if name not in self.registry.ports:
                raise PlanError("unknown_goal_port:" + name)
            plans = [p for plan in plans for p in self.need(self.registry.ports[name], plan, ())]
        for fid in requested:
            plans = [p for plan in plans for p in self.function(fid, plan, ())]
        if not plans:
            raise PlanError("no_admissible_plan:" + ";".join(sorted(set(self.rejections))[:6]))
        result = min(plans, key=lambda p: (p.cost, len(p.nodes), tuple(sorted(p.nodes))))
        result.searched = self.searched
        result.topological()
        result.audit.append({"revision": revision, "operator": "COMPILE", "search_complete": True,
                             "search_states": self.searched, "cost": result.cost,
                             "objective": "sum contract cost + latency_ms/1000, admissible READ graph only"})
        return result

    def need(self, port, plan, stack):
        self.tick()
        if self.state.fact(port.name, port) is not None:
            return [plan]
        if port.name in plan.providers:
            if any(port.accepts(self.registry.functions[plan.nodes[node].function_id].outputs[port.name])
                   for node in plan.providers[port.name]):
                return [plan]
        producers = self.registry.hf.producers(port)
        if not producers:
            self.rejections.append("missing_typed_producer:" + port.name)
        return [p for fid in producers for p in self.function(fid, plan, stack)]

    def function(self, fid, plan, stack, *, exact_producer=False):
        self.tick()
        if fid in stack:
            self.rejections.append("dependency_cycle:" + fid)
            return []
        if fid not in self.registry.functions:
            self.rejections.append("unknown_function:" + fid)
            return []
        f = self.registry.functions[fid]
        if fid in self.excluded or not self.state.allowed(f):
            self.rejections.append("capability_permission_or_excluded:" + fid)
            return []
        if fid in plan.nodes or self.state.completed(f, exact_producer=exact_producer):
            return [plan]
        context = f.skills[0]
        for existing in plan.nodes.values():
            if (frozenset((existing.function_id, fid)) in self.registry.function_conflicts or
                    self.registry.gs.conflicts({context}, {existing.skill_context})):
                self.rejections.append("conflict:" + fid)
                return []
        required = dict(f.inputs)
        state_ports = set()
        for sid in self.registry.gs.dependencies(context):
            for name in self.registry.skills[sid].get("completion_ports", []):
                required.setdefault(name, self.registry.ports[name])
                state_ports.add(name)
        for predicate in f.predicates:
            if predicate.evaluate(self.state) == Truth.FALSE:
                self.rejections.append("false_precondition:" + fid)
                return []
            required.setdefault(predicate.port, self.registry.ports[predicate.port])
            state_ports.add(predicate.port)
        plans = [copy.deepcopy(plan)]
        for port in required.values():
            plans = [p for current in plans for p in self.need(port, current, stack + (fid,))]
        for predecessor in f.order_after:
            plans = [p for current in plans for p in
                     self.function(predecessor, current, stack + (fid,), exact_producer=True)]
        results = []
        for current in plans:
            if any(frozenset((n.function_id, fid)) in self.registry.function_conflicts or
                   self.registry.gs.conflicts({context}, {n.skill_context}) for n in current.nodes.values()):
                self.rejections.append("dependency_conflict:" + fid)
                continue
            cost = current.cost + self.registry.objective(fid)
            if len(current.nodes) >= self.max_nodes or cost > self.max_cost:
                self.rejections.append("planner_node_or_cost_budget")
                continue
            bindings, edges = {}, []
            for name, port in required.items():
                e = self.state.fact(name, port)
                if e:
                    bindings[name] = Binding("evidence", e["id"], name)
                else:
                    producer = next(node for node in reversed(current.providers[name])
                                    if port.accepts(self.registry.functions[current.nodes[node].function_id].outputs[name]))
                    bindings[name] = Binding("node", producer, name)
                    if name in f.inputs:
                        edges.append(Edge(producer, fid, "DATA", name))
                    if name in state_ports:
                        edges.append(Edge(producer, fid, "STATE", name))
            order_evidence = []
            order_complete = True
            for prior in f.order_after:
                if prior in current.nodes:
                    edges.append(Edge(prior, fid, "ORDER"))
                else:
                    facts = [self.state.fact(name, port)
                             for name, port in self.registry.functions[prior].outputs.items()]
                    if not all(fact is not None and fact["function_id"] == prior for fact in facts):
                        self.rejections.append("missing_order_evidence:" + prior)
                        order_complete = False
                        break
                    order_evidence.extend(fact["id"] for fact in facts)
            if not order_complete:
                continue
            target = ({"scope": "gateway", "id": self.state.gateway_id} if f.scope == "gateway"
                      else {**copy.deepcopy(self.state.target), "scope": "client"})
            node = Invocation(fid, fid, context, target, bindings,
                              f.verifier, f.digest(), order_evidence=order_evidence)
            # A Function ID is only unique within this single-target diagnostic case.
            # Node still carries target/args/contracts; multi-target expansion needs
            # separate invocation IDs and is outside this scoped runner.
            current.nodes[fid] = node
            current.edges.extend(e for e in edges if e not in current.edges)
            for name in f.outputs:
                current.providers.setdefault(name, []).append(fid)
            current.cost = cost
            results.append(current)
        return results
