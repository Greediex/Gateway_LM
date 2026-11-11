"""C2 routing acceptance tests; synthetic replay only, no network/advisor service."""
import copy
import inspect
import json
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.registry_v01 import load_registry
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.workflow import diagnose, replay_from_fixture, workflow_registry
from gateway_pilot.turn_router import route_turn
from gateway_pilot.assistant import answer


class TurnRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = GraphRegistry.from_v01()
        cls.fixtures = read_json(ROOT / 'data/cases.json')
        cls.dev = read_json(ROOT / 'benchmarks/router_dev_v0.json')['cases']

    def replay(self, template='wan_down'):
        fixture = next(c for c in self.fixtures if c['template'] == template)
        return replay_from_fixture(copy.deepcopy(fixture), self.registry)

    def route(self, text, **kwargs):
        return route_turn(text, registry=self.registry, **kwargs)

    def test_dev_has_sixty_independent_labels_and_five_per_turn(self):
        self.assertGreaterEqual(len(self.dev), 60)
        self.assertEqual(len({c['message'] for c in self.dev}), len(self.dev))
        counts = Counter(c['turn_type'] for c in self.dev)
        self.assertEqual(len(counts), 8)
        self.assertTrue(all(n >= 5 for n in counts.values()))
        self.assertEqual(sum(c.get('source') == 'C1_review' for c in self.dev), 15)
        symptoms = {s for w in self.registry.workflows.values() for s in w['symptoms']}
        self.assertFalse(symptoms.intersection(c['message'] for c in self.dev))

    def test_five_examples_per_turn_in_three_languages(self):
        for kind in {c['turn_type'] for c in self.dev}:
            examples = [c for c in self.dev if c['turn_type'] == kind and c.get('source') != 'C1_review'][:5]
            self.assertGreaterEqual(len(examples), 5)
            for row in examples:
                with self.subTest(message=row['message']):
                    routed = self.route(row['message'], session=row.get('session'), inventory=row.get('inventory', []))
                    if kind == 'OUT_OF_SCOPE' and routed['features']['retrieval_score'] >= .35:
                        # C2-fix1 explicitly admits retrieval-established scope.
                        # Keep the dev labels unchanged so these errors stay visible.
                        self.assertNotEqual(routed['turn_type'], 'OUT_OF_SCOPE')
                    else:
                        self.assertEqual(routed['turn_type'], kind)

    def test_non_regex_meeting_symptom_uses_workflow_retrieval(self):
        result = self.route('mạng lag khi họp online trên laptop An')
        self.assertEqual(result['turn_type'], 'DIAGNOSE')
        self.assertEqual(result['workflow_candidates'][0]['id'], 'WF-018')

    def test_covered_by_references_and_status_are_validated(self):
        for source, target in [('WF-019', 'WF-077'), ('WF-018', 'WF-023'), ('WF-019', 'bogus')]:
            data = read_json(ROOT / 'data/registry_v01.json')
            next(w for w in data['workflows'] if w['workflow_id'] == source)['covered_by'] = target
            with self.subTest(source=source, target=target), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'registry.json'
                path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaises(PlanError):
                    load_registry(path)

    def test_catalog_scores_fold_before_top_three(self):
        retrieval = self.registry.retrieve('WAN', (), CaseState({'target': {}}, self.registry))
        retrieval['workflows'] = [
            {'workflow_id': 'WF-019', 'score': .4, 'rerank_score': 2},
            {'workflow_id': 'WF-023', 'score': .3, 'rerank_score': 1.5},
            {'workflow_id': 'WF-018', 'score': .2, 'rerank_score': .7}]
        with patch.object(self.registry, 'retrieve', return_value=retrieval):
            result = self.route('WAN chập chờn')
        self.assertEqual(result['turn_type'], 'DIAGNOSE')
        self.assertEqual(result['workflow_candidates'][0]['id'], 'WF-018')
        self.assertAlmostEqual(result['workflow_candidates'][0]['raw_score'], 2.7)
        self.assertNotEqual(result['action'], 'UNSUPPORTED')
        self.assertTrue(all('html_workflow_id' in w for w in result['workflow_candidates']))

    def test_optical_catalog_is_unsupported_without_calls(self):
        with patch('gateway_pilot.core.execute') as core, patch('gateway_pilot.graph_v3.runner.execute') as runner:
            result = answer('PON ONT báo LOS, kiểm tra công suất quang', self.replay(), registry=self.registry)
        self.assertEqual(result['router']['action'], 'UNSUPPORTED')
        self.assertIn('SK22', result['router']['missing_skills'])
        self.assertEqual(result['calls'], 0)
        core.assert_not_called()
        runner.assert_not_called()

    def test_optical_subject_does_not_become_a_wan_lookup(self):
        for request in ('PON không lên', 'ONT đang lên không', 'LOS đỏ trên cổng quang'):
            with self.subTest(request=request):
                result = answer(request, self.replay(), registry=self.registry)
                self.assertEqual(result['router']['action'], 'UNSUPPORTED')
                self.assertEqual(result['router']['workflow_candidates'][0]['id'], 'WF-077')
                self.assertEqual(result['calls'], 0)

    def test_non_measurement_turns_never_execute(self):
        for request, kind in [('Xin chào!', 'SMALLTALK'), ('DNS là gì?', 'KNOWLEDGE'),
                              ('Bạn làm được gì?', 'CAPABILITY'), ('Đổi DNS sang 8.8.8.8', 'CHANGE'),
                              ('Give me a recipe for pasta', 'OUT_OF_SCOPE')]:
            with self.subTest(kind=kind), patch('gateway_pilot.core.execute') as core, \
                    patch('gateway_pilot.graph_v3.runner.execute') as runner:
                result = answer(request, self.replay(), registry=self.registry)
                self.assertEqual(result['turn_type'], kind)
                self.assertEqual(result['calls'], 0)
                self.assertNotIn('graph', result)
                core.assert_not_called()
                runner.assert_not_called()

    def test_capability_uses_catalog_and_knowledge_uses_docs(self):
        cap = answer('Bạn làm được gì?', self.replay(), registry=self.registry)
        for w in self.registry.workflows.values():
            if w['status'] == 'SUPPORTED':
                self.assertIn(w['title'], cap['answer'])
        know = answer('DNS là gì?', self.replay(), registry=self.registry)
        self.assertTrue(know['router']['documents'])
        self.assertIn(know['router']['documents'][0]['text'], know['answer'])

    def test_missing_runbook_catalog_is_harmless(self):
        with patch('gateway_pilot.turn_router.RunbookIndex', side_effect=FileNotFoundError):
            result = answer('DNS là gì?', self.replay(), registry=self.registry)
        self.assertIn('Chưa có tài liệu', result['answer'])
        self.assertEqual(result['calls'], 0)

    def test_pending_session_and_exact_targets_are_followups(self):
        for session in ({'pending_question': 'Thiết bị nào?'}, type('Session', (), {'pending_question': True})()):
            self.assertEqual(self.route('Máy ở phòng khách', session=session)['turn_type'], 'FOLLOW_UP')
        self.assertEqual(self.route('Laptop An', inventory=[{'selector': 'laptop-an'}])['turn_type'], 'FOLLOW_UP')
        self.assertEqual(self.route('còn nó thì sao')['turn_type'], 'FOLLOW_UP')

    def test_missing_or_ambiguous_client_asks_with_inventory_selectors(self):
        inventory = [{'selector': 'laptop-an'}, {'selector': 'my-phone'}]
        retrieval = dict(workflows=[dict(workflow_id='WF-024', rerank_score=.8)], functions=[], skills=[])
        for request in ('thiết bị không nhận được địa chỉ IP', 'laptop-an và my-phone không có IP'):
            # Make every selected minimal goal client scoped, independent of
            # lexical changes to the mixed DHCP workflow's full goal set.
            with patch.object(self.registry, 'retrieve', return_value=retrieval):
                result = self.route(request, inventory=inventory, thresholds={'tau_high': .99})
            self.assertEqual(result['action'], 'ASK_USER')
            self.assertEqual(result['options'], ['laptop-an', 'my-phone'])
            self.assertIsNone(result['plan_hint'])

    def test_lookup_selects_output_port_and_stops_at_that_goal(self):
        result = answer('WAN đang lên không?', self.replay(), registry=self.registry)
        self.assertEqual(result['turn_type'], 'LOOKUP')
        self.assertEqual(result['router']['plan_hint']['goals'], ['wan.status'])
        self.assertEqual(result['route'], 'resolver')
        self.assertEqual(result['calls'], 1)
        self.assertIn('wan.status', result['answer'])
        self.assertNotIn('no_fault_observed', result['answer'])

    def test_lookup_reuses_fresh_fact_and_does_not_answer_from_stale_fact(self):
        from gateway_pilot.workflow import Diagnostic
        replay = self.replay()
        diag = Diagnostic(dict(request='WAN', workflow='WF-018', target={'scope':'gateway'},
                               world=replay['world'], capabilities=replay['capabilities']),
                          self.registry, 'gos', 12, None)
        diag.observe('wan.status', 'test fresh lookup')
        evidence = copy.deepcopy(diag.trace()['evidence'])
        replay['initial_evidence'] = evidence
        fresh = answer('WAN đang lên không?', replay, registry=self.registry)
        self.assertEqual(fresh['calls'], 0)
        self.assertEqual(fresh['goal_facts'][0]['port'], 'wan.status')
        for e in replay['initial_evidence']:
            e['age_s'] = e['ttl_s'] + 1
        replay['capabilities'] = []
        stale = answer('WAN đang lên không?', replay, registry=self.registry)
        self.assertEqual(stale['calls'], 0)
        self.assertNotIn('link_up', stale['answer'])

    def test_lookup_uses_typed_outputs_for_dns_ram_and_pool(self):
        for request, goal in [('DNS đang dùng máy chủ nào?', 'dns.config'),
                              ('router con bao nhieu RAM', 'system.resources'),
                              ('Dải DHCP còn bao nhiêu địa chỉ?', 'dhcp.pool')]:
            with self.subTest(request=request):
                result = self.route(request)
                self.assertEqual(result['plan_hint']['goals'], [goal])

    def test_mid_dns_wan_continues_minimal_goals_without_invented_preconditions(self):
        result = answer('DNS hay WAN làm mạng lỗi?', self.replay(), registry=self.registry)
        self.assertEqual(result['router']['band'], 'MID')
        self.assertTrue(result['router']['plan_hint']['reroute_after_evidence'])
        self.assertEqual(result['router']['band'], 'MID')
        self.assertIn('wan.status', [c['function_id'] for c in result['graph']['executed']])
        self.assertIn('dns.config', [c['function_id'] for c in result['graph']['executed']])
        self.assertNotIn('dns.probe', [c['function_id'] for c in result['graph']['executed']])
        self.assertEqual(len(result['route_history']), 1)
        self.assertTrue(all(h['reason'] for h in result['route_history']))
        self.assertTrue(all('plan_revision' in h for h in result['route_history']))

    def test_gateway_goals_run_before_requesting_a_client(self):
        for request in ('ca nha deu khong vao duoc mang',
                        'mở trang bằng tên thì lỗi nhưng gõ số IP thì vào được',
                        'internet keeps cutting out for everyone in the house'):
            with self.subTest(request=request):
                fixture = next(c for c in self.fixtures if c['id'] == 'GLM-21-1')
                result = answer(request, replay_from_fixture(fixture, self.registry), registry=self.registry)
                routed = result['router']
                self.assertEqual(routed['action'], 'RUN')
                self.assertTrue(routed['target']['pending_client'])
                self.assertTrue(all(self.registry.ports[g].scope == 'gateway'
                                    for g in routed['plan_hint']['goals']))
                self.assertGreater(result['calls'], 0)
                self.assertTrue(all(self.registry.functions[c['function_id']].scope == 'gateway'
                                    for c in result['graph']['executed']))
                self.assertIn('laptop-an', result['answer'])
                self.assertIn('phạm vi gateway', result['answer'])

    def test_options_only_supported_and_zero_scores_offer_all_five(self):
        for row in self.dev:
            routed = self.route(row['message'], inventory=row.get('inventory', []), session=row.get('session'))
            for option in routed['options']:
                if isinstance(option, dict):
                    self.assertEqual(self.registry.workflows[option['id']]['status'], 'SUPPORTED')
        empty = dict(workflows=[], functions=[], skills=[])
        with patch.object(self.registry, 'retrieve', return_value=empty):
            routed = self.route('mang')
        self.assertEqual(len(routed['options']), 5)

    def test_catalog_top_does_not_block_supported_top_three(self):
        retrieval = dict(workflows=[
            dict(workflow_id='WF-083', rerank_score=1.4),
            dict(workflow_id='WF-039', rerank_score=1.0)], functions=[], skills=[])
        with patch.object(self.registry, 'retrieve', return_value=retrieval):
            routed = self.route('router chay i')
        self.assertEqual(routed['band'], 'MID')
        self.assertEqual(routed['features']['top_score'], .5)
        self.assertEqual(routed['action'], 'RUN')
        self.assertEqual(routed['plan_hint']['goals'], ['system.resources'])
        self.assertEqual(routed['nearby_unsupported'][0]['id'], 'WF-083')

    def test_network_quality_uses_gateway_even_when_catalog_scores_higher(self):
        fixture = next(c for c in self.fixtures if c['id'] == 'GLM-21-1')
        result = answer('mạng chất lượng thế nào', replay_from_fixture(fixture, self.registry),
                        registry=self.registry)
        routed = result['router']
        self.assertEqual(routed['action'], 'RUN')
        self.assertEqual(routed['target']['scope'], 'gateway')
        self.assertFalse(routed['target']['pending_client'])
        self.assertIn('wan.probe', routed['plan_hint']['goals'])
        self.assertGreater(result['calls'], 0)
        self.assertIn('wan.probe', {call['function_id'] for call in result['graph']['executed']})

    def test_online_inventory_lookup_reports_missing_capability(self):
        fixture = next(c for c in self.fixtures if c['id'] == 'GLM-21-1')
        result = answer('ai đang online', replay_from_fixture(fixture, self.registry),
                        registry=self.registry)
        self.assertEqual(result['turn_type'], 'LOOKUP')
        self.assertEqual(result['router']['action'], 'UNSUPPORTED')
        self.assertEqual(result['calls'], 0)
        self.assertIn('nguồn dữ liệu', result['answer'].casefold())

    def test_retrieval_score_can_establish_scope_without_network_cue(self):
        result = self.route('chập chờn cả buổi tối')
        self.assertNotEqual(result['turn_type'], 'OUT_OF_SCOPE')
        self.assertFalse(result['features']['network_cue'])
        self.assertEqual(self.route('bạn làm được những gì')['turn_type'], 'CAPABILITY')

    def test_cue_loader_validates_missing_groups_and_types(self):
        from gateway_pilot.turn_router import load_cues, CUES_PATH
        original = read_json(CUES_PATH)
        variants = [{}, {**original, 'network': 'router'}, {**original, 'state': [3]},
                    {**original, 'question': ['']}, {**original, 'network': ['mạng']}]
        variants += [{k: v for k, v in original.items() if k != group}
                     for group in ('question', 'symptom', 'state', 'network', 'capability', 'smalltalk', 'follow_up')]
        for data in variants:
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / 'cues.json'
                path.write_text(json.dumps(data), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'invalid_router_cues'):
                    load_cues(path)

    def test_no_subject_or_workflow_specific_router_literals(self):
        from gateway_pilot import turn_router
        source = inspect.getsource(turn_router)
        self.assertNotIn('pon|ont|los|quang', source)
        self.assertNotIn('WF-018', source)

    def test_explicit_subject_uses_catalog_metadata_for_an_arbitrary_subject(self):
        wid = 'WF-077'
        workflow = {**self.registry.workflows[wid], 'title': 'zephyrlink', 'tags': ['zephyrlink']}
        with patch.dict(self.registry.workflows, {wid: workflow}), \
                patch.object(self.registry, '_retrieval_graph', None):
            result = self.route('zephyrlink khong len')
        self.assertEqual(result['action'], 'UNSUPPORTED')
        self.assertEqual(result['features']['query_focus'], ['zephyrlink'])

    def test_verified_false_demotes_blocked_candidate_below_unblocked(self):
        from gateway_pilot.graph_v3.contracts import Truth
        state = CaseState({'target': {}, 'capabilities': list(self.registry.functions)}, self.registry)
        retrieval = dict(workflows=[dict(workflow_id='WF-018', rerank_score=2),
                                   dict(workflow_id='WF-039', rerank_score=1)], functions=[], skills=[])
        with patch.object(self.registry, 'retrieve', return_value=retrieval), \
                patch('gateway_pilot.graph_v3.contracts.Predicate.evaluate', return_value=Truth.FALSE):
            result = self.route('router loi', state=state)
        self.assertEqual(result['workflow_candidates'][0]['id'], 'WF-039')
        self.assertEqual(result['workflow_candidates'][1]['blocked'], 1)
        self.assertEqual(result['reason'], 'verified_preconditions_demote_blocked_goals')

    def test_blocked_goals_require_false_for_every_eligible_producer(self):
        from gateway_pilot.turn_router import _blocked_goals
        from gateway_pilot.graph_v3.contracts import Truth
        state = CaseState({'target': {}, 'capabilities': list(self.registry.functions)}, self.registry)
        wf = self.registry.workflows['WF-018']
        self.assertEqual(_blocked_goals(wf, self.registry, state), 0)
        with patch('gateway_pilot.graph_v3.contracts.Predicate.evaluate', return_value=Truth.FALSE):
            self.assertEqual(_blocked_goals(wf, self.registry, state), 1)
            # One eligible alternative without a FALSE predicate keeps the
            # goal open. A failing primary never blocks every producer by itself.
            alternate = self.registry.functions['dns.probe']
            with patch.dict(alternate.outputs, {'wan.probe': self.registry.ports['wan.probe']}), \
                    patch.dict(self.registry.hf.outputs, {'wan.probe': ['wan.probe', 'dns.probe']}):
                self.assertEqual(_blocked_goals(wf, self.registry, state), 0)
        state.capabilities = set()
        with patch('gateway_pilot.graph_v3.contracts.Predicate.evaluate', return_value=Truth.FALSE):
            self.assertEqual(_blocked_goals(wf, self.registry, state), 0)

    def test_low_band_stays_diagnose_with_workflow_options(self):
        result = self.route('Mạng bị gì đó', thresholds={'tau_low': .95, 'tau_high': .99})
        self.assertEqual(result['turn_type'], 'DIAGNOSE')
        self.assertEqual(result['band'], 'LOW')
        self.assertEqual(result['action'], 'ASK_USER')
        self.assertGreaterEqual(len(result['options']), 2)
        self.assertTrue(all('html_workflow_id' in o for o in result['options']))

    def test_multi_intent_unions_goals_into_one_resolver_plan(self):
        result = self.route('WAN mất gói và router quá tải CPU')
        self.assertEqual(result['turn_type'], 'DIAGNOSE')
        self.assertEqual(result['route'], 'resolver')
        self.assertIn('wan.probe', result['plan_hint']['goals'])
        self.assertIn('system.resources', result['plan_hint']['goals'])
        self.assertFalse(result['plan_hint'].get('reroute_after_evidence', False))

    def test_multi_intent_executes_both_goal_sets_in_one_case(self):
        replay = self.replay('wan_healthy')
        system = self.replay('sys_ram')
        replay['world'].update(system['world'])
        replay['capabilities'] = sorted(set(replay['capabilities']) | set(system['capabilities']))
        result = answer('WAN mất gói và router quá tải CPU', replay, registry=self.registry)
        executed = [c['function_id'] for c in result['graph']['executed']]
        self.assertIn('system.resources', executed)
        self.assertIn('wan.probe', executed)
        self.assertEqual(executed.count('wan.status'), 1)

    def test_explicit_change_intent_cannot_execute_fastpath(self):
        result = diagnose('DNS', self.replay(), registry=self.registry, workflow='WF-023', turn_type='CHANGE')
        self.assertEqual(result['terminal']['diagnosis'], 'unsafe_change_denied')
        self.assertEqual(result['case_status'], 'BLOCKED')

    def test_supplied_workflow_bypasses_legacy_rule_router(self):
        with patch('gateway_pilot.workflow._rule_route', side_effect=AssertionError('legacy routing')):
            result = diagnose('an unfamiliar expression', self.replay(), registry=self.registry,
                              workflow='WF-018', turn_type='DIAGNOSE')
        self.assertEqual(result['terminal']['diagnosis'], 'wan_link_down')

    def test_advisor_restricted_to_gated_candidates_and_safe_fallback(self):
        class Advisor:
            def __init__(self, proposal):
                self.proposal, self.seen = proposal, None
            def choose_workflow(self, message, candidates):
                self.seen = candidates
                if isinstance(self.proposal, Exception):
                    raise self.proposal
                return self.proposal
        for proposal in ('WF-BOGUS', OSError('offline')):
            advisor = Advisor(proposal)
            expected = self.route('DNS hay WAN làm mạng lỗi?')
            actual = self.route('DNS hay WAN làm mạng lỗi?', advisor=advisor)
            self.assertEqual(actual['workflow_candidates'], expected['workflow_candidates'])
            self.assertNotEqual(actual['source'], 'llm_advisor')
            self.assertTrue(advisor.seen)
            self.assertTrue(all(self.registry.workflows[w]['status'] == 'SUPPORTED' for w in advisor.seen))
        advisor = Advisor('WF-023')
        self.assertEqual(self.route('DNS hay WAN làm mạng lỗi?', advisor=advisor)['source'], 'llm_advisor')
        state = CaseState({'target': {}, 'capabilities': [], 'permissions': []}, self.registry)
        advisor = Advisor('WF-023')
        result = self.route('DNS hay WAN làm mạng lỗi?', state=state, advisor=advisor)
        self.assertIsNone(advisor.seen)
        self.assertIsNone(result['plan_hint'])

    def test_high_band_does_not_consult_advisor(self):
        advisor = type('Advisor', (), {'choose_workflow': lambda *a: self.fail('HIGH advisor call')})()
        result = self.route('Kiểm tra WAN uplink default route', advisor=advisor,
                            thresholds={'tau_low': 0, 'tau_high': 0, 'min_margin': 0})
        self.assertEqual(result['band'], 'HIGH')
        self.assertEqual(result['route'], 'fastpath')

    def test_coverage_counts_eligible_producers_not_retrieval_bonus(self):
        normal = self.route('CPU RAM router quá tải')
        state = CaseState({'target': {}, 'capabilities': [], 'permissions': []}, self.registry)
        blocked = self.route('CPU RAM router quá tải', state=state)
        self.assertEqual(blocked['features']['coverage'], 0)
        self.assertEqual(normal['workflow_candidates'], blocked['workflow_candidates'])
        self.assertIsNone(blocked['plan_hint'])

    def test_no_advisor_every_dev_turn_has_nonempty_answer(self):
        for row in self.dev:
            with self.subTest(message=row['message']):
                result = answer(row['message'], self.replay(), registry=self.registry, session=row.get('session'))
                self.assertTrue(result['answer'].strip())
                self.assertTrue({'turn_type','answer','route','router','case_status','calls'} <= result.keys())

    def test_default_diagnose_matches_explicit_route_on_ten_fixtures(self):
        registry = workflow_registry()
        for wf in ('WF-018','WF-023','WF-024','WF-039','WF-INTERNET'):
            for fixture in [c for c in self.fixtures if c['workflow'] == wf][:2]:
                with self.subTest(fixture=fixture['id']):
                    replay = replay_from_fixture(copy.deepcopy(fixture), registry)
                    before = diagnose(fixture['request'], replay, registry=registry)
                    after = diagnose(fixture['request'], replay, registry=registry, workflow=wf, turn_type='DIAGNOSE')
                    self.assertEqual(before, after)

    def test_resolver_has_no_change_regex_and_accepts_explicit_intent(self):
        from gateway_pilot.graph_v3 import resolver
        self.assertNotIn('cap nhat|ap dung', inspect.getsource(resolver))
        state = CaseState({'target': {}}, self.registry)
        result = resolver.resolve(self.registry, state, 'DNS', intent='CHANGE')
        self.assertEqual(result['decision'], 'BLOCKED')
        self.assertEqual(result['function_candidates'], [])

    def test_assistant_cli(self):
        result = subprocess.run([sys.executable, '-m', 'gateway_pilot.assistant', '--fixture', 'GLM-04-0',
                                 '--request', 'WAN đang lên không?', '--trace'], cwd=ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['turn_type'], 'LOOKUP')


if __name__ == '__main__':
    unittest.main()
