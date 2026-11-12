"""Read-only DAG scheduler, typed per-node verifier and bounded repair.

GATEWAY_DESIGN. Local repair operators live in repair.py; see its docstring for
the relation to the unofficial GraSP reproduction.
"""
import copy
from ..core import PlanError, bind_and_gate, execute
from .contracts import Truth, validate
from .execution import InvocationExecutor
from .planner import Compiler, NodeState
from .repair import P_MAX, local_repair
from .verification import EvidenceVerifier


class GraphRunner:
    def __init__(self, registry, case, state, *, max_calls=12, max_repairs=2, deadline_s=120,
                 cost_budget=100, executor=None, verifier=None, event_sink=None):
        self.registry, self.case, self.state = registry, case, state
        self.max_calls, self.max_repairs, self.deadline_s, self.cost_budget = max_calls, max_repairs, deadline_s, cost_budget
        self.started = state.clock()
        self.calls = self.repairs = 0
        self.spent = 0
        self.plans, self.events, self.excluded = [], [], set()
        self.plan_validator = None
        self.target_attempts = {}
        self.global_replans = 0
        self.contract_b = []
        self.incomplete = False
        # Trusted composition roots: user/model input never injects executors or verifiers.
        self.executor = executor if executor is not None else InvocationExecutor()
        self.verifier = verifier if verifier is not None else EvidenceVerifier()
        if event_sink is not None and not callable(event_sink):
            raise ValueError("runner_event_sink_must_be_callable")
        self.event_sink = event_sink

    def compiler(self):
        return Compiler(self.registry, max_cost=max(0, self.cost_budget - self.spent),
                        excluded=self.excluded, max_repairs=self.max_repairs)

    def attach(self, plan):
        plan.validate_structure()
        if self.plan_validator is not None:
            self.plan_validator(plan)
        self.plans.append(plan)
        if plan.targets:
            self.state._targeted_clients = True
        return plan

    def node_state(self, node):
        if not node.context_target:
            return self.state
        view = self.state.for_target(node.context_target)
        # Gateway calls count toward the gateway's shared duplicate budget,
        # even if a gateway node carries a client-scoped prerequisite.
        if node.target["scope"] == "gateway":
            view.attempts = self.state.attempts
        else:
            view.attempts = self.target_attempts.setdefault(view.target["client_id"], view.attempts)
        return view

    def ready(self, plan):
        if plan.skill_graph_version != self.registry.gs.version:
            raise PlanError('skill_graph_changed_after_compile')
        ready = []
        for node_id in plan.topological():
            n = plan.nodes[node_id]
            if n.state not in (NodeState.PENDING, NodeState.BLOCKED, NodeState.READY):
                continue
            predecessors = [plan.nodes[e.source] for e in plan.edges if e.target == node_id]
            if any(p.state not in (NodeState.SUCCEEDED, NodeState.SKIPPED) for p in predecessors):
                if n.state in (NodeState.PENDING, NodeState.READY):
                    n.transition(NodeState.BLOCKED, "predecessor_not_verified")
                continue
            f = self.registry.functions[n.function_id]
            state = self.node_state(n)
            if n.contract_digest != f.digest():
                raise PlanError("contract_changed_after_compile")
            if not state.allowed(f):
                if n.state != NodeState.BLOCKED:
                    n.transition(NodeState.BLOCKED, "capability_or_permission_changed")
                continue
            bindings_ok = True
            for name, b in n.bindings.items():
                required = f.inputs.get(name, self.registry.ports[name])
                expected_id = b.ref if b.kind == "evidence" else plan.nodes[b.ref].output_evidence.get(name)
                e = state.by_id(expected_id, required)
                if e is None or e["id"] != expected_id:
                    bindings_ok = False
                    break
            predicates = [p.evaluate(state) for p in f.predicates]
            if not bindings_ok or any(t != Truth.TRUE for t in predicates):
                if n.state != NodeState.BLOCKED:
                    n.transition(NodeState.BLOCKED, "input_or_guard_not_verified")
                continue
            if any(not any(e["id"] == eid and state.usable(e, self.registry.ports[e["port"]]) for e in state.evidence)
                   for eid in n.order_evidence):
                if n.state != NodeState.BLOCKED:
                    n.transition(NodeState.BLOCKED, "order_proof_expired")
                continue
            if n.state != NodeState.READY:
                n.transition(NodeState.READY, "inputs_and_guards_verified")
            ready.append(n)
        return ready

    def step(self, plan, preferred=None):
        if (self.calls >= self.max_calls or self.state.clock() - self.started >= self.deadline_s):
            raise PlanError("runner_call_or_deadline_budget")
        ready = self.ready(plan)
        if not ready:
            return None
        # Never silently execute another Function when a planner explicitly
        # selected a stale or ineligible node.
        if preferred is not None and not any(node.id == preferred for node in ready):
            raise PlanError("preferred_node_not_ready")
        n = next((node for node in ready if node.id == preferred), ready[0])
        f = self.registry.functions[n.function_id]
        state = self.node_state(n)
        if self.spent + self.registry.objective(f.id) > self.cost_budget:
            raise PlanError("runner_cost_budget")
        # Recheck actual arguments/target immediately before invocation.
        arguments = {}
        for argument, (port_name, path) in f.argument_sources.items():
            binding = n.bindings.get(port_name)
            if binding is None:
                raise PlanError('unbound_argument_source:' + argument)
            eid = binding.ref if binding.kind == 'evidence' else plan.nodes[binding.ref].output_evidence.get(port_name)
            evidence = state.by_id(eid, f.inputs.get(port_name, self.registry.ports[port_name]))
            if evidence is None:
                raise PlanError('argument_evidence_unavailable:' + argument)
            value = evidence['value']
            for key in path.split('.'):
                if not isinstance(value, dict) or key not in value:
                    raise PlanError('argument_path_unavailable:' + argument)
                value = value[key]
            arguments[argument] = value
        arguments = bind_and_gate(f.id, arguments, state, self.registry.legacy)
        if not validate(arguments, f.arguments_schema):
            raise PlanError("argument_schema")
        n.arguments = arguments
        if f.scope == "client" and arguments.get("client_id"):
            n.target["id"] = arguments["client_id"]
        n.transition(NodeState.RUNNING, "policy_and_bindings_passed")
        before = self.state.clock()
        self.calls += 1
        self.spent += self.registry.objective(f.id)
        try:
            observations, simulated_ms = self.executor.collect(self, f, arguments, state)
            elapsed_ms = 1000 * (self.state.clock() - before)
            self.verifier.verify(self, n, f, state, observations,
                                 simulated_ms=simulated_ms, elapsed_ms=elapsed_ms)
        except PlanError as exc:
            n.failure = {"type": "execution", "status": "ERROR", "message": str(exc)}
            n.transition(NodeState.FAILED, str(exc))
            self.contract_b.append({"node_id": n.id, "tool_status": "EXIT_ERROR", "observations": [],
                                    "goal_claim": "NOT_EVALUATED"})
        self.events.append({"revision": plan.revision, "node": n.id, "state": n.state, "reason": n.reason})
        if self.event_sink is not None:
            try:
                self.event_sink(self.events[-1])
            except (OSError, ValueError, RuntimeError, PlanError) as exc:
                # Optional signed journaling fails closed. This can follow a
                # verified READ; the next process must recheck fresh evidence.
                raise PlanError("runner_audit_sink_failed") from exc
        return n

    def ttl_seconds(self, f):
        """Compatibility facade; verification policy lives in EvidenceVerifier."""
        return self.verifier.ttl_seconds(self, f)

    def annotate(self, e, node, f, state):
        """Compatibility facade for evidence annotation."""
        return self.verifier.annotate(self, e, node, f, state)

    @staticmethod
    def export_contract_b(node, observations, adapter_status, simulated_ms, elapsed_ms, f):
        """Compatibility facade: Contract B is produced by EvidenceVerifier."""
        return EvidenceVerifier.export_contract_b(
            node, observations, adapter_status, simulated_ms, elapsed_ms, f
        )

    def repair(self, plan, failed, event=None):
        """RETRY, then bounded local repair on the same DAG, then one GLOBAL_REPLAN."""
        f = self.registry.functions[failed.function_id]
        blocked = failed.state == NodeState.BLOCKED and (event or {}).get("type") == "precondition"
        if failed.state not in (NodeState.FAILED, NodeState.INCONCLUSIVE) and not blocked:
            raise PlanError("repair_requires_failed_or_inconclusive_node")
        event = dict(event or failed.failure or {"type": "execution"}, node=failed.id)
        if not blocked and failed.retries < f.retry_limit and self.node_state(failed).attempts[f.id] < 2:
            failed.retries += 1
            failed.transition(NodeState.PENDING, "bounded_read_retry")
            plan.audit.append({"revision": plan.revision, "operator": "RETRY", "node": failed.id})
            return plan
        if self.max_repairs <= 0:
            raise PlanError("repair_budget")
        invalid_ids = set()
        if not blocked:
            invalid_ids = {e["id"] for e in self.state.evidence
                           if e.get("function_id") == failed.function_id and
                           (not failed.context_target or
                            e.get("target") == failed.target.get("id", failed.target.get("client_id")))}
            self.state.invalidate(invalid_ids)
        event["invalidated"] = sorted(invalid_ids)
        result = (local_repair(self, plan, failed, event) if self.repairs < self.max_repairs
                  else {"escalate": "local-exhausted"})
        if "operator" in result:
            self.repairs += 1
            if result["operator"] == "SUBSTITUTE":
                self.excluded.add(f.id)
            self.events.append({"revision": plan.revision, "node": failed.id, "repair": result["operator"]})
            return plan
        if blocked:
            raise PlanError("precondition_repair_failed:" + result["escalate"])
        return self.global_replan(plan, failed, result["escalate"])

    def global_replan(self, plan, failed, escalate):
        """Escalation after local repair: one full recompile (P_MAX), then INCOMPLETE."""
        if self.global_replans >= P_MAX:
            self.incomplete = True
            plan.audit.append({"revision": plan.revision, "operator": "INCOMPLETE", "node": failed.id,
                               "escalated_from": escalate})
            raise PlanError("repair_incomplete:" + escalate)
        self.global_replans += 1
        self.repairs += 1
        f = self.registry.functions[failed.function_id]
        affected = {failed.id} | plan.descendants(failed.id)
        # Invalidate only DATA/STATE descendants; ORDER does not imply bad data.
        invalid_ids = {eid for node_id in affected for eid in plan.nodes[node_id].output_evidence.values()}
        self.state.invalidate(invalid_ids)
        self.excluded.add(failed.function_id)
        requested_outputs = list(plan.goals)
        requested_functions = []
        for requested in plan.requested:
            if requested in self.excluded:
                requested_outputs.extend(self.registry.functions[requested].outputs)
            else:
                requested_functions.append(requested)
        if not requested_outputs and not requested_functions:
            requested_outputs = list(f.outputs)
        try:
            new_plan = self.compiler().compile(tuple(dict.fromkeys(requested_outputs)), self.state,
                                               requested=requested_functions, revision=plan.revision + 1,
                                               targets=plan.targets)
        except PlanError as exc:
            self.incomplete = True
            plan.audit.append({"revision": plan.revision, "operator": "INCOMPLETE", "node": failed.id,
                               "escalated_from": "global_replan_failed", "reason": str(exc)})
            raise PlanError("repair_incomplete:global_replan_failed") from exc
        reused, copied = [], set()
        for key, node in plan.nodes.items():
            # A renumbered id may now name another target's invocation: never overwrite it.
            if key not in affected and node.state == NodeState.SUCCEEDED and key not in new_plan.nodes:
                new_plan.nodes[key] = copy.deepcopy(node)
                copied.add(key)
                reused.extend(node.output_evidence.values())
        # Reused nodes keep the edges between them.
        new_plan.edges.extend(e for e in plan.edges
                              if e.source in copied and e.target in copied and e not in new_plan.edges)
        new_plan.connect_terminals()
        new_plan.audit.append({"revision": new_plan.revision, "operator": "GLOBAL_REPLAN",
                               "escalated_from": escalate, "previous_revision": plan.revision,
                               "failed": failed.id, "invalidated_nodes": sorted(affected), "reused_evidence": reused,
                               "added": sorted(set(new_plan.nodes) - set(plan.nodes)),
                               "removed": sorted(set(plan.nodes) - set(new_plan.nodes)),
                               "edges": [{"source": e.source, "target": e.target, "kind": e.kind, "port": e.port}
                                         for e in new_plan.edges]})
        return self.attach(new_plan)

    def precondition_events(self, plan):
        """BLOCKED nodes whose guard/binding is UNKNOWN (never FALSE): precondition events."""
        events = []
        for n in plan.nodes.values():
            if n.state != NodeState.BLOCKED or n.reason != "input_or_guard_not_verified":
                continue
            state = self.node_state(n)
            f = self.registry.functions[n.function_id]
            if any(p.evaluate(state) == Truth.FALSE for p in f.predicates):
                continue
            events.append((n, {"type": "precondition", "status": "UNKNOWN", "message": n.reason}))
        return events

    def run(self, plan):
        self.attach(plan)
        while True:
            node = self.step(plan)
            if node is None:
                repaired = False
                for blocked, event in self.precondition_events(plan):
                    try:
                        plan = self.repair(plan, blocked, event)
                        repaired = True
                        break
                    except PlanError as exc:
                        self.events.append({"revision": plan.revision, "repair_blocked": str(exc)})
                if not repaired:
                    break
                continue
            if node.state in (NodeState.FAILED, NodeState.INCONCLUSIVE):
                try:
                    plan = self.repair(plan, node)
                except PlanError as exc:
                    self.events.append({"revision": plan.revision, "repair_blocked": str(exc)})
                    # Independent READY nodes can still collect useful evidence.
                    continue
        return plan
