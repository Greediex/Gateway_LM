"""Topic routing and concise answers through the existing READ Core."""
import unittest
from unittest.mock import patch

from gateway_pilot.adapters.read_backends import observations
from gateway_pilot.application.skill_chat import SkillChat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.skill_expansion.deployment import composition
from tests.test_skill_chat_p0 import FullLaptopBackend


class ConciseAnswerTests(unittest.TestCase):
    def setUp(self):
        self.backend = FullLaptopBackend()
        self.launcher = SkillLauncher(
            factory=lambda mode: composition(mode, backend=self.backend, clock=lambda: 100.),
            clock=lambda: 100.,
        )
        self.chat = SkillChat(self.launcher, fast=True, clock=lambda: 100.,
                              model_factory=lambda: self.fail('A scoped or baseline route needs no model'))

    def assert_only_topic(self, result, port, dependencies):
        self.assertEqual(result['coverage']['requested_ports'], [port])
        self.assertEqual(result['coverage']['satisfied_ports'], [port])
        self.assertEqual([p for plan in result['plans'] for p in plan['goals']], [port])
        self.assertEqual({row['function_id'] for row in result['timeline']}, {port, *dependencies})
        self.assertEqual(result['evidence_ids'], [result['snapshot']['facts'][port]['evidence_id']])
        self.assertEqual((result['case_status'], result['model_calls']), ('MEASURED', 0))
        self.assertLessEqual(len(result['answer'].splitlines()), 5)

    def test_wan_health_phrase_measures_only_internet_and_states_router_scope(self):
        result = self.chat.chat('thông tin mạng wan')
        self.assert_only_topic(result, 'laptop.internet_probe', {'clients.resolve', 'laptop.route'})
        answer = result['answer']
        self.assertRegex(answer.splitlines()[0], r'^WAN của router.*quyền đọc router.*chế độ laptop')
        for measurement in ('1.1.1.1', '4/4 gói ICMP', 'mất 0%', 'độ trễ 2 ms'):
            self.assertIn(measurement, answer)
        for unrelated in ('Wi-Fi', 'DNS', 'Gateway:', 'định danh', 'BSSID'):
            self.assertNotIn(unrelated, answer)

    def test_wifi_health_phrase_does_not_run_optional_route_or_other_probes(self):
        result = self.chat.chat('wifi có ổn không')
        self.assert_only_topic(result, 'laptop.wifi', {'clients.resolve'})
        self.assertIn('Tín hiệu Wi-Fi hiện tại: 70%', result['answer'])
        for unrelated in ('DNS', 'Gateway', 'Internet', 'định danh', 'BSSID'):
            self.assertNotIn(unrelated, result['answer'])

    def test_general_health_still_measures_the_full_baseline(self):
        for question in ('mạng có ổn không', 'thông tin mạng'):
            with self.subTest(question=question):
                result = self.chat.chat(question)
                self.assertEqual(result['routing']['method'], 'symptom_baseline')
                self.assertEqual(set(result['coverage']['satisfied_ports']), {
                    'laptop.wifi', 'laptop.route', 'laptop.gateway_probe', 'laptop.internet_probe',
                    'laptop.dns', 'client.ipv4', 'client.identity', 'expansion.client_association',
                })
                self.assertEqual((result['case_status'], result['calls'], result['model_calls']),
                                 ('MEASURED', 8, 0))
                self.assertLessEqual(len(result['answer'].splitlines()), 5)
                for measurement in ('Wi-Fi', 'Gateway', 'IP Internet', 'DNS'):
                    self.assertIn(measurement, result['answer'])
                for unrelated in ('định danh', 'BSSID', '02:00:00:00:00:01'):
                    self.assertNotIn(unrelated, result['answer'])

    def test_fixed_caveats_are_in_details_for_a_successful_wan_probe(self):
        result = self.chat.chat('thông tin mạng wan')
        self.assertEqual(len(result['caveats']), 3)
        for note, prefix in zip(result['caveats'], ('ICMP/DNS', 'Chưa đủ bằng chứng', 'Bước tiếp theo')):
            self.assertTrue(note.startswith(prefix))
            self.assertNotIn(prefix, result['answer'])
        self.assertNotIn('Trong phạm vi laptop này:', result['answer'])

    def test_wan_ignores_out_of_scope_claims_cached_by_a_general_turn(self):
        wifi = self.backend.wifi
        internet_sample = self.backend.sample

        def sample(function, arguments, context):
            if function['function_id'] != 'laptop.internet_probe':
                return internet_sample(function, arguments, context)
            value = dict(destination='1.1.1.1', interface='wifi0', sent=4, received=3,
                         loss_pct=25, latency_ms=120)
            return observations(function, {'laptop.internet_probe': value}, self.backend.source, context)

        with patch.object(self.backend, 'wifi', side_effect=lambda: {**wifi(), 'signal_pct': 20}), \
                patch.object(self.backend, 'sample', side_effect=sample):
            general = self.chat.chat('mạng có ổn không')
            self.assertTrue(any('Tín hiệu Wi-Fi yếu' in line for line in general['claim_details']))
            result = self.chat.chat('thông tin mạng wan', session_id=general['session_id'])
        self.assertEqual(result['calls'], 0)
        self.assertIn('bất thường', result['answer'])
        self.assertIn('mất 25%', result['answer'])
        self.assertIn('Có mất gói tới IP Internet kiểm tra.', result['claim_details'])
        self.assertTrue(any('Độ trễ ra Internet cao' in line for line in result['claim_details']))
        self.assertFalse(any('Wi-Fi' in line for line in result['claim_details']))
        self.assertEqual([a['workflow'] for a in result['rca_assessments']], ['LAPTOP-INTERNET'])
        self.assertIsNone(result['diagnosis'])

    def test_unavailable_wan_probe_does_not_fall_back_to_other_topics(self):
        self.backend._tools.pop('ping')
        result = self.chat.chat('thông tin mạng wan')
        self.assertEqual(result['coverage']['missing_ports'], ['laptop.internet_probe'])
        self.assertEqual((result['calls'], result['model_calls']), (0, 0))
        self.assertIn('quyền đọc router', result['answer'])
        self.assertNotIn('4/4', result['answer'])

    def test_router_or_write_target_guards_still_precede_topic_routing(self):
        for question in ('DNS của router', 'DNS của modem', 'WAN router ping 203.0.113.4',
                         'khởi động lại router'):
            with self.subTest(question=question):
                result = self.chat.chat(question)
                self.assertIn(result['case_status'], ('NEEDS_INPUT', 'BLOCKED'))
                self.assertEqual((result['calls'], result['model_calls']), (0, 0))

    def test_wan_timeout_keeps_only_verified_dependencies_as_evidence(self):
        self.backend.fail.add('laptop.internet_probe')
        result = self.chat.chat('thông tin mạng wan')
        self.assertEqual(result['coverage']['missing_ports'], ['laptop.internet_probe'])
        self.assertEqual(result['evidence_ids'], [])
        self.assertEqual(result['claim_details'], [])
        self.assertEqual({e['port'] for e in result['evidence']}, {'client.identity', 'laptop.route'})
        self.assertEqual(result['model_calls'], 0)

    def test_topic_aliases_are_scoped_even_with_general_health_words(self):
        for question, ports in (
            ('Tình trạng nhà mạng', {'laptop.internet_probe'}),
            ('Thông tin tên miền', {'laptop.dns'}),
            ('Tình trạng modem', {'laptop.gateway_probe', 'laptop.route'}),
            ('Thông tin địa chỉ IP laptop', {'client.ipv4'}),
        ):
            with self.subTest(question=question):
                result = self.chat.chat(question)
                self.assertEqual(set(result['coverage']['satisfied_ports']), ports)
                self.assertEqual(set(result['coverage']['requested_ports']), ports)
                self.assertEqual(result['routing']['method'], 'phrase')
