"""GoS lexical-seed parity and Gateway projection/gate regressions."""
import copy
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from gateway_pilot.core import ROOT, execute, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry, rerank_score
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.graph_v3.upstream import _cached_transition, kernel, rank


class GoSRetrievalTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(c for c in read_json(ROOT / 'data/cases.json')
                                       if c['template'] == 'dns_fail'))
        self.state = CaseState(self.case, self.registry, lambda: 0)

    def test_reciprocal_rank_ppr_matches_three_pinned_functions(self):
        names = ['A', 'B', 'C', 'D']
        edges = [('A', 'B', 'dependency', .5), ('B', 'C', 'workflow', 2),
                 ('A', 'C', 'semantic', 1)]
        seeds = ['C', 'A', 'D']
        m = kernel()
        matrix, index = m.build_transition_matrix(
            [SimpleNamespace(name=n) for n in names],
            [SimpleNamespace(source=a, target=b, type=t, weight=w) for a, b, t, w in edges])
        p = m.build_personalization(4, [index[n] for n in seeds], seed_weights=None)
        np.testing.assert_allclose(p, [3/11, 0, 6/11, 2/11], rtol=0, atol=1e-15)
        direct = m.personalized_pagerank(matrix, p, damping=.2, max_iter=500, tol=1e-12)
        np.testing.assert_allclose(list(rank(names, edges, seeds).values()), direct,
                                   rtol=0, atol=1e-12)
        for invalid in (['A', 'A'], ['unknown'], 'A', {'A': -1}, {'A': float('inf')}):
            with self.assertRaises(ValueError):
                rank(names, edges, invalid)

    def test_rerank_hand_arithmetic_for_six_nodes(self):
        # engine.py:845-859,1082-1145: query tokens for "dns wan" are
        # {dns_wan, dns, wan}; field bonus = weight * overlap / 3.
        # No task/domain/tooling/artifact fields in the pilot.
        nodes = [
            dict(name='dns wan', description='dns wan', tags=['dns'], ports=['wan']),
            dict(name='dns', description='', tags=[], ports=[]),
            dict(name='other', description='dns wan', tags=[], ports=[]),
            dict(name='other', description='', tags=['dns', 'wan'], ports=[]),
            dict(name='other', description='', tags=[], ports=['dns', 'wan']),
            dict(name='other', description='', tags=[], ports=[]),
        ]
        expected = [
            .1 + 1.25*3/3 + .9*3/3 + 1.15/3 + .75/3 + 1.2 + .2/1,
            .1 + 1.25/3 + 1.2 + .2/2,
            .1 + .9*3/3 + .2/3,
            .1 + 1.15*2/3 + .2/4,
            .1 + .75*2/3 + .2/5,
            .1 + .2/6,
        ]
        actual = [rerank_score('dns wan', graph_score=.1, seed_rank=i, **node)
                  for i, node in enumerate(nodes, 1)]
        np.testing.assert_allclose(actual, expected, rtol=0, atol=1e-14)
        self.assertEqual(sorted(range(6), key=lambda i: -actual[i]), [0, 1, 2, 3, 4, 5])
        # Lexical-only seed fusion has no semantic graph score/rank:
        # engine.py:1918-1921 adds 0.15 / lexical_rank after field reranking.
        lexical_expected = [value - .1 - .2/i + .15/i for i, value in enumerate(expected, 1)]
        lexical = [rerank_score('dns wan', lexical_rank=i, **node)
                   for i, node in enumerate(nodes, 1)]
        np.testing.assert_allclose(lexical, lexical_expected, rtol=0, atol=1e-14)

    def test_membership_transition_and_io_weights_are_hand_computed(self):
        r = self.registry
        # A single membership plus a competing edge exposes accidental reverse
        # duplication: F->S has .5 mass, F->consumer has 1, hence [1/3,2/3].
        r.functions = {fid: copy.deepcopy(r.functions[fid]) for fid in ('wan.status', 'wan.routes')}
        r.skills = {'SK04': r.skills['SK04']}
        r.relations = []
        r.functions['wan.routes'].skills = ()
        r.rebuild()
        result = r.retrieve('wan', [], self.state)
        edges = result['edges']
        self.assertEqual(edges.count(('s:SK04', 'f:wan.status', 'workflow', 1.0)), 1)
        self.assertFalse(any(a == 'f:wan.status' and b == 's:SK04' for a, b, _, _ in edges))
        names = tuple(sorted(result['scores']))
        matrix, index = _cached_transition(names, tuple(sorted(edges)), True, result['graph_key'])
        self.assertAlmostEqual(matrix[index['f:wan.status'], index['s:SK04']], 1/3)
        self.assertAlmostEqual(matrix[index['f:wan.status'], index['f:wan.routes']], 2/3)
        # Matching one of two consumer inputs is weight 1/2, once per pair.
        r.functions['wan.routes'].inputs['dns.config'] = r.ports['dns.config']
        r.rebuild()
        result = r.retrieve('wan', [], self.state)
        edge = next(e for e in result['edge_provenance'] if e['provenance'] == 'deterministic_io')
        self.assertEqual(edge['weight'], .5)
        self.assertEqual(edge['evidence'], ['wan.status'])
        self.assertEqual(edge['confidence'], .5)
        # Equal port names alone do not establish typed/provenance acceptance.
        r.functions['wan.status'].outputs['wan.status'] = replace(
            r.functions['wan.status'].outputs['wan.status'], provenance='untrusted/')
        r.rebuild()
        self.assertFalse(any(e['provenance'] == 'deterministic_io'
                             for e in r.retrieve('wan', [], self.state)['edge_provenance']))

    def test_ineligible_and_completed_functions_remain_graph_nodes(self):
        self.state.capabilities = {'wan.status'}
        result = self.registry.retrieve('wan', [], self.state, top_n=20)
        self.assertEqual(result['functions'], ['wan.status'])
        self.assertIn('f:dns.probe', result['scores'])
        self.assertNotIn('f:dns.probe', result['seeds'])
        evidence = execute('wan.status', {}, self.state, self.case, self.registry.legacy)
        self.state.record(evidence)
        result = self.registry.retrieve('wan', [], self.state)
        self.assertNotIn('wan.status', result['functions'])
        self.assertNotIn('f:wan.status', result['seeds'])
        self.assertIn('f:wan.status', result['scores'])
        # A changed gate must reuse exactly the same full graph/transition.
        self.assertEqual(len(result['scores']), len(self.registry.skills) + len(self.registry.functions))

    def test_nonsense_empty_and_callers_keep_working(self):
        from gateway_pilot.graph_v3.context import retrieve_context
        from gateway_pilot.graph_v3.orchestrator import run_plan
        from gateway_pilot.graph_v3.planner import Compiler
        from gateway_pilot.graph_v3.runner import GraphRunner
        for method in ('gos', 'bm25'):
            result = self.registry.retrieve('qzxvplmok', [], self.state, method=method)
            self.assertEqual(result['functions'], [])
            self.assertEqual(result['seeds'], {})
            self.assertFalse(result['lexical_match'])
            self.assertFalse(result['upstream_kernel_used'])
            self.assertEqual(result['scores'], {})
        self.assertEqual(retrieve_context(self.registry, self.state, 'qzxvplmok', [])['bundles'], [])
        self.case['request'] = 'qzxvplmok'
        plan = Compiler(self.registry).compile([], self.state, requested=['wan.status', 'dns.config'])
        runner = GraphRunner(self.registry, self.case, self.state)
        # Empty retrieval throughout isolates READY's objective/id fallback.
        with patch.object(self.registry, 'retrieve', side_effect=lambda *a, **kw: copy.deepcopy(result)):
            events = run_plan(runner, plan, [])
        self.assertEqual(events[0]['selected_ready'], 'dns.config')
        self.assertEqual(runner.calls, 2)

    def test_gs_version_invalidates_static_graph_and_transition_cache(self):
        _cached_transition.cache_clear()
        r = self.registry
        first = r.retrieve('wan', [], self.state)
        graph = r._retrieval_graph
        second = r.retrieve('dns', [], self.state)
        self.assertIs(r._retrieval_graph, graph)
        self.assertEqual(first['graph_key'], second['graph_key'])
        self.assertEqual(_cached_transition.cache_info().misses, 1)
        self.assertEqual(_cached_transition.cache_info().hits, 1)
        r.gs.edit_edge('add', source='SK04', target='SK08', edge_type='similar_to',
                       reason='test cache version', permissions={'graph.edit'}, base_version=r.gs.version)
        third = r.retrieve('wan', [], self.state)
        self.assertNotEqual(first['graph_key'], third['graph_key'])
        self.assertIsNot(r._retrieval_graph, graph)
        self.assertEqual(_cached_transition.cache_info().misses, 2)
        r.gs.rollback(1, permissions={'graph.edit'}, reason='restore same topology')
        restored = r.retrieve('wan', [], self.state)
        self.assertEqual(restored['edges'], first['edges'])
        self.assertNotEqual(restored['graph_key'], first['graph_key'])
        # Identical edge content at a new version still needs a new matrix.
        self.assertEqual(_cached_transition.cache_info().misses, 3)
        r.rebuild()
        self.assertNotEqual(restored['graph_key'], r.retrieve('wan', [], self.state)['graph_key'])

    def test_seed_and_result_budgets_and_reciprocal_seed_trace(self):
        r = self.registry
        result = r.retrieve('dns wan', [], self.state, seed_top_k=2, top_n=7)
        self.assertEqual(len(result['seeds']), 2)
        self.assertEqual(list(result['seeds'].values()), [2/3, 1/3])
        self.assertEqual(list(result['seed_ranks'].values()), [1, 2])
        self.assertEqual(len(result['functions']), 7)
        self.assertEqual(r.retrieve('dns wan', [], self.state, k=2),
                         r.retrieve('dns wan', [], self.state, seed_top_k=2, top_n=2))
        self.assertEqual(len(r.retrieve('dns wan', [], self.state)['functions']), 5)
        self.assertEqual(len(r.retrieve('dns wan', [], self.state)['seeds']), 4)
        self.assertEqual(r.retrieve('dns wan', [], self.state, k=3, seed_top_k=2),
                         r.retrieve('dns wan', [], self.state, seed_top_k=2, top_n=3))
        self.assertEqual(r.retrieve('dns wan', [], self.state, k=3, top_n=2),
                         r.retrieve('dns wan', [], self.state, seed_top_k=3, top_n=2))
        for options in ({'seed_top_k': 0}, {'top_n': -1}, {'k': True}, {'seed_top_k': 1.5}):
            with self.assertRaises(ValueError):
                r.retrieve('wan', [], self.state, **options)

    def test_seed_fusion_and_post_ppr_scan_use_upstream_formula(self):
        r = self.registry
        # A two-token query has 3 signature tokens: dns_wan, dns, wan.
        # BM25 ranks the exact one-token document "dns" before the longer
        # "dns wan" document. Field fusion must reverse that order:
        # dns wan = 1.25 + .9 + 1.2 + .15/2 = 3.425
        # dns     = 1.25/3 + 1.2 + .15/1 = 1.7666...
        base = copy.deepcopy(r.functions['system.resources'])
        r.functions = {}
        for fid, description in [('dns wan', 'dns wan'), ('dns', ''), ('other', '')]:
            f = copy.deepcopy(base)
            f.id, f.description, f.skills = fid, description, ()
            r.functions[fid] = f
        r.skills, r.relations = {}, []
        r.rebuild()
        state = SimpleNamespace(fact=lambda *a: None, errors=[], completed=lambda f: False,
                                allowed=lambda f: True)
        actual_rank = rank
        with patch('gateway_pilot.graph_v3.graphs.rank', wraps=actual_rank) as called:
            result = r.retrieve('dns wan', [], state, seed_top_k=2, top_n=3)
        self.assertEqual(called.call_args.args[2], ['f:dns wan', 'f:dns'])
        self.assertEqual(result['seeds'], {'f:dns wan': 2/3, 'f:dns': 1/3})
        # PPR scan selects dns, other first; the perfect lexical match is
        # outside top_n and cannot enter through a global rerank.
        ppr = {'f:dns': .6, 'f:other': .3, 'f:dns wan': .1}
        with patch('gateway_pilot.graph_v3.graphs.rank', return_value=ppr):
            result = r.retrieve('dns wan', [], state, seed_top_k=2, top_n=2)
        self.assertEqual(result['functions'], ['dns', 'other'])
        self.assertEqual(set(result['rerank_scores']), {'f:dns', 'f:other'})
        self.assertAlmostEqual(result['rerank_scores']['f:dns'], .6 + 1.25/3 + 1.2 + .2/2)
        self.assertAlmostEqual(result['rerank_scores']['f:other'], .3)
        with patch('gateway_pilot.graph_v3.graphs.rank', return_value=ppr):
            result = r.retrieve('dns wan', [], state, seed_top_k=2, top_n=3)
        self.assertEqual(result['functions'], ['dns wan', 'dns', 'other'])
        self.assertAlmostEqual(result['rerank_scores']['f:dns wan'], .1 + 1.25 + .9 + 1.2 + .2/1)


    def test_vietnamese_accented_and_unaccented_queries_rank_alike(self):
        # Review fix: upstream tokens keep only [a-z0-9]; without folding,
        # "phân giải tên miền" degrades to fragments and DNS is outranked.
        state = CaseState({"target": {}, "capabilities": list(self.registry.functions)}, self.registry)
        accented = self.registry.retrieve("Kiểm tra phân giải tên miền", [], state, seed_top_k=4, top_n=5)
        plain = self.registry.retrieve("kiem tra phan giai ten mien", [], state, seed_top_k=4, top_n=5)
        self.assertEqual(accented["functions"], plain["functions"])
        self.assertEqual(accented["seed_ranks"], plain["seed_ranks"])
        self.assertEqual(set(accented["functions"][:2]), {"dns.config", "dns.probe"})
        # ASCII input is untouched, so the ported formula keeps upstream parity.
        self.assertEqual(rerank_score("dns wan", name="dns wan"), 1.25 + 1.2)


if __name__ == '__main__':
    unittest.main()
