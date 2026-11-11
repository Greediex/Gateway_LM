"""G_run compiler: bounded AND/OR search over admissible producer alternatives.

GATEWAY_DESIGN: bounded AND/OR search and declared cost objective.
PORTED_WITH_PARITY_TEST: backward goal closure and typed DATA/STATE edges,
checked against the apple fixture in the unofficial GraSP reproduction.
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
    hard: bool = True


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
    preconditions: list = field(default_factory=list)
    effects: list = field(default_factory=list)
    on_unknown: str = "BLOCK_AND_REQUEST_EVIDENCE"
    retry: dict = field(default_factory=dict)
    timeout_ms: float = 0
    risk: str = "READ"
    repair_budget: int = 0
    adapter: str = ""
    context_target: dict = field(default_factory=dict)
    failure: dict = field(default_factory=dict)

    def transition(self, value, reason=""):
        allowed = {
            NodeState.PENDING: {NodeState.READY, NodeState.BLOCKED, NodeState.SKIPPED},
            NodeState.BLOCKED: {NodeState.READY, NodeState.SKIPPED},
            NodeState.READY: {NodeState.RUNNING, NodeState.BLOCKED},
            NodeState.RUNNING: {NodeState.SUCCEEDED, NodeState.FAILED, NodeState.INCONCLUSIVE},
            # SKIPPED from a failed node is only reached through the BYPASS repair operator.
            NodeState.FAILED: {NodeState.PENDING, NodeState.SKIPPED},
            NodeState.INCONCLUSIVE: {NodeState.PENDING, NodeState.SKIPPED},
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
    case_id: str = "case"
    targets: tuple = ()
    goal_bindings: list = field(default_factory=list)
    initial_facts: list[Binding] = field(default_factory=list)
    structural_edges: list[Edge] = field(default_factory=list)
    numbered: bool = False

    def topological(self, *, structural=False):
        nodes = set(self.nodes) | ({"src", "snk"} if structural else set())
        edges = self.edges + self.structural_edges if structural else self.edges
        if any(e.kind not in {"DATA", "STATE", "ORDER"} or (not e.hard and e.kind != "ORDER")
               or e.source not in nodes or e.target not in nodes for e in edges):
            raise PlanError("invalid_execution_edge")
        pending, ordered = set(nodes), []
        while pending:
            ready = sorted(n for n in pending if all(e.source not in pending for e in edges if e.target == n))
            if not ready:
                raise PlanError("execution_cycle")
            for node in ready:
                pending.remove(node)
                ordered.append(node)
        return ordered

    def add_order_constraints(self, edges):
        self.edges.extend(edge for edge in edges if edge.hard or edge.kind != "ORDER")
        self.topological()
        for edge in edges:
            if edge.hard or edge.kind != "ORDER" or edge in self.edges:
                continue
            self.edges.append(edge)
            try:
                self.topological()
            except PlanError as exc:
                self.edges.pop()
                if str(exc) != "execution_cycle":
                    raise
                self.audit.append({"revision": self.revision, "operator": "DROP_SOFT_ORDER",
                                   "from": edge.source, "to": edge.target})

    def connect_terminals(self):
        self.structural_edges = [
            *(Edge("src", node, "ORDER") for node in self.nodes if not any(e.target == node for e in self.edges)),
            *(Edge(node, "snk", "ORDER") for node in self.nodes if not any(e.source == node for e in self.edges)),
        ] or [Edge("src", "snk", "ORDER")]

    def validate_structure(self):
        order = self.topological(structural=True)
        positions = {node: index for index, node in enumerate(order)}
        edges = self.edges + self.structural_edges
        if set(positions) != set(self.nodes) | {"src", "snk"} or any(
                positions[e.source] >= positions[e.target] for e in edges):
            raise PlanError("invalid_topological_order")
        reachable = {"src"}
        for node in order:
            if node in reachable:
                reachable.update(e.target for e in edges if e.source == node)
        if "snk" not in reachable:
            raise PlanError("source_sink_disconnected")
        expected_goals = list(self.goals) * max(1, len(self.targets))
        if sorted(b.port for b in self.goal_bindings) != sorted(expected_goals) or any(
                (b not in self.initial_facts if b.kind == "evidence" else
                 b.kind != "node" or b.ref not in self.nodes or b.port not in self.nodes[b.ref].effects)
                for b in self.goal_bindings):
            raise PlanError("uncovered_plan_goal")
        return order

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
        result = asdict(self)
        if self.numbered:
            result["contract_a"] = self.export_contract_a()
        return result

    def export_contract_a(self):
        self.validate_structure()
        nodes = [{"node_id": "src", "effects": [asdict(b) for b in self.initial_facts]}]
        nodes.extend({"node_id": n.id, "function_id": n.function_id, "skill_context": n.skill_context,
                      "adapter": n.adapter, "target": n.target,
                      "args": {key: asdict(binding) for key, binding in n.bindings.items()},
                      "requires": n.preconditions, "effects": n.effects, "on_unknown": n.on_unknown,
                      "verifier": n.verifier, "risk": n.risk, "retry": n.retry,
                      "timeout_ms": n.timeout_ms, "repair_budget": n.repair_budget}
                     for n in self.nodes.values())
        nodes.append({"node_id": "snk", "requires": list(self.goals)})
        return {"plan_id": f"{self.case_id}/plan/{self.revision}", "revision": self.revision,
                "case_id": self.case_id, "nodes": nodes,
                "edges": [{"from": e.source, "to": e.target, "type": e.kind}
                          for e in self.edges + self.structural_edges]}


class Compiler:
    def __init__(self, registry, *, max_nodes=12, max_cost=100, max_search=2000, excluded=(), max_repairs=2):
        self.registry = registry
        self.max_nodes, self.max_cost, self.max_search = max_nodes, max_cost, max_search
        self.excluded, self.searched, self.rejections = set(excluded), 0, []
        self.max_repairs = max_repairs
        self.numbered = getattr(registry, "contract_format", None) == "v0.1"

    def tick(self):
        self.searched += 1
        if self.searched > self.max_search:
            raise PlanError("planner_search_budget")

    def compile(self, goals, state, *, requested=(), revision=1, skill_context=None,
                targets=(), order_constraints=()):
        self.searched, self.rejections = 0, []
        self.skill_context = skill_context or {}
        goals, requested = tuple(goals), tuple(requested)
        targets = tuple(copy.deepcopy(t) for t in targets)
        for name in goals:
            if name not in self.registry.ports:
                raise PlanError("unknown_goal_port:" + name)
        if targets and (not self.numbered or any(not isinstance(t, dict) or t.get("scope") != "client" or
                                                not isinstance(t.get("client_id"), str) or not t["client_id"]
                                                for t in targets)):
            raise PlanError("invalid_plan_client_targets")
        if len({t["client_id"] for t in targets}) != len(targets):
            raise PlanError("duplicate_plan_client_target")
        plans = [ExecutionDAG(goals, requested=requested, revision=revision, targets=targets,
                              case_id=state.case_id, skill_graph_version=self.registry.gs.version,
                              numbered=self.numbered)]
        for view in ([state.for_target(target) for target in targets] if targets else [state]):
            self.state = view
            for name in goals:
                port = self.registry.ports[name]
                plans = [p for plan in plans for p in self.need(port, plan, ())]
                for plan in plans:
                    plan.goal_bindings.append(self.binding(port, plan))
            for fid in requested:
                plans = [p for plan in plans for p in self.function(fid, plan, ())]
        if not plans:
            raise PlanError("no_admissible_plan:" + ";".join(sorted(set(self.rejections))[:6]))
        result = min(plans, key=lambda p: (p.cost, len(p.nodes), tuple(sorted(p.nodes))))
        result.searched = self.searched
        result.add_order_constraints(list(order_constraints))
        result.connect_terminals()
        result.validate_structure()
        result.audit.append({"revision": revision, "operator": "COMPILE", "search_complete": True,
                             "search_states": self.searched, "cost": result.cost,
                             "objective": "sum contract cost + latency_ms/1000, admissible READ graph only"})
        return result

    def target(self, scope):
        if scope == "gateway":
            return {"scope": "gateway", "id": self.state.gateway_id}
        return {**copy.deepcopy(self.state.target), "scope": "client"}

    def provider(self, port, plan):
        target = self.target(port.scope)
        return next((node for node in reversed(plan.providers.get(port.name, ()))
                     if plan.nodes[node].target == target and
                     port.accepts(self.registry.functions[plan.nodes[node].function_id].outputs[port.name])), None)

    def binding(self, port, plan):
        fact = self.state.fact(port.name, port)
        if fact:
            proof = Binding("evidence", fact["id"], port.name)
            if proof not in plan.initial_facts:
                plan.initial_facts.append(proof)
            return proof
        producer = self.provider(port, plan)
        if producer is None:
            raise PlanError("uncovered_plan_goal:" + port.name)
        return Binding("node", producer, port.name)

    def invocation(self, fid, plan):
        target = self.target(self.registry.functions[fid].scope)
        return next((n.id for n in plan.nodes.values() if n.function_id == fid and n.target == target), None)

    def need(self, port, plan, stack):
        self.tick()
        if self.state.fact(port.name, port) is not None:
            return [plan]
        if self.provider(port, plan) is not None:
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
        if self.invocation(fid, plan) is not None or self.state.completed(f, exact_producer=exact_producer):
            return [plan]
        context = self.skill_context.get(fid, f.skills[0])
        if context not in f.skills:
            raise PlanError("invalid_skill_context:" + fid)
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
            node_id = (f"{fid}#{1 + sum(n.function_id == fid for n in current.nodes.values())}"
                       if self.numbered else fid)
            for name, port in required.items():
                binding = bindings[name] = self.binding(port, current)
                if binding.kind == "node":
                    if name in f.inputs:
                        edges.append(Edge(binding.ref, node_id, "DATA", name))
                    if name in state_ports:
                        edges.append(Edge(binding.ref, node_id, "STATE", name))
            order_evidence = []
            order_complete = True
            for prior in f.order_after:
                predecessor = self.invocation(prior, current)
                if predecessor is not None:
                    edges.append(Edge(predecessor, node_id, "ORDER"))
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
            node = Invocation(node_id, fid, context, self.target(f.scope), bindings,
                              f.verifier, f.digest(), order_evidence=order_evidence,
                              preconditions=[*required, *(f"{p.port}.{p.field} {p.op} {p.value!r}"
                                                          for p in f.predicates if p.op != "exists")],
                              effects=list(f.outputs),
                              on_unknown=getattr(f, "on_unknown", "BLOCK_AND_REQUEST_EVIDENCE"),
                              retry={"max_attempts": 1 + f.retry_limit}, timeout_ms=f.timeout_ms,
                              risk=f.risk, repair_budget=self.max_repairs, adapter=getattr(f, "adapter", "") or fid,
                              context_target=copy.deepcopy(self.state.target) if current.targets else {})
            current.nodes[node_id] = node
            current.edges.extend(e for e in edges if e not in current.edges)
            for name in f.outputs:
                current.providers.setdefault(name, []).append(node_id)
            current.cost = cost
            results.append(current)
        return results
