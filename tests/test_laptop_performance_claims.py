"""LAPTOP-PERFORMANCE Claims: thresholds, boundaries, missing/expired facts, rendering."""
import json
import unittest
from pathlib import Path

from gateway_pilot.application.grounded_answer import CLAIM_MESSAGES, assessment_summary
from gateway_pilot.graph_v3.claims import ClaimBook

DIAG = json.loads((Path(__file__).resolve().parents[1]
                   / 'config/skill_launcher/live.diagnostics.json').read_text(encoding='utf-8'))
WF = 'LAPTOP-PERFORMANCE'
PORTS = {'laptop.wifi', 'laptop.gateway_probe', 'laptop.internet_probe'}


class View:
    """Facts present in the view; an absent port models missing or expired evidence."""
    def __init__(self, **values):
        self.facts = {p: {'id': 'ev-' + p, 'value': v} for p, v in values.items()}

    def fact(self, port):
        return self.facts.get(port)


def facts(signal=80.0, gw=2.0, gw_loss=0.0, inet=20.0, inet_loss=0.0):
    return {'laptop.wifi': {'signal_pct': signal},
            'laptop.gateway_probe': {'latency_ms': gw, 'loss_pct': gw_loss},
            'laptop.internet_probe': {'latency_ms': inet, 'loss_pct': inet_loss}}


def true_claims(**values):
    book = ClaimBook([c for c in DIAG['claims'] if c['workflow'] == WF], PORTS,
                     {WF: DIAG['workflows'][WF]})
    result = book.evaluate_all(View(**values), WF)
    return {cid for cid, r in result.items() if r['value'] == 'TRUE'}, result


class PerformanceClaimTests(unittest.TestCase):
    def test_wired_into_network_inspect_only_with_messages(self):
        self.assertIn(WF, DIAG['skill_workflows']['laptop.network.inspect'])
        for cid in DIAG['workflows'][WF]['claims']:
            self.assertIn(cid, CLAIM_MESSAGES)

    def test_normal_path_is_healthy_only(self):
        ids, _ = true_claims(**facts())
        self.assertEqual(ids, {'performance_path_normal'})

    def test_each_fault_threshold_and_boundary(self):
        cases = [({'signal': 39.9}, 'wifi_signal_weak'), ({'gw': 20.01}, 'gateway_latency_high'),
                 ({'inet': 100.5}, 'internet_latency_high')]
        for override, fault in cases:
            ids, _ = true_claims(**facts(**override))
            self.assertEqual(ids, {fault}, override)
        # Exactly on the threshold is still normal (lt 40 / gt 20 / gt 100).
        ids, _ = true_claims(**facts(signal=40.0, gw=20.0, inet=100.0))
        self.assertEqual(ids, {'performance_path_normal'})

    def test_loss_blocks_healthy_without_new_fault(self):
        ids, _ = true_claims(**facts(inet_loss=25.0))
        self.assertNotIn('performance_path_normal', ids)

    def test_missing_or_expired_source_is_unknown_not_healthy(self):
        values = facts()
        del values['laptop.internet_probe']
        ids, result = true_claims(**values)
        self.assertNotIn('performance_path_normal', ids)
        self.assertEqual(result['performance_path_normal']['value'], 'UNKNOWN')
        self.assertEqual(result['internet_latency_high']['value'], 'UNKNOWN')

    def test_malformed_values_never_support_a_claim(self):
        ids, _ = true_claims(**facts(signal='weak', gw=True, inet=None))
        self.assertEqual(ids, set())


class SummaryRenderingTests(unittest.TestCase):
    def assessments(self, *rows):
        return [{'claim_results': [dict(truth='TRUE', diagnosis=d, severity=s, evidence_ids=e)
                                   for d, s, e in rows]}]

    def test_fault_lines_are_specific(self):
        text = assessment_summary({'laptop.wifi': {'evidence_id': 'e1'}},
                                  self.assessments(('wifi_signal_weak', 'FAULT', ['e1'])))
        self.assertIn('bất thường', text)
        self.assertIn('Tín hiệu Wi-Fi yếu', text)

    def test_stale_evidence_is_not_rendered(self):
        text = assessment_summary({'laptop.wifi': {'evidence_id': 'fresh'}},
                                  self.assessments(('wifi_signal_weak', 'FAULT', ['old'])))
        self.assertEqual(text, '')

    def test_healthy_hint_is_marked_as_not_a_cause(self):
        text = assessment_summary({'p': {'evidence_id': 'e'}},
                                  self.assessments(('performance_path_normal', 'HEALTHY', ['e'])))
        self.assertIn('không có dấu hiệu chậm', text)
        self.assertIn('chưa phải nguyên nhân đã xác minh', text)


if __name__ == '__main__':
    unittest.main()
