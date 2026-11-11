"""C3: grounded Answer Composer, grounding per turn type, LLM post-check."""
import json
import re
import unittest

from gateway_pilot.answer import NO_GROUNDING_NOTE, check_llm_text
from gateway_pilot.assistant import answer
from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.workflow import replay_from_fixture

FIELDS = {"turn_type", "answer", "grounding", "case_status", "evidence_ids", "doc_ids", "options",
          "next_steps", "route", "contracts", "llm_used"}
NUMBER = re.compile(r"(?<![A-Za-z0-9-])-?\d+(?:[.,]\d+)?")  # SK22-style identifiers are not numbers


class AnswerC3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = GraphRegistry.from_v01()
        fixture = next(c for c in read_json(ROOT / "data/cases.json") if c["id"] == "GLM-21-1")
        cls.replay = replay_from_fixture(fixture, cls.registry)
        cls.dev = read_json(ROOT / "benchmarks/router_dev_v0.json")
        cls.dev = cls.dev["cases"]
        cls.dev_results = [(row, answer(row["text"] if "text" in row else row["message"], cls.replay,
                                        registry=cls.registry)) for row in cls.dev]

    def ask(self, message, **kwargs):
        return answer(message, self.replay, registry=self.registry, **kwargs)

    def test_every_turn_has_the_c3_structure(self):
        for row, result in self.dev_results:
            with self.subTest(row=row.get("text", row.get("message"))):
                self.assertLessEqual(FIELDS, set(result))
                self.assertIn(result["grounding"], {"EVIDENCE", "DOCS", "CATALOG", "NONE"})
                self.assertEqual(set(result["contracts"]), {"c0", "a", "c"})
                self.assertFalse(result["llm_used"])

    def test_grounding_matches_turn_type(self):
        expected = {
            "laptop-an vẫn có Wi-Fi mà không vào được mạng": ("DIAGNOSE", "EVIDENCE"),
            "router còn bao nhiêu RAM trống": ("LOOKUP", "EVIDENCE"),
            "DHCP là gì": ("KNOWLEDGE", "DOCS"),
            "cách đổi kênh wifi": ("KNOWLEDGE", "NONE"),
            "bạn làm được những gì": ("CAPABILITY", "CATALOG"),
            "tín hiệu quang ONT báo đỏ LOS": ("DIAGNOSE", "CATALOG"),
            "đổi DNS sang 8.8.8.8": ("CHANGE", "NONE"),
            "chào bạn": ("SMALLTALK", "NONE"),
            "thời tiết Hà Nội hôm nay thế nào": (None, None),
        }
        for message, (kind, grounding) in expected.items():
            with self.subTest(message):
                result = self.ask(message)
                if kind is None:
                    continue  # router quality, not composer (see board issue #13)
                self.assertEqual((result["turn_type"], result["grounding"]), (kind, grounding))
        knowledge = self.ask("DHCP là gì")
        self.assertEqual(knowledge["doc_ids"], ["dhcp-lease"])
        diagnose = self.ask("laptop-an vẫn có Wi-Fi mà không vào được mạng")
        self.assertTrue(diagnose["evidence_ids"])
        self.assertIn("đo tại router", diagnose["answer"])
        self.assertTrue(diagnose["contracts"]["c"]["facts"])
        self.assertTrue(diagnose["contracts"]["a"])

    def test_knowledge_without_documents_lists_nearest_topics(self):
        result = self.ask("cách đổi kênh wifi")
        self.assertIn("Chưa có tài liệu", result["answer"])
        self.assertIn("Chủ đề gần nhất", result["answer"])
        self.assertEqual((result["doc_ids"], result["grounding"]), ([], "NONE"))

    def test_partial_always_names_what_was_not_verified(self):
        partial = [result for _, result in self.dev_results if result["case_status"] == "PARTIAL"]
        partial.append(self.ask("laptop-an vẫn có Wi-Fi mà không vào được mạng"))
        self.assertTrue(partial)
        for result in partial:
            with self.subTest(result["answer"][:60]):
                self.assertIn("Chưa xác minh", result["answer"])
                self.assertTrue(result["next_steps"])

    def test_numbers_only_come_from_the_question_evidence_or_documents(self):
        for row, result in self.dev_results:
            message = row.get("text", row.get("message"))
            allowed = json.dumps([message, result.get("graph", {}).get("evidence", []),
                                  result.get("router", {}).get("documents", [])], ensure_ascii=False)
            allowed_numbers = set(NUMBER.findall(allowed))
            # The ISO time stamp of evidence is printed as part of each fact line.
            stamp = {n for e in result.get("graph", {}).get("evidence", []) for n in NUMBER.findall(e.get("observed_at", ""))}
            with self.subTest(message):
                self.assertLessEqual(set(NUMBER.findall(result["answer"])), allowed_numbers | stamp)

    def test_llm_text_with_an_unseen_number_is_rejected(self):
        def llm(payload):
            return "Router mất 37% gói tin."  # 37 is in no fact

        result = self.ask("laptop-an vẫn có Wi-Fi mà không vào được mạng", llm=llm)
        self.assertFalse(result["llm_used"])
        self.assertTrue(result["llm_rejected"].startswith("number_not_in_input"))
        self.assertNotIn("37", result["answer"])
        self.assertIn("Chưa xác minh", result["answer"])

    def test_llm_text_with_an_unseen_diagnosis_code_is_rejected(self):
        for text in ("Kết luận: wan_link_down.", "Theo quy trình WF-077, cần kiểm quang."):
            result = self.ask("laptop-an vẫn có Wi-Fi mà không vào được mạng", llm=lambda payload, text=text: text)
            self.assertFalse(result["llm_used"])
            self.assertTrue(result["llm_rejected"].startswith("code_not_in_input"))

    def test_grounded_llm_rephrase_is_used_and_keeps_the_unverified_note(self):
        def llm(payload):
            loss = next(f["value"]["loss_pct"] for f in payload["facts"] if f["port"] == "wan.probe")
            return f"Router ra Internet bình thường (mất {loss}% gói), DNS tại router trả NOERROR."

        result = self.ask("laptop-an vẫn có Wi-Fi mà không vào được mạng", llm=llm)
        self.assertTrue(result["llm_used"])
        self.assertTrue(result["answer"].startswith("Router ra Internet bình thường"))
        self.assertIn("Chưa xác minh", result["answer"])

    def test_ungrounded_llm_knowledge_answer_is_marked(self):
        result = self.ask("cách đổi kênh wifi", llm=lambda payload: "Vào trang quản trị Wi-Fi và chọn kênh khác.")
        self.assertTrue(result["llm_used"])
        self.assertEqual(result["grounding"], "NONE")
        self.assertIn(NO_GROUNDING_NOTE, result["answer"])

    def test_llm_failure_falls_back_to_template(self):
        def broken(payload):
            raise OSError("ollama down")

        result = self.ask("laptop-an vẫn có Wi-Fi mà không vào được mạng", llm=broken)
        self.assertFalse(result["llm_used"])
        self.assertEqual(result["llm_rejected"], "OSError")
        self.assertTrue(result["answer"].strip())
        self.assertEqual(check_llm_text("", {}), (False, "empty"))


if __name__ == "__main__":
    unittest.main()
