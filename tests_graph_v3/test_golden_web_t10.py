"""T10: golden fixtures for the C++ port and the web Contracts view."""
import json
import sys
import unittest

from jsonschema import Draft202012Validator

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry

GOLDEN = ROOT / "docs/contracts/golden"
sys.path.insert(0, str(GOLDEN))
import build_golden  # noqa: E402


def schema(name):
    return Draft202012Validator(read_json(ROOT / f"docs/contracts/{name}.schema.json"))


class GoldenWebT10Tests(unittest.TestCase):
    def test_golden_fixtures_rebuild_byte_identical(self):
        registry = GraphRegistry.from_v01()
        fixtures = {c["id"]: c for c in read_json(ROOT / "data/cases.json")}
        self.assertGreaterEqual(len(build_golden.CASES), 5)
        for name in build_golden.CASES:
            with self.subTest(name):
                committed = (GOLDEN / f"{name}.json").read_text(encoding="utf-8")
                self.assertEqual(build_golden.golden(name, registry, fixtures), committed)

    def test_every_golden_contract_matches_its_schema(self):
        validators = {key: schema(name) for key, name in (("contract_0", "contract_0"), ("contract_a", "contract_a"),
                                                          ("contract_b", "contract_b"), ("contract_c", "contract_c"))}
        for path in sorted(GOLDEN.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(path.name):
                for key in ("contract_0", "contract_a", "contract_b"):
                    for item in document[key]:
                        self.assertFalse(list(validators[key].iter_errors(item)), (key, item))
                if document["contract_c"]:
                    self.assertFalse(list(validators["contract_c"].iter_errors(document["contract_c"])))
                    self.assertEqual(document["contract_c"]["decision"], document["case_status"])

    def test_web_response_carries_contracts_revisions_and_route(self):
        sys.path.insert(0, str(ROOT / "web_gateway"))
        try:
            import server
        finally:
            sys.path.remove(str(ROOT / "web_gateway"))
        response = server.analyze({"message": "Tại sao WAN mất mạng?", "fixture_id": "GLM-01-0", "method": "bm25"})
        self.assertEqual(set(response["contracts"]), {"c0", "a", "b", "c"})
        self.assertIn(response["route"], {"fastpath", "resolver"})
        self.assertTrue(response["revisions"])
        self.assertTrue(response["contracts"]["b"])
        app = (ROOT / "web_gateway/static/app.js").read_text(encoding="utf-8")
        page = (ROOT / "web_gateway/static/index.html").read_text(encoding="utf-8")
        self.assertIn('data-tab="contracts"', page)
        self.assertIn("function renderContracts", app)


if __name__ == "__main__":
    unittest.main()
