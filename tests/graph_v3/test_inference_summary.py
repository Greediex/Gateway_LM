"""Independent inference log validator (synthetic contract tests only)."""
from __future__ import annotations

import copy
import unittest

from scripts.hardware.summarize_inference import summarize


class InferenceSummaryTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{
            "sample_id": str(i),
            "model_sha256": "a"*64, "backend": "qnn_htp",
            "input_tokens": 150, "output_tokens": 32,
            "ttft_ms": 260, "total_ms": 1600 + i*100,
            "rss_peak_bytes": 200_000_000,
        } for i in range(1, 6)]
        self.host = {
            "platform": "generic_linux_host",
            "device_acceptance_possible": False,
            "metrics": {"npu_util_percent": {"mean": None}},
        }

    def test_host_and_unverified_npu_do_not_count_as_board_acceptance(self):
        result = summarize(self.rows, self.host)
        self.assertEqual(result["samples"], 5)
        self.assertEqual(result["backend"], "qnn_htp")
        self.assertFalse(result["eligible_for_independent_device_review"])
        self.assertEqual(result["acceptance_status"], "NOT_DEVICE_VALIDATED")
        self.assertGreater(result["total_ms_p95"], result["total_ms_p50"])

    def test_on_device_npu_counter_still_requires_manual_attestation(self):
        board = copy.deepcopy(self.host)
        board["platform"] = "openwrt"
        board["device_acceptance_possible"] = True
        board["metrics"]["npu_util_percent"]["mean"] = 82.1
        result = summarize(self.rows, board)
        self.assertTrue(result["eligible_for_independent_device_review"])
        self.assertEqual(
            result["acceptance_status"],
            "REQUIRES_MANUAL_BOARD_ATTESTATION_AND_THRESHOLDS",
        )

    def test_bad_npu_logging_or_mixed_model_is_rejected(self):
        bad = copy.deepcopy(self.rows)
        bad[0]["backend"] = "cpu"
        with self.assertRaisesRegex(ValueError, "mixed"):
            summarize(bad, self.host)
        bad = copy.deepcopy(self.rows)
        bad[0]["total_ms"] = 50
        with self.assertRaisesRegex(ValueError, "invalid_inference_time"):
            summarize(bad, self.host)
        bad = copy.deepcopy(self.rows)
        bad[0]["sample_id"] = bad[1]["sample_id"]
        with self.assertRaisesRegex(ValueError, "invalid_inference_metadata"):
            summarize(bad, self.host)
        bad = copy.deepcopy(self.rows)
        bad[0]["ttft_ms"] = float("nan")
        with self.assertRaisesRegex(ValueError, "invalid_inference_time"):
            summarize(bad, self.host)


if __name__ == "__main__":
    unittest.main()
