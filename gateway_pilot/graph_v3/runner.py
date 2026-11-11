"""Read-only DAG scheduler, typed per-node verifier and bounded repair.

GATEWAY_DESIGN. Local repair operators live in repair.py; see its docstring for
the relation to the unofficial GraSP reproduction.
"""
import copy
from ..core import PlanError, bind_and_gate, execute
from .contracts import Truth, validate
from .planner import Compiler, NodeState
from .repair import P_MAX, classify, local_repair


class GraphRunner:
    def __init__(self, registry, case, state, *, max_calls=12, max_repairs=2, deadline_s=120, cost_budget=100):
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
        live = "live_reader" in self.case
        # The adapter is a service object, not replay data: share it, copy the rest.
        local_case = self.case if live else {key: value if key == "adapter" else copy.deepcopy(value)
                                             for key, value in self.case.items()}
        response = {} if live else local_case["world"].get(f.id, {})
        simulated_ms = response.pop("_duration_ms", 0) if isinstance(response, dict) else 0
        try:
            adapter = self.case.get("adapter")
            if len(f.outputs) == 1:
                observations = [adapter.call(f.id, arguments, state, local_case) if adapter is not None
                                else execute(f.id, arguments, state, local_case, self.registry.legacy)]
            elif live:
                raise PlanError("live_requires_single_output_contract")
            else:
                # Explicit multi-output replay envelope for hyperedges. One call,
                # separate evidence records and validation for each output port.
                state.attempts[f.id] += 1
                self.state.executed.append({"function_id": f.id, "arguments": arguments})
                observations = []
                for name, port in f.outputs.items():
                    value = copy.deepcopy(response.get("outputs", {}).get(name, {}))
                    status = value.pop("_status", "OK")
                    age = value.pop("_age_s", 0)
                    target = value.pop("_target", self.state.gateway_id if port.scope == "gateway" else
                                       arguments.get("client_id", value.get("client_id", "unresolved")))
                    e = {"id": "e" + str(len(self.state.evidence) + 1), "function_id": f.id,
                         "port": name, "scope": port.scope, "target": target, "source": "synthetic_replay/v3",
                         "age_s": age, "ttl_s": self.ttl_seconds(f), "status": status, "value": value,
                         "observed_at": self.state.observed_at()}
                    self.state.evidence.append(e)
                    observations.append(e)
            elapsed_ms = 1000 * (self.state.clock() - before)
            adapter_status = {e["id"]: e["status"] for e in observations}
            for e in observations:
                e["ttl_s"] = self.ttl_seconds(f)  # freshness bound comes from the contract
                if (n.context_target and e["scope"] == "client" and
                        e["target"] != n.context_target["client_id"]):
                    e["_scope_mismatch"] = True
                    e["_invalidated"] = True
                    e["status"] = "VERIFICATION_FAILED"
                state.record(e)
                if max(simulated_ms, elapsed_ms) > f.timeout_ms:
                    e["status"] = "TIMEOUT"
                e["verifier"] = f.verifier
                e["contract_digest"] = f.digest()
                if e["status"] == "OK" and state.fact(e["port"], f.outputs[e["port"]]) is not e:
                    e["status"] = "VERIFICATION_FAILED"
                self.annotate(e, n, f, state)
            self.contract_b.append(self.export_contract_b(n, observations, adapter_status, simulated_ms, elapsed_ms, f))
            self.state.refresh_revision()
            if all(e["status"] == "OK" for e in observations):
                n.output_evidence = {e["port"]: e["id"] for e in observations}
                n.transition(NodeState.SUCCEEDED, "schema_scope_source_freshness_verified")
            else:
                status = next(e["status"] for e in observations if e["status"] != "OK")
                n.failure = {"type": classify(status), "status": status, "message": status}
                n.transition(NodeState.FAILED if status == "TIMEOUT" else NodeState.INCONCLUSIVE, status)
        except PlanError as exc:
            n.failure = {"type": "execution", "status": "ERROR", "message": str(exc)}
            n.transition(NodeState.FAILED, str(exc))
            self.contract_b.append({"node_id": n.id, "tool_status": "EXIT_ERROR", "observations": [],
                                    "goal_claim": "NOT_EVALUATED"})
        self.events.append({"revision": plan.revision, "node": n.id, "state": n.state, "reason": n.reason})
        return n

    def ttl_seconds(self, f):
        """TTL from the Function contract (v0.1 ttl_seconds, else the legacy ttl_s)."""
        ttl = getattr(f, "ttl_seconds", None)
        return ttl if ttl is not None else self.registry.legacy.functions[f.id]["ttl_s"]

    def annotate(self, e, node, f, state):
        """Complete the HTML evidence record fields after verification."""
        port = f.outputs.get(e["port"])
        if e.get("source", "").startswith("synthetic_replay"):
            e["observed_at"] = self.state.observed_at()
        e.update(evidence_id=e["id"], case_id=self.state.case_id, skill_context=node.skill_context,
                 ttl_seconds=e.get("ttl_s"), raw=copy.deepcopy(e.get("value")))
        e["validator_result"] = state.validator(e, port) if port is not None else {}
        e["assertions"] = state.assertions_for(e) if e["status"] == "OK" else []

    @staticmethod
    def export_contract_b(node, observations, adapter_status, simulated_ms, elapsed_ms, f):
        """Contract B (runner -> evidence layer): tool status kept apart from any goal claim."""
        statuses = set(adapter_status.values())
        if "TIMEOUT" in statuses or max(simulated_ms, elapsed_ms) > f.timeout_ms:
            tool = "TIMEOUT"
        elif statuses <= {"OK", "PARSE_ERROR"}:
            tool = "EXIT_OK"  # the adapter answered; verification is the evidence layer's job
        else:
            tool = "EXIT_ERROR"
        return {"node_id": node.id, "tool_status": tool,
                "observations": [{"evidence_id": e["id"], "kind": e["port"], "target": e["target"],
                                  "scope": e["scope"], "result": e["status"], "source": e["source"]}
                                 for e in observations],
                "goal_claim": "NOT_EVALUATED"}

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
