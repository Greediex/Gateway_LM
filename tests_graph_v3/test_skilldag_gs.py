"""T2: pinned SkillDAG G_S semantics, in-memory edits and lexical search."""
import copy
import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry, Relation, SkillGraph
from gateway_pilot.graph_v3.skilldag import backend, check_skills, memory_backend
from gateway_pilot.graph_v3.state import CaseState


class SkillDAGTests(unittest.TestCase):
    def graph(self, *relations):
        return SkillGraph({s: {"name": "needle" if s == "A" else s,
                               "description": ""} for s in "ABCDEFG"}, relations)

    def apply(self, graph, proposal):
        return graph.apply(proposal, permissions={"graph.edit"}, actor="test")

    def test_specializes_cycle_through_backbone(self):
        graph = self.graph(Relation("A", "B", "depends_on"), Relation("B", "C", "specializes"))
        with self.assertRaisesRegex(PlanError, "WOULD_CREATE_CYCLE"):
            graph.propose_edge(Relation("C", "A", "specializes"), reason="cycle")
        with self.assertRaisesRegex(PlanError, "WOULD_CREATE_CYCLE"):
            graph.edit_edge("add", source="C", target="A", edge_type="specializes",
                            reason="cycle", base_version=1, permissions={"graph.edit"})
        self.assertEqual(graph.version, 1)

    def test_contradictory_edge_and_reason_required(self):
        graph = self.graph(Relation("A", "B", "depends_on"))
        with self.assertRaisesRegex(PlanError, "CONTRADICTORY_EDGE"):
            graph.propose_edge(Relation("B", "A", "conflicts_with"), reason="exclude")
        for reason in (None, "", "  "):
            with self.subTest(reason=reason), self.assertRaisesRegex(PlanError, "INVALID_REASON"):
                graph.propose_edge(Relation("A", "C", "similar_to"), reason=reason)
        with self.assertRaisesRegex(PlanError, "INVALID_REASON"):
            graph.rollback(1, reason="", permissions={"graph.edit"})

    def test_symmetric_normalization_and_duplicate(self):
        for kind in ("similar_to", "composes_with", "conflicts_with"):
            with self.subTest(kind=kind):
                graph = self.graph()
                proposal = graph.propose_edge(Relation("B", "A", kind, 2.5), reason="observed")
                self.assertEqual(proposal["would"]["source"], "A")
                self.assertEqual(graph.edges, ())
                self.apply(graph, proposal)
                self.assertEqual(graph.edges, (Relation("A", "B", kind, 2.5),))
                with self.assertRaisesRegex(PlanError, "EDGE_ALREADY_EXISTS"):
                    graph.propose_edge(Relation("B", "A", kind), reason="duplicate")
                self.assertEqual(graph.edits[-1]["reason"], "observed")

    def test_check_redundant_and_repair_suggestions(self):
        graph = self.graph(Relation("A", "B", "similar_to"), Relation("C", "D", "specializes"),
                           Relation("A", "E", "depends_on"), Relation("A", "F", "conflicts_with"))
        selected = ["A", "B", "C", "D", "F"]
        report = graph.check_set(selected)
        self.assertEqual({r["reason"] for r in report["redundant"]}, {"similar_to", "specializes"})
        self.assertEqual(report["missing_deps"], ["E"])
        self.assertEqual(graph.repair_set(selected)["suggestions"], {"add": ["E"], "remove": ["B", "D", "F"]})
        self.assertEqual(check_skills(graph, selected)["redundant"], report["redundant"])

    def test_search_bm25_and_upstream_bfs_both_directions(self):
        graph = self.graph(Relation("B", "A", "depends_on"), Relation("B", "C", "specializes"),
                           Relation("A", "D", "similar_to"), Relation("C", "D", "composes_with"),
                           Relation("C", "E", "similar_to"), Relation("A", "F", "conflicts_with"),
                           Relation("F", "G", "depends_on"))
        # No network/embedding hook can be invoked by this search.
        with patch.object(backend(), "_load_or_build_node_embeddings", side_effect=AssertionError("embedding")):
            result = graph.search("needle", top_k=1)
        self.assertEqual(set(result), {"matches", "neighbors", "conflicts"})
        self.assertEqual([m["skill_id"] for m in result["matches"]], ["A"])
        self.assertAlmostEqual(result["matches"][0]["score"], math.log(1 + 6.5 / 1.5))
        self.assertEqual([(r["skill_id"], r["depth"]) for r in result["neighbors"]], [("B", 1), ("D", 1), ("C", 2)])
        self.assertEqual(result["conflicts"][0]["skill_id"], "F")
        self.assertTrue(all("score" not in r for r in result["neighbors"] + result["conflicts"]))
        self.assertEqual(graph.search("needle", 1, depth=0)["neighbors"], [])
        self.assertIn("E", [r["skill_id"] for r in graph.search("needle", 1, depth=3)["neighbors"]])
        self.assertEqual(graph.search("", 1)["matches"], [])

    def test_delegated_dependencies_conflicts_and_expand(self):
        graph = self.graph(Relation("A", "B", "depends_on"), Relation("B", "C", "composes_with"),
                           Relation("A", "D", "conflicts_with"))
        # composes_with is soft: it must never become a hard prerequisite.
        self.assertEqual(graph.dependencies("A"), {"B"})
        self.assertEqual(GraphRegistry().gs.dependencies("SK04"), set())
        self.assertEqual(graph.get_dependencies("A", transitive=False)["dependencies"], [{"target": "B", "type": "depends_on"}])
        self.assertEqual(graph.expand_set(["A"])["expanded"], ["A", "B"])
        self.assertTrue(graph.conflicts({"D"}, {"A"}))
        self.assertEqual(graph.get_conflicts("A")["conflicts"][0]["target"], "D")

    def test_remove_retype_rollback_and_outer_guards(self):
        graph = self.graph()
        self.apply(graph, graph.propose_edge(Relation("B", "A", "similar_to"), reason="add"))
        proposal = graph.propose_retype_edge("B", "A", "similar_to", "conflicts_with", reason="new evidence")
        before = copy.deepcopy((graph.edges, graph.history, graph.edits))
        with self.assertRaisesRegex(PlanError, "graph_edit_permission"):
            graph.apply(proposal)
        self.assertEqual((graph.edges, graph.history, graph.edits), before)
        self.apply(graph, proposal)
        with self.assertRaisesRegex(PlanError, "graph_version_conflict"):
            self.apply(graph, proposal)
        self.assertEqual(graph.edges[0].kind, "conflicts_with")
        graph.rollback(2, permissions={"graph.edit"}, reason="undo retype")
        self.assertEqual(graph.edges[0].kind, "similar_to")
        self.apply(graph, graph.propose_remove_edge("B", "A", "similar_to", reason="remove"))
        self.assertEqual(graph.edges, ())
        graph.rollback(permissions={"graph.edit"}, reason="restore")
        self.assertEqual(graph.edges[0].kind, "similar_to")
        self.assertEqual(graph.version, 6)

    def test_version_rollback_can_reverse_a_prior_rollback(self):
        graph = self.graph()
        self.apply(graph, graph.propose_edge(Relation("A", "B", "similar_to", 2.5), reason="first"))
        self.apply(graph, graph.propose_edge(Relation("C", "D", "similar_to"), reason="second"))
        graph.rollback(1, permissions={"graph.edit"}, reason="undo both")
        self.assertEqual(graph.edges, ())
        graph.rollback(3, permissions={"graph.edit"}, reason="restore before rollback")
        self.assertEqual(graph.edges, graph.history[3])
        graph.rollback(2, permissions={"graph.edit"}, reason="restore first only")
        self.assertEqual(graph.edges, graph.history[2])
        self.assertEqual(graph.edges[0].weight, 2.5)

    def test_only_save_and_vector_scoring_are_overridden(self):
        original, memory = backend(), memory_backend()
        self.assertTrue(issubclass(memory, original))
        for method in ("search", "_collect_neighbors", "_collect_conflicts", "propose_edge",
                       "propose_remove_edge", "propose_retype_edge", "edit_edge", "rollback",
                       "get_dependencies", "get_conflicts", "expand_set", "check_set", "repair_set"):
            self.assertIs(getattr(memory, method), getattr(original, method))

    def test_task_rollback_and_retype_dry_run(self):
        graph = self.graph()
        graph.edit_edge("add", source="A", target="B", edge_type="depends_on", reason="one",
                        task_id="task1", permissions={"graph.edit"}, base_version=1)
        graph.edit_edge("add", source="C", target="D", edge_type="specializes", reason="two",
                        task_id="task2", permissions={"graph.edit"}, base_version=2)
        before = copy.deepcopy((graph.edges, graph.history, graph.edits))
        proposal = graph.propose_retype_edge("A", "B", "depends_on", "similar_to", reason="preview")
        self.assertEqual(proposal["related"][1]["reason"], "one")
        self.assertEqual((graph.edges, graph.history, graph.edits), before)
        graph.rollback(task_id="task1", permissions={"graph.edit"}, reason="task undo")
        self.assertEqual(graph.edges, (Relation("C", "D", "specializes"),))
        with self.assertRaisesRegex(PlanError, "EDGE_NOT_FOUND"):
            graph.propose_remove_edge("A", "B", "depends_on", reason="missing")

    def test_retype_keeps_requested_direction_and_weight(self):
        graph = self.graph(Relation("A", "B", "similar_to", 2.5))
        proposal = graph.propose_retype_edge("B", "A", "similar_to", "depends_on", reason="directional evidence")
        self.apply(graph, proposal)
        self.assertEqual(graph.edges, (Relation("B", "A", "depends_on", 2.5),))
        graph.rollback(1, permissions={"graph.edit"}, reason="restore symmetric")
        self.assertEqual(graph.edges, (Relation("A", "B", "similar_to", 2.5),))

    def test_edit_and_rollback_do_not_write_third_party(self):
        # Upstream save() writes next to its graph_path, i.e. inside the SkillDAG checkout.
        directory = ROOT / "third_party" / "SkillDAG"
        before = {p.relative_to(directory): (p.stat().st_size, p.stat().st_mtime_ns)
                  for p in directory.rglob("*") if p.is_file()}
        graph = self.graph()
        graph.edit_edge("add", source="A", target="B", edge_type="depends_on", reason="evidence",
                        permissions={"graph.edit"}, base_version=1)
        graph.rollback(1, permissions={"graph.edit"}, reason="undo")
        after = {p.relative_to(directory): (p.stat().st_size, p.stat().st_mtime_ns)
                 for p in directory.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(graph.edges, ())

    def test_extension_relations_remain_in_ppr_and_out_of_skilldag(self):
        data = read_json(ROOT / "data/registry_v01.json")
        for kind in ("alternative_to", "produces_for", "workflow"):
            data["extension_relations"].append({"source": "SK05", "target": "SK04", "type": kind,
                                                 "weight": 2.5, "origin": "test", "reason": "extension"})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "registry.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            registry = GraphRegistry.from_v01(path)
        check_skills(registry.gs, ["SK05", "SK04"])
        state = CaseState({"target": {}, "capabilities": list(registry.functions),
                           "permissions": ["network.read", "system.read"]}, registry)
        result = registry.retrieve("DNS WAN", [], state, k=4)
        for projected in ("alternative", "dependency", "workflow"):
            self.assertIn(("s:SK05", "s:SK04", projected, 2.5), result["edges"])
        legacy = GraphRegistry()
        legacy.relations += [Relation("SK05", "SK04", "alternative_to")]
        legacy.rebuild()
        check_skills(legacy.gs, ["SK05"])


if __name__ == "__main__":
    unittest.main()
