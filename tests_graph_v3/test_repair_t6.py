"""T6: typed verifier events, five bounded local repair operators, one global replan."""
import copy
import unittest

from gateway_pilot.core import ROOT, read_json, execute
from gateway_pilot.graph_v3.contracts import Port, Predicate, Function
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Binding, Compiler, Edge, ExecutionDAG, Invocation, NodeState
from gateway_pilot.graph_v3.repair import (DEFAULT_ORDER, L_MAX, RepairContext, bypass, classify,
                                           insert_prereq, local_repair, rebind, rewire, substitute)
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState


class RepairT6Tests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(c for c in read_json(ROOT / "data/cases.json") if c["template"] == "dns_fail"))
        self.state = CaseState(self.case, self.registry, lambda: 0.0)

    def put(self, fid):
        e = execute(fid, {}, self.state, self.case, self.registry.legacy)
        self.state.record(e)
        return e

    def alt(self, source, name, *, inputs=None):
        f = copy.deepcopy(self.registry.functions[source])
        f.id, f.cost = name, 3
        old = copy.deepcopy(self.registry.legacy.functions[source])
        old["id"] = name
        if inputs is not None:
            f.inputs = {p: self.registry.ports[p] for p in inputs}
            old["requires"] = list(inputs)
        self.registry.functions[name] = f
        self.registry.legacy.functions[name] = old
        self.state.capabilities.add(name)
        self.case["world"][name] = copy.deepcopy(self.case["world"][source])
        self.registry.rebuild()

    def run_until_failure(self, plan, runner, fid):
        runner.attach(plan)
        while True:
            node = runner.step(plan)
            if node is None or (node.function_id == fid and node.state in (NodeState.FAILED, NodeState.INCONCLUSIVE)):
                return node

    def context(self, runner, plan, node_id, kind):
        return RepairContext(runner, plan, node_id, {"type": kind, "node": node_id})

    def audits(self, runner, operator):
        plans = list({id(p): p for p in runner.plans}.values())  # run() re-attaches the same plan
        return [a for p in plans for a in p.audit if a.get("operator") == operator]

    # Verifier -----------------------------------------------------------------

    def test_verifier_classifies_timeout_postcondition_execution_and_precondition(self):
        self.assertEqual(DEFAULT_ORDER["timeout"], ("SUBSTITUTE", "BYPASS"))
        for world, expected in [({**self.case["world"]["wan.status"], "_duration_ms": 3000}, "timeout"),
                                ({"link_up": "true"}, "postcondition"),
                                ({"_status": "MISSING"}, "execution")]:
            with self.subTest(expected=expected):
                case = copy.deepcopy(self.case)
                case["world"]["wan.status"] = world
                state = CaseState(case, self.registry, lambda: 0.0)
                plan = Compiler(self.registry).compile(["wan.status"], state)
                node = GraphRunner(self.registry, case, state, max_repairs=0).step(
                    GraphRunner(self.registry, case, state).attach(plan))
                self.assertEqual(node.failure["type"], expected)
        self.assertEqual(classify("VERIFICATION_FAILED"), "postcondition")
        # Precondition: an invalidated input with no provider in the plan.
        self.put("wan.status")
        e = self.put("wan.routes")
        plan = Compiler(self.registry).compile(["wan.probe"], self.state)
        self.state.invalidate({e["id"]})
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.attach(plan)
        self.assertIsNone(runner.step(plan))
        [(node, event)] = runner.precondition_events(plan)
        self.assertEqual((node.function_id, event["type"]), ("wan.probe", "precondition"))

    # Operators: applicable and not applicable ---------------------------------

    def test_substitute_applies_only_with_same_port_scope_and_gate(self):
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        failed = self.run_until_failure(plan, runner, "wan.status")
        self.assertIsNone(substitute(self.context(runner, plan, failed.id, "timeout")))
        self.alt("wan.status", "z.status.backup")
        patch = substitute(self.context(runner, plan, failed.id, "timeout"))
        self.assertEqual(patch["replaced"], {"wan.status": "z.status.backup"})
        self.assertNotIn("wan.status", plan.nodes)
        self.assertEqual(plan.nodes["wan.routes"].bindings["wan.status"].ref, "z.status.backup")
        self.assertIn(Edge("z.status.backup", "wan.routes", "DATA", "wan.status"), plan.edges)

    def test_requested_root_is_substituted_locally(self):
        self.alt("dns.config", "z.config.backup")
        self.case["world"]["dns.config"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile([], self.state, requested=["dns.config"])
        runner = GraphRunner(self.registry, self.case, self.state)
        final = runner.run(plan)
        self.assertIs(final, plan)
        self.assertEqual([a["replaced"] for a in self.audits(runner, "SUBSTITUTE")],
                         [{"dns.config": "z.config.backup"}])
        self.assertEqual(final.requested, ("z.config.backup",))
        self.assertEqual(runner.global_replans, 0)

    def test_bypass_needs_downstream_facts_and_never_skips_a_goal_producer(self):
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        failed = self.run_until_failure(plan, runner, "wan.status")
        self.assertIsNone(bypass(self.context(runner, plan, failed.id, "timeout")))
        fresh = self.put("wan.status")  # fallback observation from outside this plan
        patch = bypass(self.context(runner, plan, failed.id, "timeout"))
        self.assertEqual(patch["skipped"], ["wan.status"])
        self.assertEqual(plan.nodes["wan.status"].state, NodeState.SKIPPED)
        self.assertEqual(plan.nodes["wan.routes"].bindings["wan.status"].ref, fresh["id"])
        goal_plan = Compiler(self.registry).compile(["wan.status"], CaseState(self.case, self.registry))
        node = goal_plan.nodes["wan.status"]
        node.state = NodeState.FAILED
        self.assertIsNone(bypass(self.context(runner, goal_plan, node.id, "timeout")))

    def test_rebind_moves_stale_evidence_binding_to_fresh_fact(self):
        old = self.put("wan.status")
        self.case["world"]["wan.routes"] = {"_status": "MISSING"}
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        self.assertEqual(plan.nodes["wan.routes"].bindings["wan.status"].ref, old["id"])
        runner = GraphRunner(self.registry, self.case, self.state)
        failed = self.run_until_failure(plan, runner, "wan.routes")
        self.assertIsNone(rebind(self.context(runner, plan, failed.id, "execution")))
        new = self.put("wan.status")  # supersedes the old observation
        patch = rebind(self.context(runner, plan, failed.id, "execution"))
        self.assertEqual(patch["rebound"], ["wan.status"])
        self.assertEqual(plan.nodes["wan.routes"].bindings["wan.status"].ref, new["id"])
        self.assertEqual(plan.nodes["wan.routes"].function_id, "wan.routes")

    def test_insert_prereq_adds_bounded_producers_and_run_recovers(self):
        self.put("wan.status")
        e = self.put("wan.routes")
        plan = Compiler(self.registry).compile(["wan.probe"], self.state)
        self.assertEqual(set(plan.nodes), {"wan.probe"})
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.attach(plan)
        self.assertIsNone(insert_prereq(self.context(runner, plan, "wan.probe", "precondition")))
        self.state.invalidate({e["id"]})
        final = runner.run(plan)
        [audit] = self.audits(runner, "INSERT_PREREQ")
        self.assertEqual(audit["added_nodes"], ["wan.routes"])
        self.assertEqual(audit["added_edges"], [dict(source="wan.routes", target="wan.probe", kind="DATA",
                                                     port="wan.routes", hard=True)])
        self.assertLessEqual(len(audit["added_nodes"]), L_MAX)
        self.assertEqual(final.nodes["wan.probe"].state, NodeState.SUCCEEDED)
        self.assertEqual(final.revision, 2)

    def test_insert_prereq_needing_four_nodes_is_aborted_without_partial_patch(self):
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                  "additionalProperties": True}
        ports = {n: Port(n, "gateway", schema, provenance="synthetic_replay/") for n in ("x1", "x2", "x3", "x4", "y")}
        self.registry.ports.update(ports)
        chain = [("p1", [], "x1"), ("p2", ["x1"], "x2"), ("p3", ["x2"], "x3"), ("p4", ["x3"], "x4"), ("c", ["x4"], "y")]
        for fid, inputs, output in chain:
            self.registry.functions[fid] = Function(fid, ("SK04",), {p: ports[p] for p in inputs},
                                                    {output: ports[output]}, fid, "gateway")
            self.registry.legacy.functions[fid] = {"id": fid, "produces": [output], "requires": inputs,
                                                   "risk": "READ", "scope": "gateway", "ttl_s": 30}
            self.registry.legacy.data["port_fields"][output] = {"ok": "bool"}
            self.case["world"][fid] = {"ok": True}
            self.state.capabilities.add(fid)
        self.registry.rebuild()
        first = Compiler(self.registry).compile(["x4"], self.state)
        GraphRunner(self.registry, self.case, self.state).run(first)
        plan = Compiler(self.registry).compile(["y"], self.state)
        self.assertEqual(set(plan.nodes), {"c"})
        self.state.invalidate({e["id"] for e in self.state.evidence if e["port"] in {"x1", "x2", "x3", "x4"}})
        nodes, edges = set(plan.nodes), list(plan.edges)
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.attach(plan)
        self.assertIsNone(insert_prereq(self.context(runner, plan, "c", "precondition")))
        self.assertEqual((set(plan.nodes), plan.edges), (nodes, edges))

    def test_rewire_removes_only_soft_order_edges(self):
        soft = Edge("dns.config", "wan.status", "ORDER", hard=False)
        plan = Compiler(self.registry).compile(["dns.config", "wan.routes"], self.state, order_constraints=[soft])
        self.assertIn(soft, plan.edges)
        runner = GraphRunner(self.registry, self.case, self.state)
        data = [e for e in plan.edges if e.kind == "DATA"]
        self.assertTrue(data)
        self.assertIsNone(rewire(self.context(runner, plan, "wan.routes", "execution")))
        self.assertEqual([e for e in plan.edges if e.kind == "DATA"], data)
        self.assertEqual(rewire(self.context(runner, plan, "wan.status", "execution"))["operator"], "REWIRE")
        self.assertNotIn(soft, plan.edges)
        self.assertEqual([e for e in plan.edges if e.kind == "DATA"], data)
        self.assertIsNone(rewire(self.context(runner, plan, "wan.status", "execution")))

    def custom(self, specs, predicates=None):
        """Gateway functions (fid, inputs, outputs) over boolean ports, with replay values."""
        schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
                  "additionalProperties": True}
        for fid, inputs, outputs in specs:
            for name in (*inputs, *outputs):
                self.registry.ports.setdefault(name, Port(name, "gateway", schema, provenance="synthetic_replay/"))
                self.registry.legacy.data["port_fields"][name] = {"ok": "bool"}
            ports = self.registry.ports
            self.registry.functions[fid] = Function(fid, ("SK04",), {p: ports[p] for p in inputs},
                                                    {p: ports[p] for p in outputs}, fid, "gateway",
                                                    predicates=tuple((predicates or {}).get(fid, ())))
            self.registry.legacy.functions[fid] = {"id": fid, "produces": list(outputs), "requires": list(inputs),
                                                   "risk": "READ", "scope": "gateway", "ttl_s": 30}
            self.case["world"][fid] = ({"ok": True} if len(outputs) == 1 else
                                       {"outputs": {p: {"ok": True} for p in outputs}})
            self.state.capabilities.add(fid)
        self.registry.rebuild()

    def test_insert_prereq_over_edge_budget_is_aborted(self):
        # Three new producers but six new edges (E_MAX = 5): the whole patch is refused.
        self.custom([("p1", [], ["x1"]), ("p2", ["x1"], ["x2"]), ("p3", ["x1", "x2"], ["x3"]),
                     ("c", ["x1", "x2", "x3"], ["y"])])
        GraphRunner(self.registry, self.case, self.state).run(
            Compiler(self.registry).compile(["x1", "x2", "x3"], self.state))
        plan = Compiler(self.registry).compile(["y"], self.state)
        self.assertEqual(set(plan.nodes), {"c"})
        self.state.invalidate({e["id"] for e in self.state.evidence if e["port"] in {"x1", "x2", "x3"}})
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.attach(plan)
        nodes, edges = set(plan.nodes), list(plan.edges)
        self.assertIsNone(insert_prereq(self.context(runner, plan, "c", "precondition")))
        self.assertEqual((set(plan.nodes), plan.edges), (nodes, edges))

    def test_insert_prereq_refuses_when_another_guard_is_false(self):
        # c's input x lacks a provider (fixable), but its guard on y is FALSE: a finding, not a gap.
        self.custom([("px", [], ["x"]), ("py", [], ["y"]), ("c", ["x"], ["z"])],
                    predicates={"c": [Predicate("y", "ok", "eq", True)]})
        self.case["world"]["py"] = {"ok": False}
        GraphRunner(self.registry, self.case, self.state).run(Compiler(self.registry).compile(["y"], self.state))
        f = self.registry.functions["c"]
        plan = ExecutionDAG(())
        plan.nodes["c"] = Invocation("c", "c", "SK04", {"scope": "gateway", "id": self.state.gateway_id},
                                     {"x": Binding("evidence", "missing", "x")}, f.verifier, f.digest(),
                                     state=NodeState.BLOCKED, repair_budget=2)
        runner = GraphRunner(self.registry, self.case, self.state)
        self.assertIsNone(insert_prereq(self.context(runner, plan, "c", "precondition")))
        self.assertEqual(set(plan.nodes), {"c"})
        self.case["world"]["py"] = {"ok": True}  # with the guard TRUE the same gap is repaired
        self.state.invalidate({e["id"] for e in self.state.evidence if e["port"] == "y"})
        GraphRunner(self.registry, self.case, self.state).run(Compiler(self.registry).compile(["y"], self.state))
        self.assertEqual(insert_prereq(self.context(runner, plan, "c", "precondition"))["operator"], "INSERT_PREREQ")
        self.assertEqual(set(plan.nodes), {"c", "px"})

    def test_substitute_rejects_wrong_schema_scope_or_gated_alternative(self):
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        failed = self.run_until_failure(plan, runner, "wan.status")
        port = self.registry.ports["wan.status"]
        variants = {
            "schema": dict(outputs={"wan.status": Port("wan.status", "gateway", {"type": "object"},
                                                       provenance=port.provenance)}),
            "scope": dict(scope="client"),
            "gate": dict(),
        }
        for name, change in variants.items():
            with self.subTest(name):
                self.alt("wan.status", "z.status." + name)
                for key, value in change.items():
                    setattr(self.registry.functions["z.status." + name], key, value)
                if name == "gate":
                    self.state.capabilities.discard("z.status.gate")
                self.registry.rebuild()
                self.assertIsNone(substitute(self.context(runner, plan, failed.id, "timeout")))
                del self.registry.functions["z.status." + name]
                self.registry.rebuild()

    def test_rewire_never_removes_a_hard_order_edge(self):
        hard = Edge("dns.config", "wan.status", "ORDER", hard=True)
        plan = Compiler(self.registry).compile(["dns.config", "wan.routes"], self.state, order_constraints=[hard])
        runner = GraphRunner(self.registry, self.case, self.state)
        self.assertIsNone(rewire(self.context(runner, plan, "wan.status", "execution")))
        self.assertIn(hard, plan.edges)

    def test_global_replan_does_not_reuse_a_node_that_must_rerun(self):
        self.alt("wan.status", "z.status.global", inputs=["system.resources"])
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile(["dns.probe", "wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.attach(plan)
        runner.step(plan, "dns.config")
        runner.step(plan, "wan.status")
        self.state.invalidate({self.state.fact("dns.config")["id"]})  # stale before the replan
        new_plan = runner.repair(plan, plan.nodes["wan.status"])
        self.assertEqual(new_plan.nodes["dns.config"].state, NodeState.PENDING)
        runner.run(new_plan)
        self.assertEqual(self.state.attempts["dns.config"], 2)

    # Escalation and preservation ------------------------------------------------

    def test_timeout_with_only_a_different_port_alternative_escalates_instead_of_substituting(self):
        self.put("wan.status")
        self.put("wan.routes")
        self.case["world"]["wan.probe"]["_duration_ms"] = 3000
        self.assertIn("client.probe", self.registry.functions)
        plan = Compiler(self.registry).compile(["wan.probe"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.run(plan)
        self.assertFalse(self.audits(runner, "SUBSTITUTE"))
        self.assertEqual(runner.global_replans, 1)
        self.assertTrue(runner.incomplete)
        self.assertFalse(any(n.function_id == "client.probe" for p in runner.plans for n in p.nodes.values()))

    def test_independent_succeeded_branch_keeps_evidence_ids(self):
        self.alt("wan.status", "z.status.backup")
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile(["dns.probe", "wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        self.run_until_failure(plan, runner, "wan.status")
        before = {"dns.config": self.state.fact("dns.config")["id"]}
        final = runner.repair(plan, plan.nodes["wan.status"])
        self.assertIs(final, plan)
        self.assertEqual({p: plan.nodes[p].output_evidence[p] for p in before}, before)
        runner.run(final)
        self.assertEqual({p: self.state.fact(p)["id"] for p in before}, before)
        self.assertEqual(self.state.attempts["dns.config"], 1)
        self.assertTrue(self.state.fact("dns.probe"))

    def test_exceeding_r_max_escalates_to_exactly_one_global_replan_then_incomplete(self):
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        self.alt("wan.status", "z.status.a")
        self.alt("wan.status", "z.status.b")
        # Needs an extra producer: not a local substitute, but admissible for the global replan.
        self.alt("wan.status", "z.status.global", inputs=["system.resources"])
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state, max_repairs=10)
        runner.run(plan)
        substitutes = self.audits(runner, "SUBSTITUTE")
        self.assertEqual([list(a["replaced"].values())[0] for a in substitutes], ["z.status.a", "z.status.b"])
        self.assertEqual(len(self.audits(runner, "GLOBAL_REPLAN")), 1)
        self.assertEqual(self.audits(runner, "GLOBAL_REPLAN")[0]["escalated_from"], "local-exhausted")
        self.assertTrue(self.audits(runner, "INCOMPLETE"))
        self.assertTrue(runner.incomplete)
        self.assertEqual(runner.global_replans, 1)

    def test_global_replan_keeps_edges_between_reused_nodes(self):
        self.alt("wan.status", "z.status.global", inputs=["system.resources"])
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile(["dns.probe", "wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        runner.attach(plan)
        for fid in ("dns.config", "dns.probe", "wan.status"):
            runner.step(plan, fid)
        final = runner.run(runner.repair(plan, plan.nodes["wan.status"]))
        [audit] = self.audits(runner, "GLOBAL_REPLAN")
        self.assertEqual(audit["escalated_from"], "local-failed")
        self.assertIn(Edge("dns.config", "dns.probe", "DATA", "dns.config"), final.edges)
        self.assertEqual(final.nodes["dns.probe"].state, NodeState.SUCCEEDED)
        self.assertTrue(self.state.fact("wan.routes"))

    def test_local_repair_spends_node_budget_then_reports_exhaustion(self):
        self.case["world"]["wan.status"]["_duration_ms"] = 3000
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        runner = GraphRunner(self.registry, self.case, self.state)
        failed = self.run_until_failure(plan, runner, "wan.status")
        event = {"type": "timeout"}
        self.assertEqual(local_repair(runner, plan, failed, event), {"escalate": "local-failed"})
        self.assertEqual(local_repair(runner, plan, plan.nodes["wan.status"], event), {"escalate": "local-failed"})
        self.assertEqual(local_repair(runner, plan, plan.nodes["wan.status"], event), {"escalate": "local-exhausted"})
        self.assertEqual(plan.revision, 1)


if __name__ == "__main__":
    unittest.main()
