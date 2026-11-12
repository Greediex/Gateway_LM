"""GATEWAY_DESIGN: C1 catalog references, retrieval and passive design records."""
import copy
import hashlib
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler
from gateway_pilot.graph_v3.registry_v01 import load_registry
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.workflow import (CLIENT_WORDS, INTERNET_WORDS, TOPICS, HTML_WORKFLOW_IDS,
                                    MESSAGES, WORKFLOWS, diagnose, normalize,
                                    replay_from_fixture, workflow_registry)


class CatalogC1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = GraphRegistry.from_v01()

    def state(self, registry=None, **overrides):
        registry = registry or self.registry
        case = dict(target={}, capabilities=list(registry.functions))
        case.update(overrides)
        return CaseState(case, registry)

    def candidate(self, mutate):
        data = read_json(ROOT / 'data/registry_v01.json')
        mutate(data)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'registry.json'
            path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
            return load_registry(path)

    def test_supported_rank_first_without_old_regex_keywords(self):
        queries = {
            'WF-018': ['Mạng lag khi họp online', 'duong truyen ra ngoai bi ngat khi hop',
                       'External connection drops during online meetings',
                       'Đường truyền ra ngoài hay bị đứt giữa cuộc gọi'],
            'WF-023': ['Trang web không tải được', 'trang web bao loi khong tim thay ten',
                       'Cannot resolve website names', 'Gõ tên trang thì báo lỗi tra cứu'],
            'WF-024': ['Máy chờ nhận địa chỉ mãi', 'ket noi dung o buoc xin dia chi',
                       'Failing to allocate an address', 'Máy cứ chờ xin địa chỉ mãi không xong'],
            'WF-039': ['Bộ nhớ gần cạn và máy nóng', 'bo xu ly luon bi chiem dung',
                       'Memory exhaustion and high processor utilization', 'Máy nóng và bộ nhớ sắp cạn'],
            'WF-INTERNET': ['Máy không lên mạng dù vẫn bắt sóng', 'chi rieng may nay khong mo duoc trang',
                            'This device alone cannot reach any website',
                            'Riêng máy này không lên mạng mặc dù bắt được sóng'],
        }
        self.assertEqual(set(queries), set(WORKFLOWS))
        old_patterns = [*TOPICS.values(), CLIENT_WORDS, INTERNET_WORDS]
        for wid, phrasings in queries.items():
            for query in phrasings:
                with self.subTest(workflow=wid, query=query):
                    self.assertFalse(any(re.search(p, normalize(query)) for p in old_patterns))
                    result = self.registry.retrieve(query, [], self.state())
                    self.assertEqual(result['workflows'][0]['workflow_id'], wid)
                    self.assertEqual(result['workflows'][0]['status'], 'SUPPORTED')

    def test_optical_catalog_is_retrievable_but_has_no_plan(self):
        result = self.registry.retrieve('quang ONT', [], self.state())
        first = result['workflows'][0]
        self.assertEqual((first['workflow_id'], first['status']), ('WF-077', 'CATALOG_ONLY'))
        self.assertEqual(set(first), {'workflow_id', 'status', 'score', 'rerank_score'})
        self.assertEqual(result['functions'], [])
        self.assertFalse(any(n.startswith('w:WF-077') for n in result['seeds']))
        for wid, row in self.registry.workflows.items():
            if row['status'] == 'CATALOG_ONLY' or row['kind'] == 'CHANGE':
                with self.subTest(workflow=wid):
                    self.assertEqual(row['goal_ports'], [])
                    self.assertEqual(self.registry.goal_ports[wid], [])
                    plan = Compiler(self.registry).compile(row['goal_ports'], self.state())
                    self.assertEqual(plan.nodes, {})
        self.assertEqual(self.registry.workflows['WF-WRITE']['kind'], 'CHANGE')

    def test_all_html_records_and_design_skills_are_preserved(self):
        saved = read_json(ROOT / 'data/workflow_catalog_v01.json')
        self.assertEqual(len(saved['workflows']), 101)
        self.assertEqual({w['workflow_id'] for w in saved['workflows']},
                         {f'WF-{i:03}' for i in range(1, 102)})
        self.assertEqual({s['skill_id'] for s in saved['skills']}, {f'SK{i:02}' for i in range(1, 23)})
        self.assertTrue(re.fullmatch('[a-f0-9]{64}', saved['source_sha256']))
        for row in saved['workflows']:
            self.assertIn(row['workflow_id'], self.registry.workflows)
        source = ROOT / 'runs/html_catalog_rag_v1/catalog.json'
        if source.exists():
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), saved['source_sha256'])
            extracted = read_json(source)
            for row in saved['workflows']:
                original = extracted['workflows'][row['workflow_id']]
                self.assertEqual(row['title'], original['title'])
                self.assertEqual(row['symptoms'], [original['title']])
                self.assertEqual(row['skill_ids'], original['skills'])

    def test_running_ids_goals_claims_and_html_mapping(self):
        old = workflow_registry()
        supported = {wid for wid, w in self.registry.workflows.items() if w['status'] == 'SUPPORTED'}
        self.assertEqual(supported, set(WORKFLOWS))
        for wid in supported:
            row = self.registry.workflows[wid]
            expected = list(old.goal_ports[wid]) + (['client.dns'] if wid == 'WF-INTERNET' else [])
            self.assertEqual(row['goal_ports'], expected)
            self.assertTrue(set(row['minimal_goals']) <= set(expected))
            self.assertTrue(row['minimal_goals'])
            self.assertTrue(row['claims'])
            self.assertTrue(set(row['claims']) <= MESSAGES.keys())
        for wid, html_id in HTML_WORKFLOW_IDS.items():
            self.assertEqual(self.registry.workflows[wid]['html_workflow_id'], html_id)

    def test_static_workflow_projection_has_one_directed_edge_per_implemented_skill(self):
        _, names, edges, _, fields, _ = self.registry._static_retrieval_graph()
        for wid, row in self.registry.workflows.items():
            self.assertIn('w:' + wid, names)
            self.assertEqual(fields['w:' + wid], dict(name=row['title'],
                description=' '.join(row['symptoms']), tags=[row['kind'], row['target_scope'], *row.get('tags', ())],
                ports=row['goal_ports']))
            expected = {('w:' + wid, 's:' + sid, 'workflow', 1.0)
                        for sid in row['skill_ids'] if sid in self.registry.skills}
            actual = [edge for edge in edges if edge[0] == 'w:' + wid]
            self.assertEqual(set(actual), expected)
            self.assertEqual(len(actual), len(expected))
            self.assertFalse(any(e[1] == 'w:' + wid for e in edges))
        self.assertIn('SK22', self.registry.workflows['WF-077']['skill_ids'])
        self.assertNotIn('s:SK22', names)

    def test_loader_rejects_unknown_goal_port(self):
        with self.assertRaisesRegex(PlanError, 'unknown_goal_port'):
            self.candidate(lambda d: d['workflows'][0]['goal_ports'].append('unknown.port'))

    def test_loader_rejects_unknown_claim(self):
        with self.assertRaisesRegex(PlanError, 'unknown_workflow_claim'):
            self.candidate(lambda d: d['workflows'][0]['claims'].append('invented_diagnosis'))

    def test_loader_rejects_claimless_supported_workflow(self):
        with self.assertRaisesRegex(PlanError, 'supported_workflow_without_claims'):
            self.candidate(lambda d: next(w for w in d['workflows'] if w['status'] == 'SUPPORTED').update(claims=[]))

    def test_loader_rejects_duplicate_workflow_ids_even_without_claims(self):
        def mutate(data):
            row = copy.deepcopy(next(w for w in data['workflows'] if w['status'] == 'CATALOG_ONLY'))
            self.assertEqual(row['claims'], [])
            data['workflows'].append(row)
        with self.assertRaisesRegex(PlanError, 'duplicate_registry_id:workflow_id'):
            self.candidate(mutate)

    def test_loader_rejects_supported_without_goals(self):
        with self.assertRaisesRegex(PlanError, 'supported_workflow_without_goals'):
            self.candidate(lambda d: next(w for w in d['workflows'] if w['status'] == 'SUPPORTED').update(goal_ports=[]))

    def test_loader_rejects_goal_without_eligible_in_principle_producer(self):
        for change in ({'status': 'PROBE_FAILED'}, {'risk': 'WRITE'}, {'adapter': 'openwrt'}):
            with self.subTest(change=change), self.assertRaisesRegex(PlanError, 'goal_without_eligible_producer'):
                self.candidate(lambda d: next(f for f in d['functions'] if f['function_id'] == 'system.resources').update(change))
        def remove(data):
            data['functions'] = [f for f in data['functions'] if f['function_id'] != 'system.resources']
        with self.assertRaisesRegex(PlanError, 'goal_without_eligible_producer'):
            self.candidate(remove)

    def test_loader_rejects_unknown_skill_for_supported_and_design_records(self):
        for status in ('SUPPORTED', 'CATALOG_ONLY'):
            with self.subTest(status=status), self.assertRaisesRegex(PlanError, 'unknown_workflow_skill'):
                self.candidate(lambda d: next(w for w in d['workflows'] if w['status'] == status)['skill_ids'].append('SK99'))

    def test_catalog_and_change_cannot_declare_goals(self):
        for wid in ('WF-077', 'WF-WRITE'):
            with self.subTest(workflow=wid), self.assertRaisesRegex(PlanError, 'nonplannable_workflow_goals'):
                self.candidate(lambda d: next(w for w in d['workflows'] if w['workflow_id'] == wid)['goal_ports'].append('wan.status'))

    def test_workflow_budgets_are_separate_and_gates_remain_hard(self):
        for method in ('gos', 'bm25'):
            result = self.registry.retrieve('phân giải tên miền', [], self.state(), method=method,
                                            top_n=1, workflow_top_n=4)
            self.assertEqual(len(result['functions']), 1)
            self.assertEqual(len(result['workflows']), 4)
            gated = self.registry.retrieve('phân giải tên miền', [], self.state(capabilities=[]), method=method)
            self.assertEqual(gated['functions'], [])
            self.assertTrue(gated['workflows'])
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                self.registry.retrieve('dns', [], self.state(), workflow_top_n=value)

    def test_runtime_reads_only_shipped_data(self):
        import gateway_pilot.graph_v3.registry_v01 as module
        original = module.read_json
        def read(path):
            self.assertNotIn('runs', Path(path).parts)
            self.assertEqual(Path(path).parent, ROOT / 'data')
            return original(path)
        with patch.object(module, 'read_json', side_effect=read):
            registry = GraphRegistry.from_v01()
            registry.retrieve('quang ONT', [], self.state(registry))

    def test_legacy_has_no_workflows_and_dynamic_policy_keeps_its_result(self):
        registry = workflow_registry()
        self.assertEqual(registry.retrieve('dns', [], self.state(registry))['workflows'], [])
        fixture = next(c for c in read_json(ROOT / 'data/cases.json') if c['id'] == 'GLM-21-0')
        replay = replay_from_fixture(copy.deepcopy(fixture), registry)
        result = diagnose('Laptop An vẫn có Wi-Fi, sao không truy cập Internet?', replay,
                          registry=registry, dynamic=True)
        self.assertEqual(result['workflow'], 'WF-INTERNET')
        self.assertEqual(result['terminal']['diagnosis'], 'client_path_unverified')
        self.assertEqual([e['function_id'] for e in result['graph']['executed']],
                         ['clients.resolve', 'wifi.station', 'client.ipv4', 'wan.status',
                          'wan.routes', 'wan.probe', 'dns.config', 'dns.probe'])


if __name__ == '__main__':
    unittest.main()
