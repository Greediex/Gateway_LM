"""Offline regression + negative gates. Real repo v0.2 validation is separate."""
from __future__ import annotations
import hashlib,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from gateway_pilot.skill_expansion.catalog import SkillCatalog
from gateway_pilot.skill_expansion.edge_gate import analyze
from gateway_pilot.skill_expansion.replay_backend import StrictSkillReplayBackend, ReplayFixtureError
from gateway_pilot.skill_expansion.runtime_bridge import RuntimeSkillBridge,SkillNotReady
from gateway_pilot.skill_expansion.repo_audit import audit,AuditError

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/skill_expansion_v1'

def read(name):return json.loads((DATA/name).read_text(encoding='utf-8'))

def port_documents():
    return [json.loads(f.read_text(encoding='utf-8')) for f in (ROOT/'proposed_catalog_v02/ports').glob('*.json')]

class GraphReviewTests(unittest.TestCase):
    def test_all_120_mapped(self):
        mapping=read('skill_function_mapping_120.json')
        self.assertEqual(len(mapping),120)
        self.assertEqual(len({x['skill_id'] for x in mapping}),120)
        self.assertEqual({x['skill_id'] for x in mapping},set(SkillCatalog.load().skills))
    def test_all_40_composites_have_evidence_suggestions(self):
        rows=read('skill_function_mapping_120.json')
        composite=[r for r in rows if r['proposal_mode']=='NO_DIRECT_READ_FUNCTION']
        self.assertEqual(len(composite),40)
        known={f['function_id'] for f in read('function_proposals.json')}
        for row in composite:
            self.assertTrue(row['suggested_evidence_functions'],row['skill_id'])
            self.assertTrue(set(row['suggested_evidence_functions']) <= known)
            self.assertFalse(row['suggestions_are_bindings'])
            self.assertTrue(row['requires_claim_or_workflow_definition'])
    def test_cross_scope_compositions_flagged(self):
        rows=read('skill_function_mapping_120.json')
        self.assertEqual(sum(x['cross_scope_aggregation'] for x in rows),9)
        self.assertTrue(all(len(x['evidence_scope_set'])>1 for x in rows if x['cross_scope_aggregation']))
    def test_all_unapproved(self):
        mapping=read('skill_function_mapping_120.json')
        self.assertTrue(all(not x['runtime_enabled'] and x['requires_operator_review'] for x in mapping))
    def test_72_real_shapes_in_proposed_metadata(self):
        funcs=read('function_proposals.json')
        self.assertEqual(len(funcs),72)
        self.assertEqual(len({x['function_id'] for x in funcs}),72)
        self.assertTrue(all(x['risk']=='READ_ONLY' and x['lifecycle']=='PROPOSED' and x['effects']==[] for x in funcs))
        self.assertTrue(all(len(x['outputs'])==1 for x in funcs))
    def test_metadata_files_coherent(self):
        funcs=read('function_proposals.json');p=port_documents()
        self.assertEqual(len(p),72)
        expected={f['function_id'] for f in funcs}
        filenames={f.name.removesuffix('.json') for f in (ROOT/'proposed_catalog_v02/functions/skill_expansion').glob('*.json')}
        self.assertEqual(expected,filenames)
        self.assertEqual({next(iter(f['outputs'])) for f in funcs},{r['port_id'] for r in p})
    def test_graph_precheck_no_autoapprove(self):
        out=analyze(SkillCatalog.load())
        self.assertEqual(out['total_edges'],206)
        self.assertEqual(sum(r['source_status']=='PROPOSED' for r in out['edges']),203)
        self.assertFalse(out['can_import_into_runtime']);self.assertFalse(out['reviewed_by_operator'])
        self.assertTrue(all(row['runtime_approved'] is False for row in out['edges']))
    def test_proposed_catalog_ids_v02_compatible(self):
        import re
        p=re.compile(r'^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$')
        for f in read('function_proposals.json'):
            self.assertTrue(p.fullmatch(f['function_id']))
            self.assertTrue(p.fullmatch(f['skill_refs'][0]['skill_id']))

class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.backend=StrictSkillReplayBackend(read('function_proposals.json'),port_documents(),read('replay_fixtures_v2.json'))
        self.context=SimpleNamespace(scope='gateway',target_id='synthetic-router',environment_id='a'*64)
        self.f=next(x for x in read('function_proposals.json') if x['function_id']=='expansion.radio_health')
    def test_replay_all_fixtures_schema_valid(self):
        self.assertEqual(len(self.backend._fixture),72)
    def test_synthetic_support_gate(self):
        self.assertTrue(self.backend.supports(self.f['function_id'],self.context))
        self.context.target_id='real-router'
        self.assertFalse(self.backend.supports(self.f['function_id'],self.context))
    def test_wrong_scope_fail_closed(self):
        self.context.scope='client'
        self.assertFalse(self.backend.supports(self.f['function_id'],self.context))
    def test_missing_function_fail_closed(self):
        self.assertFalse(self.backend.supports('expansion.missing',self.context))
    def test_no_arbitrary_args(self):
        with self.assertRaises(ReplayFixtureError):
            self.backend.sample_preview(self.f,{'shell':'true'},self.context)
    def test_row_fidelity(self):
        row=self.backend.sample_preview(self.f,{},self.context)[0]
        self.assertEqual(row['port'],'expansion.radio_health')
        self.assertEqual(row['scope'],'gateway')
        self.assertEqual(row['source'],self.backend.source)
        self.assertEqual(row['target'],'synthetic-router')
        self.assertEqual(row['ttl_s'],30)
        self.assertEqual(row['value']['channel'],0)
    def test_tampered_metadata_rejected(self):
        f=dict(self.f);f['description']='tampered'
        with self.assertRaises(ReplayFixtureError):self.backend.sample_preview(f,{},self.context)
    def test_partial_fixture_rejected(self):
        fixtures=read('replay_fixtures_v2.json');fixtures.pop('expansion.radio_health')
        # absent fixture must return unsupported, never fabricate results
        b=StrictSkillReplayBackend(read('function_proposals.json'),port_documents(),fixtures)
        self.assertFalse(b.supports(self.f['function_id'],self.context))
    def test_wrong_value_type_rejected(self):
        fixtures=read('replay_fixtures_v2.json')
        fixtures[self.f['function_id']]['expansion.radio_health']['channel']='bad'
        with self.assertRaises(ReplayFixtureError):
            StrictSkillReplayBackend(read('function_proposals.json'),port_documents(),fixtures)

class RuntimeGateTests(unittest.TestCase):
    def setUp(self):
        self.clock=[100]
        self.f=SimpleNamespace(id='expansion.radio_health',skills=('gateway.b02',),
                                outputs={'expansion.radio_health':object()},scope='gateway',
                                version='1.0.0',metadata_digest='z'*64,permission='network.read')
        self.registry=SimpleNamespace(contract_format='v0.2',catalog_digest='a'*64,
                                      skills={'gateway.b02':{'completion_ports':['expansion.radio_health']}},
                                      functions={self.f.id:self.f})
        self.ctx=SimpleNamespace(scope="gateway")
        self.rt=SimpleNamespace(registry=self.registry,context=self.ctx,
                                permissions=frozenset({'network.read'}),policy_context_id='p'*64,
                                _clock=lambda:self.clock[0])
        self.called=[]
        self.rt.execute=lambda goals,**kwargs:self.called.append((goals,kwargs)) or ('runner','plan')
        self.bridge=RuntimeSkillBridge(self.rt)
        self.snap=SimpleNamespace(registry_digest='a'*64,context=self.ctx,
             permissions=self.rt.permissions,policy_context_id=self.rt.policy_context_id,
             functions=[SimpleNamespace(function_id=self.f.id,status='AVAILABLE',
                        version=self.f.version,metadata_digest=self.f.metadata_digest)],
             checked_at=99,expires_at=110)
    def test_selected_skill_can_use_only_core(self):
        p=self.bridge.plan('B02',snapshot=self.snap)
        self.assertEqual(p.goals,('expansion.radio_health',))
        self.assertEqual(self.bridge.execute('B02',snapshot=self.snap),('runner','plan'))
        self.assertEqual(self.called[0][0],('expansion.radio_health',))
    def test_unregistered_proposed_rejected(self):
        with self.assertRaises(SkillNotReady):self.bridge.plan('A02',snapshot=self.snap)
    def test_no_snapshot_rejected(self):
        with self.assertRaises(SkillNotReady):self.bridge.plan('B02')
    def test_bad_capability_rejected(self):
        self.snap.functions[0].status='UNSUPPORTED'
        with self.assertRaises(SkillNotReady):self.bridge.plan('B02',snapshot=self.snap)
    def test_wrong_context_rejected(self):
        self.snap.context=object()
        with self.assertRaises(SkillNotReady):self.bridge.plan('B02',snapshot=self.snap)
    def test_expired_lease_rejected(self):
        self.clock[0]=111
        with self.assertRaises(SkillNotReady):self.bridge.plan('B02',snapshot=self.snap)
    def test_no_completion_port_rejected(self):
        self.registry.skills['gateway.b02']['completion_ports']=[]
        with self.assertRaises(SkillNotReady):self.bridge.plan('B02',snapshot=self.snap)
    def test_no_skipping_v01_gate(self):
        self.registry.contract_format='v0.1'
        with self.assertRaises(SkillNotReady):self.bridge.plan('B02',snapshot=self.snap)
    def test_call_budget_checked(self):
        with self.assertRaises(ValueError):self.bridge.execute('B02',snapshot=self.snap,max_calls=0)

class RepositoryAuditTests(unittest.TestCase):
    def test_fixture_checkout_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir();(root/'gateway_pilot/graph_v3').mkdir(parents=True)
            (root/'gateway_pilot/graph_v3/graphs.py').write_text('# fixture only')
            s=[{'skill_id':id} for id in ['SK01','SK02','SK03','SK04','SK05','SK08','SK09','SK13']]
            f=[{'function_id':f'legacy.test_{i}', 'skill_ids':[s[i%8]['skill_id']]} for i in range(17)]
            e=[{'source':'SK02','target':'SK01','type':'depends_on'},
               {'source':'SK03','target':'SK01','type':'depends_on'},
               {'source':'SK04','target':'SK05','type':'composes_with'}]
            (root/'data/registry_v01.json').write_text(json.dumps({'skills':s,'functions':f,'relations':e}))
            report=audit(root)
            self.assertEqual(report['registry_v01_skills'],8)
            self.assertEqual(report['registry_v01_functions'],17)
            self.assertEqual(report['proposal_skills'],120)
            self.assertTrue(report['does_not_change_runtime'])
    def test_missing_repo_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(AuditError):audit(tmp)

if __name__=='__main__':unittest.main()
