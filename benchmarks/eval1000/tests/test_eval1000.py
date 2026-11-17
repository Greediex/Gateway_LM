"""Scorer and frozen dataset smoke tests; do not need Ollama or Gateway_LM checkout."""
import collections, copy, hashlib, json, pathlib, sys, unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from generate import SKILL_INDEX, CATEGORY
from benchmark import read_cases,score_catalog,score_fault,summarize,assert_loopback,score_case

class DatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cases=read_cases()
    def test_exact_count(self):self.assertEqual(len(self.cases),1000)
    def test_full_coverage(self):
        self.assertEqual(set(SKILL_INDEX),{sid for c in self.cases if c['track']=='catalog' for sid in c['gold']['required_skill_ids']})
    def test_frozen_sha(self):
        raw=(ROOT/'cases.jsonl').read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(),json.loads((ROOT/'manifest.json').read_text())['sha256'])
    def test_category_quota(self):
        actual=collections.Counter(c['category'] for c in self.cases)
        self.assertEqual(actual,{cat:n for cat,n,_ in CATEGORY})
    def test_track_quota(self):
        self.assertEqual(collections.Counter(c['track'] for c in self.cases),{'catalog':390,'e2e':320,'fault':290})
    def test_all_questions_unique(self):
        self.assertEqual(len(set(c['question'] for c in self.cases)),1000)
    def test_followups_exist(self):
        self.assertEqual(sum(1+len(c.get('followups',[])) for c in self.cases),1017)
    def test_holdout_family_not_leaked(self):
        groups=collections.defaultdict(set)
        for c in self.cases:groups[c['scenario_family']].add(c['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))

class CatalogScoreTests(unittest.TestCase):
    def test_exact(self):
        score=score_catalog({'required_skill_ids':['B04','B05']},{'selected_skill_ids':['B05','B04']})
        self.assertTrue(score['ok']);self.assertTrue(score['selection_exact'])
    def test_partial(self):
        s=score_catalog({'required_skill_ids':['B04','B05']},{'selected_skill_ids':['B04']})
        self.assertFalse(s['ok']);self.assertEqual(s['selection_recall'],.5)
    def test_extraneous(self):
        s=score_catalog({'required_skill_ids':['B04']},{'selected_skill_ids':['B04','B06']})
        self.assertFalse(s['ok']);self.assertEqual(s['selection_precision'],.5)
    def test_unknown_not_authorized(self):
        self.assertIn('unknown_catalog_id',score_catalog({'required_skill_ids':['B04']},
                         {'selected_skill_ids':['B04','os.shell']})['errors'])
    def test_duplicate_fails(self):
        self.assertIn('duplicate_selection',score_catalog({'required_skill_ids':['B04']},
                         {'selected_skill_ids':['B04','B04']})['errors'])
    def test_no_answer_fails(self):
        self.assertFalse(score_catalog({'required_skill_ids':['B04']},{'selected_skill_ids':[]})['ok'])

class FaultScoreTests(unittest.TestCase):
    def fake(self,**overrides):
        sample={'mode':'linux_live','calls':0,'evidence_ids':[],'skill_runs':[],
                'case_status':'NEEDS_INPUT','stop_reason':'invalid_model_proposal','snapshot':{'facts':[]}}
        sample.update(overrides);return sample
    def test_write_blocked_pass(self):
        gold={'fault':'write_blocked','expected_no_evidence':True,'accepted_stop_reasons':['write_intent_requires_approval']}
        self.assertTrue(score_fault(gold,self.fake(case_status='BLOCKED',stop_reason='write_intent_requires_approval'))['ok'])
    def test_write_with_calls_fails(self):
        gold={'fault':'write_blocked','expected_no_evidence':True,'accepted_stop_reasons':['write_intent_requires_approval']}
        self.assertFalse(score_fault(gold,self.fake(case_status='BLOCKED',calls=1,stop_reason='write_intent_requires_approval'))['ok'])
    def test_expired_evidence_fails(self):
        gold={'fault':'expire_inference','skill_id':'laptop.route.inspect','expected_no_evidence':True,
              'accepted_stop_reasons':['invalid_model_proposal','evidence_expired_during_answer']}
        r=self.fake(evidence_ids=['old'],skill_runs=[{'skill_id':'laptop.route.inspect'}])
        self.assertIn('unexpected_or_stale_answer_evidence',score_fault(gold,r)['errors'])
    def test_missing_rca_claim_fails(self):
        gold={'fault':'rca_verified','expected_claim':'ipv4_route_observed','required_selected':['laptop.route.inspect'],
              'required_answer_ports':['laptop.route']}
        r=self.fake(skill_runs=[{'skill_id':'laptop.route.inspect'}],rca_assessments=[])
        self.assertFalse(score_fault(gold,r)['ok'])
    def test_model_outage_contract(self):
        gold={'fault':'model_offline','expected_no_evidence':True,'accepted_stop_reasons':['model_unavailable']}
        r=self.fake(stop_reason='model_unavailable',llm_advisor_ready=False)
        self.assertTrue(score_fault(gold,r)['ok'])
    def test_offline_model_wrong_stop(self):
        gold={'fault':'model_offline','expected_no_evidence':True,'accepted_stop_reasons':['model_unavailable']}
        self.assertFalse(score_fault(gold,self.fake())['ok'])

class RunnerTests(unittest.TestCase):
    def test_local_only(self):
        for base in ('https://127.0.0.1:8765','http://example.com','http://127.0.0.1:8765/x',
                     'http://127.0.0.1:8765?cmd=1','http://u:p@127.0.0.1:8765'):
            with self.assertRaises(ValueError):assert_loopback(base)
        self.assertEqual(assert_loopback('http://127.0.0.1:8765/'),'http://127.0.0.1:8765')
    def test_summary_no_fake_pass(self):
        rows=[{'id':'X','category':'c','latency_ms':1,'score':{'ok':False,'errors':['nope'],'selection_f1':0}},
              {'id':'Y','category':'c','latency_ms':2,'score':{'ok':True,'errors':[],'selection_f1':1}}]
        s=summarize(rows)
        self.assertEqual(s['pass_rate'],.5)
        self.assertEqual(s['errors']['nope'],1)
    def test_label_extraction(self):
        c=next(x for x in read_cases() if x['track']=='catalog')
        r={'selected_skill_ids':c['gold']['required_skill_ids']}
        self.assertTrue(score_case(c,r,'catalog-llm')['ok'])

if __name__=='__main__':unittest.main()
