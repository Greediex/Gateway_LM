import copy
import json
import math
import unittest
from types import SimpleNamespace
import numpy as np

from gateway_pilot.core import ROOT, PlanError, read_json, execute
from gateway_pilot.graph_v3.contracts import Port, Predicate, Truth, Function, schema_subset
from gateway_pilot.graph_v3.graphs import GraphRegistry, SkillGraph, Relation
from gateway_pilot.graph_v3.planner import Compiler, ExecutionDAG, Edge, NodeState
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.graph_v3.upstream import kernel, rank, KERNEL_SHA256, SOURCE


class GraphTests(unittest.TestCase):
    def setUp(self):
        self.registry = GraphRegistry()
        self.case = copy.deepcopy(next(c for c in read_json(ROOT / "data/cases.json") if c["template"] == "dns_fail"))
        self.now = 0.0
        self.state = CaseState(self.case, self.registry, lambda: self.now)

    def put(self, fid):
        e = execute(fid, {}, self.state, self.case, self.registry.legacy)
        self.state.record(e)
        return e

    def alt(self, source="wan.probe", name="z.backup", cost=3):
        f = copy.deepcopy(self.registry.functions[source])
        f.id, f.cost = name, cost
        self.registry.functions[name] = f
        old = copy.deepcopy(self.registry.legacy.functions[source]); old["id"] = name
        self.registry.legacy.functions[name] = old
        self.state.capabilities.add(name)
        self.case["world"][name] = copy.deepcopy(self.case["world"][source])
        self.registry.rebuild()
        return f

    def test_actual_upstream_analytic_two_node_reverse_ppr(self):
        scores = rank(["A", "B"], [("A", "B", "dependency", 1)], {"B": 1})
        self.assertAlmostEqual(scores["A"], 4/9, places=10)
        self.assertAlmostEqual(scores["B"], 5/9, places=10)

    def test_upstream_forward_only_does_not_recover_producer(self):
        scores = rank(["A", "B"], [("A", "B", "dependency", 1)], {"B": 1}, reverse=False)
        self.assertEqual(scores["A"], 0)

    def test_upstream_transition_matrix_oracle(self):
        m = kernel()
        nodes = [SimpleNamespace(name=x) for x in "ABC"]
        edges = [SimpleNamespace(source=a,target=b,type=t,weight=w) for a,b,t,w in
                 [("A","B","dependency",2),("A","C","semantic",1),("B","C","workflow",3)]]
        matrix,_ = m.build_transition_matrix(nodes,edges)
        np.testing.assert_allclose(matrix, [[0,2/3,1/3],[2/5,0,3/5],[2/17,15/17,0]])

    def test_upstream_adapter_matches_direct_call(self):
        names, edges, seeds = ["A","B","C"], [("A","B","dependency",2),("B","C","workflow",1)], {"C":2,"B":1}
        m=kernel(); nodes=[SimpleNamespace(name=x) for x in names]
        es=[SimpleNamespace(source=a,target=b,type=t,weight=w) for a,b,t,w in edges]
        matrix,index=m.build_transition_matrix(nodes,es)
        p=m.build_personalization(3,[index[n] for n in seeds],list(seeds.values()))
        direct=m.personalized_pagerank(matrix,p,damping=.2,max_iter=500,tol=1e-12)
        np.testing.assert_allclose(list(rank(names,edges,seeds).values()),direct,atol=1e-14)

    def test_zero_weight_and_conflict_not_diffused(self):
        scores=rank(["A","B"],[("A","B","dependency",0),("A","B","conflict",1)],{"B":1})
        self.assertEqual(scores["A"],0)

    def test_skill_hard_edges_are_runtime_dependencies(self):
        # dhcp.pool has no Function input, so identity must come from G_S.
        p=Compiler(self.registry).compile([],self.state,requested=["dhcp.pool"])
        self.assertIn("clients.resolve",p.nodes)
        self.assertIn(Edge("clients.resolve","dhcp.pool","STATE","client.identity"),p.edges)

    def test_soft_composition_does_not_become_hard_execution(self):
        p=Compiler(self.registry).compile([],self.state,requested=["wan.status"])
        self.assertEqual(set(p.nodes),{"wan.status"})

    def test_skill_dependency_cycle_rejected(self):
        with self.assertRaisesRegex(PlanError,"skill_dependency_cycle"):
            SkillGraph(self.registry.skills,[Relation("SK01","SK03","depends_on"),Relation("SK03","SK01","depends_on")])

    def test_membership_is_bidirectional(self):
        self.assertIn("SK08",self.registry.gsf.by_function["system.logs"])
        self.assertIn("system.logs",self.registry.gsf.by_skill["SK09"])

    def test_data_and_state_edges_and_invocation_contract(self):
        p=Compiler(self.registry).compile(["wan.probe"],self.state)
        self.assertIn(Edge("wan.routes","wan.probe","DATA","wan.routes"),p.edges)
        self.assertIn(Edge("wan.routes","wan.probe","STATE","wan.routes"),p.edges)
        self.assertTrue(p.nodes['wan.probe'].verifier)
        self.assertTrue(p.nodes['wan.probe'].contract_digest)
        self.assertEqual(p.nodes['wan.probe'].target['scope'],'gateway')
        self.assertEqual(p.nodes['wan.probe'].bindings['wan.routes'].kind,'node')

    def test_order_edge_is_separate(self):
        self.registry.functions['dns.probe'].order_after=('wan.probe',)
        p=Compiler(self.registry).compile(['dns.probe'],self.state)
        self.assertIn(Edge('wan.probe','dns.probe','ORDER'),p.edges)

    def test_full_prerequisite_cost_beats_cheap_consumer(self):
        # Cheap alternative with expensive extra prerequisite loses globally.
        self.registry.functions['wan.probe'].cost=4
        alt=self.alt(cost=1)
        alt.inputs['system.resources']=self.registry.ports['system.resources']
        self.registry.functions['system.resources'].cost=10
        self.registry.rebuild()
        p=Compiler(self.registry).compile(['wan.probe'],self.state)
        self.assertIn('wan.probe',p.nodes)
        self.assertNotIn('z.backup',p.nodes)

    def test_producer_cost_not_alphabetical(self):
        alt=self.alt(cost=.1)
        p=Compiler(self.registry).compile(['wan.probe'],self.state)
        self.assertIn(alt.id,p.nodes)
        self.assertNotIn('wan.probe',p.nodes)

    def test_filter_capability_before_topk(self):
        self.state.capabilities={'wan.status'}
        result=self.registry.retrieve('DNS change resolver',[],self.state,k=1)
        self.assertEqual(result['functions'],['wan.status'])
        self.assertTrue(result['upstream_kernel_used'])

    def test_filter_permission_before_topk(self):
        self.state.permissions={'system.read'}
        result=self.registry.retrieve('WAN',[],self.state,k=4)
        self.assertTrue(all(f.startswith('system.') for f in result['functions']))

    def test_state_query_updates_after_new_evidence(self):
        before=self.registry.retrieve('network',['wan.status'],self.state)['query']
        self.put('wan.status')
        after=self.registry.retrieve('network',['wan.status'],self.state)['query']
        self.assertNotEqual(before,after)
        self.assertIn('link_up',after)

    def test_completed_function_not_exposed_or_reexecuted(self):
        self.put('wan.status')
        result=self.registry.retrieve('WAN status',[],self.state,k=20)
        self.assertNotIn('wan.status',result['functions'])
        p=Compiler(self.registry).compile(['wan.status'],self.state)
        self.assertFalse(p.nodes)

    def test_fresh_evidence_is_bound_by_id(self):
        e=self.put('wan.status')
        p=Compiler(self.registry).compile(['wan.routes'],self.state)
        self.assertEqual(p.nodes['wan.routes'].bindings['wan.status'].ref,e['id'])

    def test_real_clock_expiry_and_version_invalidation(self):
        e=self.put('wan.status'); self.now=31
        self.assertIsNone(self.state.fact('wan.status'))
        self.now=0; self.state.config_version='changed'
        self.assertIsNone(self.state.fact('wan.status'))
        self.state.config_version=e['config_version']; self.state.boot_id='reboot'
        self.assertIsNone(self.state.fact('wan.status'))

    def test_newer_error_does_not_fallback_to_old_success(self):
        self.put('wan.status')
        self.case['world']['wan.status']={'_status':'TIMEOUT'}
        self.put('wan.status')
        self.assertIsNone(self.state.fact('wan.status'))

    def test_wrong_source_rejected(self):
        e=self.put('wan.status'); e['source']='untrusted-log'
        self.assertIsNone(self.state.fact('wan.status'))

    def test_wrong_gateway_rejected(self):
        e=self.put('wan.status'); e['target']='other'
        self.assertIsNone(self.state.fact('wan.status'))

    def test_tri_state_predicate(self):
        p=Predicate('wan.routes','default_route','eq',True)
        self.assertEqual(p.evaluate(self.state),Truth.UNKNOWN)
        self.put('wan.status'); self.put('wan.routes')
        self.assertEqual(p.evaluate(self.state),Truth.TRUE)
        self.state.evidence[-1]['value']['default_route']=False
        self.assertEqual(p.evaluate(self.state),Truth.FALSE)

    def test_predicate_false_blocks_not_assumes_success(self):
        self.put('wan.status'); e=self.put('wan.routes');e['value']['default_route']=False
        with self.assertRaisesRegex(PlanError,'false_precondition'):
            Compiler(self.registry).compile(['wan.probe'],self.state)

    def test_runtime_guard_false_blocks_probe(self):
        self.case['world']['wan.routes']['default_route']=False
        plan=Compiler(self.registry).compile(['wan.probe'],self.state)
        runner=GraphRunner(self.registry,self.case,self.state)
        final=runner.run(plan)
        self.assertEqual(final.nodes['wan.probe'].state,NodeState.BLOCKED)
        self.assertFalse(self.state.attempts['wan.probe'])

    def test_schema_required_and_numeric_narrowing(self):
        self.assertTrue(schema_subset({'type':'integer','minimum':2},{'type':'number','minimum':1}))
        self.assertFalse(schema_subset({'type':'number'},{'type':'integer'}))
        self.assertFalse(schema_subset({'type':'object','properties':{},'required':[]},
                                       {'type':'object','properties':{'ip':{'type':'string'}},'required':['ip']}))

    def test_unknown_schema_combinator_not_guessed(self):
        self.assertFalse(schema_subset({'oneOf':[{'type':'string'}]},{'type':'string'}))

    def test_scope_and_provenance_part_of_schema_graph(self):
        p=self.registry.ports['wan.status']
        self.assertFalse(p.accepts(Port(p.name,'client',p.schema)))
        self.assertFalse(p.accepts(Port(p.name,p.scope,p.schema,'other/')))

    def test_node_and_search_budgets(self):
        with self.assertRaisesRegex(PlanError,'budget'):
            Compiler(self.registry,max_nodes=1).compile(['wan.probe'],self.state)
        with self.assertRaisesRegex(PlanError,'search_budget'):
            Compiler(self.registry,max_search=1).compile(['wan.probe'],self.state)

    def test_function_cycle_rejected(self):
        self.registry.functions['wan.status'].inputs={'wan.probe':self.registry.ports['wan.probe']}
        self.registry.rebuild()
        with self.assertRaisesRegex(PlanError,'dependency_cycle'):
            Compiler(self.registry).compile(['wan.probe'],self.state)

    def test_conflict_inside_prerequisite_chain_rejected(self):
        self.registry.function_conflicts.add(frozenset(['wan.status','wan.routes']))
        with self.assertRaisesRegex(PlanError,'conflict'):
            Compiler(self.registry).compile(['wan.routes'],self.state)

    def test_output_verification_and_no_blind_ack(self):
        self.case['world']['wan.status']={'link_up':'true'}
        plan=Compiler(self.registry).compile(['wan.status'],self.state)
        runner=GraphRunner(self.registry,self.case,self.state,max_repairs=0)
        final=runner.run(plan)
        self.assertEqual(final.nodes['wan.status'].state,NodeState.INCONCLUSIVE)
        self.assertIsNone(self.state.fact('wan.status'))

    def test_deadline_and_call_budget(self):
        plan=Compiler(self.registry).compile(['wan.status'],self.state)
        runner=GraphRunner(self.registry,self.case,self.state,max_calls=0)
        with self.assertRaisesRegex(PlanError,'budget'): runner.step(plan)
        runner=GraphRunner(self.registry,self.case,self.state,deadline_s=1)
        self.now=2
        with self.assertRaisesRegex(PlanError,'deadline'): runner.step(plan)

    def test_contract_change_after_compile_rejected(self):
        plan=Compiler(self.registry).compile(['wan.status'],self.state)
        self.registry.functions['wan.status'].cost=50
        with self.assertRaisesRegex(PlanError,'contract_changed'): GraphRunner(self.registry,self.case,self.state).run(plan)

    def test_illegal_node_transition_rejected(self):
        p=Compiler(self.registry).compile(['wan.status'],self.state)
        with self.assertRaisesRegex(PlanError,'illegal_node_transition'):
            p.nodes['wan.status'].transition(NodeState.SUCCEEDED)

    def test_timed_out_producer_substituted_and_unrelated_evidence_preserved(self):
        self.alt('wan.status','z.status.backup',3)
        self.case['world']['wan.status']['_duration_ms']=3000
        p=Compiler(self.registry).compile(['dns.probe','wan.routes'],self.state)
        runner=GraphRunner(self.registry,self.case,self.state)
        final=runner.run(p)
        self.assertEqual(final.revision,2)
        self.assertTrue(self.state.fact('wan.routes'))
        self.assertEqual(self.state.attempts['dns.config'],1)
        self.assertEqual(self.state.attempts['dns.probe'],1)
        self.assertTrue(any(a.get('operator')=='SUBSTITUTE_REWIRE_INSERT_PREREQ' for a in final.audit))
        self.assertEqual(self.state.attempts['z.status.backup'],1)

    def test_order_edge_does_not_invalidate_data_descendants(self):
        self.registry.functions['dns.probe'].order_after=('wan.status',)
        p=Compiler(self.registry).compile(['dns.probe'],self.state)
        self.assertNotIn('dns.probe',p.descendants('wan.status'))

    def test_multi_output_shared_producer_cost_and_execution(self):
        schema={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok'],'additionalProperties':False}
        x,y=Port('x','gateway',schema),Port('y','gateway',schema)
        self.registry.ports.update(x=x,y=y)
        for name,outputs,cost in [('x_only',{'x':x},2),('y_only',{'y':y},2),('shared',{'x':x,'y':y},3)]:
            self.registry.functions[name]=Function(name,('SK04',),{},outputs,name,'gateway',cost=cost)
            self.state.capabilities.add(name)
            self.registry.legacy.functions[name]={'id':name,'produces':list(outputs),'requires':[], 'risk':'READ','scope':'gateway','ttl_s':30}
        self.registry.rebuild()
        p=Compiler(self.registry).compile(['x','y'],self.state)
        self.assertEqual(set(p.nodes),{'shared'})
        self.case['world']['shared']={'outputs':{'x':{'ok':True},'y':{'ok':True}}}
        runner=GraphRunner(self.registry,self.case,self.state)
        final=runner.run(p)
        self.assertEqual(final.nodes['shared'].state,NodeState.SUCCEEDED)
        self.assertEqual(runner.calls,1)
        self.assertTrue(self.state.fact('x'));self.assertTrue(self.state.fact('y'))

    def test_schema_additional_properties_and_union_fail_closed(self):
        self.assertFalse(schema_subset({'type':'object','additionalProperties':True},
                                      {'type':'object','additionalProperties':{'type':'string'}}))
        self.assertFalse(schema_subset({'type':['object','null'],'properties':{}},
                                      {'type':['object','null'],'required':['id']}))

    def test_nested_boolean_schema_fails_closed_without_exception(self):
        self.assertFalse(schema_subset({'type':'array','items':False},{'type':'array','items':True}))
        self.assertFalse(schema_subset({'type':'object','properties':{'x':True}},
                                      {'type':'object','properties':{'x':{'type':'string'}}}))

    def test_repair_preserves_other_requested_root(self):
        self.alt('dns.config','z.config.backup',3)
        self.case['world']['dns.config']['_duration_ms']=3000
        p=Compiler(self.registry).compile([],self.state,requested=['dns.config','wan.probe'])
        runner=GraphRunner(self.registry,self.case,self.state)
        final=runner.run(p)
        self.assertTrue(self.state.fact('wan.probe'))
        self.assertTrue(self.state.fact('dns.config'))
        self.assertIn('wan.probe',final.requested)
        self.assertEqual(final.revision,2)

    def test_incompatible_planned_output_does_not_hide_an_alternative(self):
        broad=Port('p','gateway',{'type':'object','properties':{'n':{'type':'integer'}},'required':['n']})
        narrow=Port('p','gateway',{'type':'object','properties':{'n':{'type':'integer','minimum':5}},'required':['n']})
        bit={'type':'object','properties':{'ok':{'type':'boolean'}},'required':['ok']}
        q,r=Port('q','gateway',bit),Port('r','gateway',bit)
        self.registry.ports.update(p=broad,q=q,r=r)
        for name,inputs,outputs,world in [
            ('a_broad',{}, {'p':broad,'q':q}, {'outputs':{'p':{'n':0},'q':{'ok':True}}}),
            ('b_narrow',{}, {'p':narrow}, {'n':10}),
            ('c_consumer',{'p':narrow}, {'r':r}, {'ok':True})]:
            self.registry.functions[name]=Function(name,('SK04',),inputs,outputs,name,'gateway')
            self.registry.legacy.functions[name]={'id':name,'produces':list(outputs),'requires':list(inputs),
                                                  'risk':'READ','scope':'gateway','ttl_s':30}
            for port in outputs:
                self.registry.legacy.data['port_fields'][port]={'ok':'bool'} if port!='p' else {'n':'number'}
            self.state.capabilities.add(name); self.case['world'][name]=world
        self.registry.functions['c_consumer'].predicates=(Predicate('p','n','gt',0),)
        self.registry.rebuild()
        p=Compiler(self.registry).compile(['q','r'],self.state)
        self.assertEqual(set(p.nodes),{'a_broad','b_narrow','c_consumer'})
        self.assertEqual(p.nodes['c_consumer'].bindings['p'].ref,'b_narrow')
        final=GraphRunner(self.registry,self.case,self.state).run(p)
        self.assertEqual(final.nodes['c_consumer'].state,NodeState.SUCCEEDED)

    def test_order_does_not_accept_equivalent_data_from_different_producer(self):
        self.alt('dns.config', 'z.config.backup')
        self.put('z.config.backup')
        self.registry.functions['wan.status'].order_after=('dns.config',)
        plan=Compiler(self.registry).compile(['wan.status'],self.state)
        self.assertEqual(plan.topological(),['dns.config','wan.status'])
        self.assertIn(Edge('dns.config','wan.status','ORDER'),plan.edges)

    def test_produces_for_and_similarity_are_retrieval_hints(self):
        self.registry.relations.extend([Relation('SK04','SK05','produces_for',2.0),
                                        Relation('SK04','SK05','similar_to')])
        self.registry.rebuild()
        retrieved=self.registry.retrieve('DNS resolver',[],self.state,k=4)
        self.assertIn(('s:SK04','s:SK05','dependency',2.0),retrieved['edges'])
        self.assertIn(('s:SK04','s:SK05','semantic',1.0),retrieved['edges'])
        plan=Compiler(self.registry).compile(['dns.probe'],self.state)
        self.assertEqual(set(plan.nodes),{'dns.config','dns.probe'})

    def test_ppr_invalid_inputs_rejected(self):
        for names,edges,seeds in [(['A','A'],[],{'A':1}),(['A'],[('A','B','semantic',1)],{'A':1}),
                                  (['A'],[],{'A':float('nan')})]:
            with self.assertRaises(ValueError):rank(names,edges,seeds)

    def test_wrong_method_or_budget_not_silent_fallback(self):
        with self.assertRaises(ValueError):self.registry.retrieve('WAN',[],self.state,method='misspelled')
        with self.assertRaises(ValueError):self.registry.retrieve('WAN',[],self.state,k=0)

    def test_dry_run_edit_permission_version_and_rollback(self):
        gs=self.registry.gs
        proposal=gs.propose_edge(Relation('SK05','SK04','alternative_to'))
        self.assertEqual(gs.version,1)
        self.assertFalse(any(e.kind=='alternative_to' for e in gs.edges))
        with self.assertRaisesRegex(PlanError,'permission'):gs.apply(proposal)
        gs.apply(proposal,permissions={'graph.edit'},actor='test-core')
        self.assertEqual(gs.version,2)
        with self.assertRaisesRegex(PlanError,'version_conflict'):gs.apply(proposal,permissions={'graph.edit'})
        gs.rollback(1,permissions={'graph.edit'})
        self.assertEqual(gs.version,3)
        self.assertFalse(any(e.kind=='alternative_to' for e in gs.edges))

    def test_conflicting_skill_dependency_proposal_rejected(self):
        gs=self.registry.gs
        with self.assertRaisesRegex(PlanError,'dependency_conflict'):
            gs.propose_edge(Relation('SK03','SK01','conflicts_with'))

    def test_skill_graph_revision_change_invalidates_compiled_plan(self):
        p=Compiler(self.registry).compile(['wan.status'],self.state)
        gs=self.registry.gs
        gs.apply(gs.propose_edge(Relation('SK05','SK04','composes_with')),permissions={'graph.edit'})
        with self.assertRaisesRegex(PlanError,'skill_graph_changed'):
            GraphRunner(self.registry,self.case,self.state).ready(p)

    def test_orchestrator_actually_uses_gos_to_select_ready_nodes(self):
        from gateway_pilot.graph_v3.orchestrator import acquire
        result=acquire(self.case,self.registry,self.state)
        self.assertEqual(result['upstream_kernel_calls'],result['calls'])
        self.assertTrue(self.state.fact('dns.probe'))
        for event in result['retrievals']:
            self.assertIn(event['selected_ready'],event['ready_set'])
            ranked=sorted(event['ready_set'],key=lambda fid:(-event['scores'].get('f:'+fid,0),self.registry.objective(fid),fid))
            self.assertEqual(event['selected_ready'],ranked[0])

    def test_missing_client_capability_is_explicit_partial_goal(self):
        from gateway_pilot.graph_v3.orchestrator import acquire
        c=copy.deepcopy(next(c for c in read_json(ROOT/'data/cases.json') if c['template']=='internet_unverified'))
        s=CaseState(c,self.registry,lambda:0)
        result=acquire(c,self.registry,s)
        self.assertIn('client.probe',result['unavailable_goals'])
        self.assertIn('client.probe',result['unverified_goals'])
        self.assertTrue(s.fact('wan.probe'))

    def test_microbench_is_prerequisite_recovery_not_llm_accuracy(self):
        from gateway_pilot.graph_v3.evaluate import microbench
        rows=microbench()
        self.assertEqual(sum(x['bundle_complete'] for x in rows if x['method']=='gos'),4)
        self.assertEqual(sum(x['bundle_complete'] for x in rows if x['method']=='bm25'),0)


if __name__=='__main__': unittest.main()
