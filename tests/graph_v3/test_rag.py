import json
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.context import retrieve_context
from gateway_pilot.graph_v3.graphs import Relation, SkillGraph
from gateway_pilot.graph_v3.skilldag import check_skills
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.graph_v3.upstream import _cached_transition, rank
from gateway_pilot.rag import DEFAULT_CATALOG, REPLAY_FIRMWARE, REPLAY_PRODUCT, RunbookIndex, explain, json_bytes
from gateway_pilot.workflow import diagnose, replay_from_fixture, workflow_registry


class RagTests(unittest.TestCase):
    def setUp(self):
        self.index = RunbookIndex()

    def retrieve(self, query, **options):
        args = {"product": REPLAY_PRODUCT, "firmware": REPLAY_FIRMWARE, "permissions": {"docs.read"}}
        return self.index.retrieve(query, **{**args, **options})

    def test_retrieves_vietnamese_without_diacritics_and_abstains_off_topic(self):
        result = self.retrieve("thiet bi khong duoc cap ip DHCP pool")
        self.assertEqual(result["documents"][0]["id"], "dhcp-lease")
        self.assertEqual(self.retrieve("chứng khoán trái phiếu cổ tức")["reason"], "no_matching_runbook")
        self.assertEqual(self.retrieve("SERVFAIL")["documents"][0]["id"], "dns-scope")

    def test_hard_filters_docs_permission_and_exact_firmware(self):
        for options, reason in (({"permissions": set()}, "docs_read_denied"),
                                ({"firmware": "other"}, "no_exact_firmware_profile")):
            result = self.retrieve("DNS resolver", **options)
            self.assertEqual(result["reason"], reason)
            self.assertEqual(result["documents"], [])
            self.assertNotIn("source", result)

    def test_graph_adds_only_prerequisites_of_primary_runbook(self):
        result = self.retrieve("Laptop An vẫn có Wi-Fi, sao không truy cập Internet?", method="gos")
        self.assertEqual([row["id"] for row in result["documents"]], ["wifi-internet", "wan-route"])

    def test_wrong_firmware_high_lexical_match_never_leaks(self):
        rows = read_json(DEFAULT_CATALOG)
        rows.append({**rows[0], "id": "wrong-build", "firmware": "different-version", "requires": [],
                     "title": "zebraorbital exactphrase", "keywords": "zebraorbital exactphrase"})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(rows), encoding="utf-8")
            result = RunbookIndex(path).retrieve("zebraorbital exactphrase", product=REPLAY_PRODUCT,
                                                 firmware=REPLAY_FIRMWARE, permissions={"docs.read"})
        self.assertEqual(result["reason"], "no_matching_runbook")

    def test_context_is_measured_on_actual_serialized_utf8(self):
        result = self.retrieve("DNS SERVFAIL", max_bytes=600)
        self.assertEqual(result["context_bytes"], json_bytes(result["documents"]))
        self.assertLessEqual(result["context_bytes"], 600)
        self.assertEqual(self.retrieve("DNS SERVFAIL", max_bytes=2)["reason"], "context_budget")

    def test_doc_only_and_diagnosis_do_not_mix_provenance(self):
        guide = self.retrieve("máy có wifi nhưng không mở được trang web")
        self.assertIsNone(explain(guide)["measurement"])
        case = next(row for row in read_json(ROOT / "data" / "cases.json") if row["id"] == "GLM-21-1")
        registry = workflow_registry()
        result = diagnose(case["request"], replay_from_fixture(case, registry), registry=registry)
        report = explain(guide, result)
        self.assertEqual(report["measurement"]["evidence_ids"], result["terminal"]["evidence_ids"])
        self.assertTrue({doc["id"] for doc in guide["documents"]}.isdisjoint(report["measurement"]["evidence_ids"]))

    def test_skilldag_expands_hard_dependencies_and_checks_conflicts(self):
        skills = {name: {"name": name} for name in ("s1", "s2", "s3")}
        graph = SkillGraph(skills, [Relation("s1", "s2", "depends_on"),
                                    Relation("s2", "s3", "conflicts_with")])
        result = check_skills(graph, ("s1", "s3"))
        self.assertEqual(result["prerequisites"], ["s2"])
        self.assertEqual(result["conflicts"][0]["target"], "s3")

    def test_skill_bundles_include_typed_prerequisites_and_exclude_writes(self):
        registry = workflow_registry()
        state = CaseState({"target": {"scope": "gateway", "id": "gateway_01"},
                           "capabilities": ["dns.probe", "dns.config", "dns.apply"]}, registry)
        result = retrieve_context(registry, state, "DNS resolver query", ["dns.probe"], k=2)
        bundle = next(item for item in result["bundles"] if item["root"] == "dns.probe")
        self.assertEqual([row["id"] for row in bundle["functions"]], ["dns.config", "dns.probe"])
        self.assertTrue(all(row["id"] != "dns.apply" for item in result["bundles"] for row in item["functions"]))
        self.assertEqual(retrieve_context(registry, state, "DNS", ["dns.probe"], max_bytes=2)["bundles"], [])

    def test_ppr_cache_reuses_transition_with_different_seed_vectors(self):
        _cached_transition.cache_clear()
        names, edges = ["p", "c"], [("p", "c", "dependency", 1)]
        first = rank(names, edges, {"p": 1})
        second = rank(names, edges, {"c": 1})
        self.assertNotEqual(first, second)
        self.assertEqual(_cached_transition.cache_info().hits, 1)
        _cached_transition.cache_clear()
        self.assertEqual(second, rank(names, edges, {"c": 1}))


if __name__ == "__main__":
    unittest.main()
