"""Skill graph for the web view: exact 120 Skills, no dangling edges, counts from coverage."""
import json
import unittest
from http import HTTPStatus
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock, patch

from gateway_pilot.skill_expansion import coverage
from gateway_pilot.skill_expansion.coverage import CoverageError, build_coverage, skill_graph
from web_gateway.server import Handler


class SkillGraphTests(unittest.TestCase):
    def test_graph_matches_coverage_and_has_no_dangling_edges(self):
        g = skill_graph()
        skills = [x for x in g["nodes"] if x["kind"] == "skill"]
        self.assertEqual(len(skills), 120)
        ids = {x["id"] for x in g["nodes"]}
        self.assertEqual(len(ids), len(g["nodes"]))
        for e in g["edges"]:
            self.assertIn(e["source"], ids)
            self.assertIn(e["target"], ids)
        rows = build_coverage()
        self.assertEqual(sum(x["verified"] for x in skills), sum(r.simulation_verified for r in rows))
        self.assertEqual(sum(x["chat_callable"] for x in skills),
                         sum(r.replay_launchable or r.live_launchable for r in rows))
        by_id = {x["id"]: x for x in skills}
        self.assertEqual({r.domain for r in rows}, set(g["groups"]))
        for row in rows:
            with self.subTest(skill=row.skill_id):
                self.assertEqual(by_id[row.skill_id]["verified"], row.simulation_verified)
                self.assertEqual(by_id[row.skill_id]["chat_callable"],
                                 row.replay_launchable or row.live_launchable)

    def test_composite_sources_are_edges(self):
        edges = {(e["source"], e["target"]) for e in skill_graph()["edges"]}
        composite = {s for s, _ in edges if s in ("A03", "D04", "SK02", "K01")}
        self.assertEqual(composite, {"A03", "D04", "SK02", "K01"})
        self.assertIn(("A03", "expansion.identity_consistency"), edges)
        self.assertIn(("A03", "expansion.device_inventory"), edges)

    def test_graph_checks_pinned_action_metadata_without_building_registry(self):
        from gateway_pilot.command_catalog.loader import read_json

        with patch("gateway_pilot.skill_expansion.deployment.deployment") as deployment:
            skill_graph()
        deployment.assert_not_called()

        def drift(path):
            doc = read_json(path)
            if path.name == "live.actions.json":
                doc["actions"].pop()
            return doc

        with patch("gateway_pilot.command_catalog.loader.read_json", side_effect=drift):
            with self.assertRaisesRegex(CoverageError, "unapproved graph launch metadata"):
                skill_graph()


class SkillGraphHandlerTests(unittest.TestCase):
    def get_graph(self, host="localhost:8765"):
        handler = Handler.__new__(Handler)
        handler.server = SimpleNamespace(server_port=8765)
        handler.headers = {"Host": host}
        handler.path = "/api/graph"
        handler.wfile = BytesIO()
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.do_GET()
        return handler.send_response.call_args.args[0], json.loads(handler.wfile.getvalue())

    def test_get_graph_returns_catalog(self):
        status, graph = self.get_graph()
        self.assertEqual(status, HTTPStatus.OK)
        self.assertEqual(graph, skill_graph())

    def test_get_unavailable_graph_returns_503(self):
        for error in (CoverageError("stale acceptance"), FileNotFoundError("missing metadata"),
                      KeyError("invalid metadata"), TypeError("malformed metadata")):
            with self.subTest(error=type(error).__name__):
                with patch.object(coverage, "skill_graph", side_effect=error):
                    status, body = self.get_graph()
                self.assertEqual(status, HTTPStatus.SERVICE_UNAVAILABLE)
                self.assertEqual(body, {"error": "Skill graph unavailable"})

    def test_get_graph_rejects_foreign_host_before_loading_metadata(self):
        with patch.object(coverage, "skill_graph") as load:
            status, _ = self.get_graph("example.test:8765")
        self.assertEqual(status, HTTPStatus.FORBIDDEN)
        load.assert_not_called()


if __name__ == "__main__":
    unittest.main()
