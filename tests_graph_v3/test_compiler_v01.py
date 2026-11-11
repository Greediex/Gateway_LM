import copy
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.contracts import Function, Port, Predicate
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler, Edge
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState


class CompilerV01Tests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry.from_v01()
        self.case = {
            "id": "test-case",
            "target": {"scope": "gateway"},
            "capabilities": list(self.registry.functions),
            "world": {},
        }
        self.state = CaseState(self.case, self.registry)

    def test_target_specific_invocations_bind_and_execute_independently(self):
        clients = ("client-a", "client-b")
        targets = [{"scope": "client", "client_id": client, "selector": client} for client in clients]

        def reader(fid, state):
            client = state.target["client_id"]
            if fid == "clients.resolve":
                observation = {"client_id": client, "unique": True}
            else:
                observation = {"configured": True, "address": "192.0.2." + str(clients.index(client) + 1)}
            return observation, "synthetic_replay/v1", "2026-11-10T00:00:00Z"

        self.case["live_reader"] = reader
        plan = Compiler(self.registry).compile(["client.ipv4"], self.state, targets=targets)
        self.assertEqual(set(plan.nodes), {"clients.resolve#1", "clients.resolve#2", "client.ipv4#1", "client.ipv4#2"})
        for index, client in enumerate(clients, 1):
            node = plan.nodes[f"client.ipv4#{index}"]
            self.assertEqual(node.target["client_id"], client)
            self.assertEqual(node.bindings["client.identity"].ref, f"clients.resolve#{index}")
        runner = GraphRunner(self.registry, self.case, self.state, max_repairs=0)
        runner.attach(plan)
        runner.step(plan, "clients.resolve#1")
        runner.step(plan, "clients.resolve#2")
        while runner.step(plan) is not None:
            pass
        for index, client in enumerate(clients, 1):
            node = plan.nodes[f"client.ipv4#{index}"]
            self.assertEqual(node.state, "SUCCEEDED")
            observation = next(e for e in self.state.evidence if e["id"] == node.output_evidence["client.ipv4"])
            self.assertEqual(observation["target"], client)
            self.assertEqual(observation["value"]["address"], f"192.0.2.{index}")
        self.assertIsNone(self.state.fact("client.ipv4"))

    def test_wrong_target_observation_cannot_supersede_another_clients_fact(self):
        targets = [{"scope": "client", "client_id": client} for client in ("a", "b")]

        def reader(fid, state):
            client = state.target["client_id"]
            if fid == "clients.resolve":
                observation = {"client_id": client, "unique": True}
            else:
                observation = {"configured": True, "address": "192.0.2.1", "_target": "a"}
            return observation, "synthetic_replay/v1", "2026-11-10T00:00:00Z"

        self.case["live_reader"] = reader
        plan = Compiler(self.registry).compile(["client.ipv4"], self.state, targets=targets)
        GraphRunner(self.registry, self.case, self.state, max_repairs=0).run(plan)
        verified, wrong = plan.nodes["client.ipv4#1"], plan.nodes["client.ipv4#2"]
        self.assertEqual(verified.state, "SUCCEEDED")
        self.assertEqual(wrong.state, "INCONCLUSIVE")
        first_client = self.state.for_target(targets[0]).fact("client.ipv4")
        self.assertEqual(first_client["id"], verified.output_evidence["client.ipv4"])

    def test_soft_order_cycle_is_audited_and_hard_cycle_is_rejected(self):
        compiler = Compiler(self.registry)
        soft = Edge("wan.routes#1", "wan.status#1", "ORDER", hard=False)
        plan = compiler.compile(["wan.routes"], self.state, order_constraints=[soft])
        self.assertNotIn(soft, plan.edges)
        self.assertTrue(any(e["operator"] == "DROP_SOFT_ORDER" for e in plan.audit))
        hard = Edge("wan.routes#1", "wan.status#1", "DATA", "wan.routes")
        with self.assertRaisesRegex(PlanError, "execution_cycle"):
            compiler.compile(["wan.routes"], self.state, order_constraints=[hard])

    def test_contract_a_includes_structural_nodes_and_validates(self):
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        schema = read_json(ROOT / "docs/contracts/contract_a.schema.json")
        Draft202012Validator.check_schema(schema)
        contract = plan.export_contract_a()
        Draft202012Validator(schema).validate(contract)
        self.assertEqual(plan.export()["contract_a"], contract)
        self.assertEqual(contract["case_id"], "test-case")
        nodes = {n["node_id"]: n for n in contract["nodes"]}
        self.assertEqual(nodes["snk"]["requires"], ["wan.routes"])
        self.assertEqual(nodes["wan.routes#1"]["args"]["wan.status"]["ref"], "wan.status#1")
        self.assertEqual(nodes["wan.routes#1"]["repair_budget"], 2)
        self.assertIn({"from": "src", "to": "wan.status#1", "type": "ORDER"}, contract["edges"])
        self.assertIn({"from": "wan.routes#1", "to": "snk", "type": "ORDER"}, contract["edges"])

    def test_structural_validation_distinguishes_uncovered_goal_and_no_path(self):
        plan = Compiler(self.registry).compile(["wan.routes"], self.state)
        disconnected = copy.deepcopy(plan)
        disconnected.structural_edges = []
        with self.assertRaisesRegex(PlanError, "source_sink_disconnected"):
            disconnected.validate_structure()
        with patch.object(plan, "topological", return_value=["snk", "wan.routes#1", "wan.status#1", "src"]):
            with self.assertRaisesRegex(PlanError, "invalid_topological_order"):
                plan.validate_structure()
        plan.goal_bindings.clear()
        with self.assertRaisesRegex(PlanError, "uncovered_plan_goal"):
            plan.validate_structure()

    def test_backward_filter_and_typed_edges_match_reproduction_apple_fixture(self):
        # third_party/grasp-reproduction/skill-dag/test/verify.js, section [1].
        # Parameter relations in the JS fixture become typed DATA input ports.
        registry = GraphRegistry()
        schema = {"type": "object"}
        names = ("location", "opened", "holding", "at_sink", "clean", "on_counter", "hot", "sliced")
        ports = {name: Port(name, "gateway", schema) for name in names}
        registry.ports.update(ports)
        library = [
            ("find", [], [], "location"), ("open", [], [], "opened"),
            ("pick", ["location"], ["location", "opened"], "holding"),
            ("goto", [], [], "at_sink"), ("clean", ["holding"], ["holding"], "clean"),
            ("put", ["holding"], ["holding"], "on_counter"),
            ("heat", [], [], "hot"), ("slice", [], [], "sliced"),
        ]
        for fid, inputs, guards, effect in library:
            registry.functions[fid] = Function(
                fid, ("SK04",), {p: ports[p] for p in inputs}, {effect: ports[effect]}, fid,
                "gateway", predicates=tuple(Predicate(port) for port in guards),
            )
            registry.legacy.functions[fid] = {"id": fid}
        registry.rebuild()
        state = CaseState({"target": {}, "capabilities": [row[0] for row in library]}, registry)
        plan = Compiler(registry).compile(["clean", "on_counter"], state)
        self.assertEqual(set(plan.nodes), {"find", "open", "pick", "clean", "put"})
        self.assertEqual({(e.source, e.target) for e in plan.edges if e.kind == "STATE"},
                         {("find", "pick"), ("open", "pick"), ("pick", "clean"), ("pick", "put")})
        self.assertEqual({(e.source, e.target) for e in plan.edges if e.kind == "DATA"},
                         {("find", "pick"), ("pick", "clean"), ("pick", "put")})
