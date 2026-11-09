"""Read-only DAG scheduler, per-node verifier and bounded local plan repair."""
import copy
from ..core import PlanError, bind_and_gate, execute
from .contracts import Truth, validate
from .planner import Compiler, NodeState


class GraphRunner:
    def __init__(self, registry, case, state, *, max_calls=12, max_repairs=2, deadline_s=120, cost_budget=100):
        self.registry, self.case, self.state = registry, case, state
        self.max_calls, self.max_repairs, self.deadline_s, self.cost_budget = max_calls, max_repairs, deadline_s, cost_budget
        self.started = state.clock()
        self.calls = self.repairs = 0
        self.spent = 0
        self.plans, self.events, self.excluded = [], [], set()

    def compiler(self):
        return Compiler(self.registry, max_cost=max(0, self.cost_budget - self.spent), excluded=self.excluded)

    def attach(self, plan):
        plan.topological()
        self.plans.append(plan)
        return plan

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
            if n.contract_digest != f.digest():
                raise PlanError("contract_changed_after_compile")
            if not self.state.allowed(f):
                if n.state != NodeState.BLOCKED:
                    n.transition(NodeState.BLOCKED, "capability_or_permission_changed")
                continue
            bindings_ok = True
            for name, b in n.bindings.items():
                required = f.inputs.get(name, self.registry.ports[name])
                expected_id = b.ref if b.kind == "evidence" else plan.nodes[b.ref].output_evidence.get(name)
                e = self.state.by_id(expected_id, required)
                if e is None or e["id"] != expected_id:
                    bindings_ok = False
                    break
            predicates = [p.evaluate(self.state) for p in f.predicates]
            if not bindings_ok or any(t != Truth.TRUE for t in predicates):
                if n.state != NodeState.BLOCKED:
                    n.transition(NodeState.BLOCKED, "input_or_guard_not_verified")
                continue
            if any(not any(e["id"] == eid and self.state.usable(e, self.registry.ports[e["port"]]) for e in self.state.evidence)
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
        if self.spent + self.registry.objective(f.id) > self.cost_budget:
            raise PlanError("runner_cost_budget")
        # Recheck actual arguments/target immediately before invocation.
        arguments = {}
        for argument, (port_name, path) in f.argument_sources.items():
            binding = n.bindings.get(port_name)
            if binding is None:
                raise PlanError('unbound_argument_source:' + argument)
            eid = binding.ref if binding.kind == 'evidence' else plan.nodes[binding.ref].output_evidence.get(port_name)
            evidence = self.state.by_id(eid, f.inputs.get(port_name, self.registry.ports[port_name]))
            if evidence is None:
                raise PlanError('argument_evidence_unavailable:' + argument)
            value = evidence['value']
            for key in path.split('.'):
                if not isinstance(value, dict) or key not in value:
                    raise PlanError('argument_path_unavailable:' + argument)
                value = value[key]
            arguments[argument] = value
        arguments = bind_and_gate(f.id, arguments, self.state, self.registry.legacy)
        if not validate(arguments, f.arguments_schema):
            raise PlanError("argument_schema")
        n.arguments = arguments
        if f.scope == "client" and arguments.get("client_id"):
            n.target["id"] = arguments["client_id"]
        n.transition(NodeState.RUNNING, "policy_and_bindings_passed")
        before = self.state.clock()
        self.calls += 1
        self.spent += self.registry.objective(f.id)
        local_case = copy.deepcopy(self.case)
        response = local_case["world"].get(f.id, {})
        simulated_ms = response.pop("_duration_ms", 0) if isinstance(response, dict) else 0
        try:
            # The only executor remains the replay adapter, never a shell/router.
            if len(f.outputs) == 1:
                observations = [execute(f.id, arguments, self.state, local_case, self.registry.legacy)]
            else:
                # Explicit multi-output replay envelope for hyperedges. One call,
                # separate evidence records and validation for each output port.
                self.state.attempts[f.id] += 1
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
                         "age_s": age, "ttl_s": 30, "status": status, "value": value,
                         "observed_at": "2026-11-07T00:00:00Z"}
                    self.state.evidence.append(e)
                    observations.append(e)
            elapsed_ms = 1000 * (self.state.clock() - before)
            for e in observations:
                self.state.record(e)
                if max(simulated_ms, elapsed_ms) > f.timeout_ms:
                    e["status"] = "TIMEOUT"
                e["verifier"] = f.verifier
                e["contract_digest"] = f.digest()
                if e["status"] == "OK" and self.state.fact(e["port"], f.outputs[e["port"]]) is not e:
                    e["status"] = "VERIFICATION_FAILED"
            if all(e["status"] == "OK" for e in observations):
                n.output_evidence = {e["port"]: e["id"] for e in observations}
                n.transition(NodeState.SUCCEEDED, "schema_scope_source_freshness_verified")
            else:
                status = next(e["status"] for e in observations if e["status"] != "OK")
                n.transition(NodeState.FAILED if status == "TIMEOUT" else NodeState.INCONCLUSIVE, status)
        except PlanError as exc:
            n.transition(NodeState.FAILED, str(exc))
        self.events.append({"revision": plan.revision, "node": n.id, "state": n.state, "reason": n.reason})
        return n

    def repair(self, plan, failed):
        f = self.registry.functions[failed.function_id]
        if failed.state not in (NodeState.FAILED, NodeState.INCONCLUSIVE):
            raise PlanError("repair_requires_failed_or_inconclusive_node")
        if failed.retries < f.retry_limit and self.state.attempts[f.id] < 2:
            failed.retries += 1
            failed.transition(NodeState.PENDING, "bounded_read_retry")
            plan.audit.append({"revision": plan.revision, "operator": "RETRY", "node": failed.id})
            return plan
        if self.repairs >= self.max_repairs:
            raise PlanError("repair_budget")
        self.repairs += 1
        affected = {failed.id} | plan.descendants(failed.id)
        # Invalidate only DATA/STATE descendants; ORDER does not imply bad data.
        invalid_ids = {eid for node_id in affected for eid in plan.nodes[node_id].output_evidence.values()}
        invalid_ids |= {e["id"] for e in self.state.evidence if e.get("function_id") == failed.function_id}
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
        new_plan = self.compiler().compile(tuple(dict.fromkeys(requested_outputs)), self.state,
                                           requested=requested_functions, revision=plan.revision + 1)
        reused = []
        for key, node in plan.nodes.items():
            if key not in affected and node.state == NodeState.SUCCEEDED:
                new_plan.nodes.setdefault(key, copy.deepcopy(node))
                reused.extend(node.output_evidence.values())
        new_plan.audit.append({"revision": new_plan.revision, "operator": "SUBSTITUTE_REWIRE_INSERT_PREREQ",
                               "previous_revision": plan.revision, "failed": failed.id,
                               "invalidated_nodes": sorted(affected), "reused_evidence": reused,
                               "added": sorted(set(new_plan.nodes) - set(plan.nodes)),
                               "removed": sorted(set(plan.nodes) - set(new_plan.nodes)),
                               "edges": [{"source": e.source, "target": e.target, "kind": e.kind, "port": e.port}
                                         for e in new_plan.edges]})
        return self.attach(new_plan)

    def run(self, plan):
        self.attach(plan)
        while True:
            node = self.step(plan)
            if node is None:
                break
            if node.state in (NodeState.FAILED, NodeState.INCONCLUSIVE):
                try:
                    plan = self.repair(plan, node)
                except PlanError as exc:
                    self.events.append({"revision": plan.revision, "repair_blocked": str(exc)})
                    # Independent READY nodes can still collect useful evidence.
                    continue
        return plan
