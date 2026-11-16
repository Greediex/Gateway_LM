"""CAT-01 profile selection is metadata, never execution approval."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from gateway_pilot.core import PlanError
from gateway_pilot.command_catalog.compatibility import compile_registry
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.skill_expansion.profiles import (
    DEFAULT_PROFILE, audit_mappings, build_profile, coverage_report, load_bundle, validate_profile)


class SkillProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = load_bundle()
        cls.pinned = read_json(DEFAULT_PROFILE)

    def setUp(self):
        self.bundle = copy.deepcopy(self.original)
        self.profile = copy.deepcopy(self.pinned)

    def test_all_120_mappings_and_known_gaps_are_explicit(self):
        r = coverage_report(self.profile, self.bundle)
        self.assertEqual(len(r['mapping_rows']),120)
        self.assertEqual(r['coverage']['legacy_references'],8)
        self.assertEqual(r['coverage']['direct_read_proposals'],72)
        self.assertEqual(r['coverage']['composite_without_direct_function'],40)
        self.assertEqual(r['gap_counts']['CLIENT_IDENTITY_DEPENDENCY_NOT_DECLARED'],5)
        self.assertEqual(r['gap_counts']['CROSS_SCOPE_AGGREGATION_REQUIRED'],9)
        self.assertEqual(sum(row['selected_for_cat02'] for row in r['mapping_rows']),3)
        self.assertEqual(r['coverage']['current_profile_replay_verified'],0)
        self.assertEqual(r['coverage']['current_profile_live_verified'],0)
        self.assertEqual(r['coverage']['runtime_bindings'],0)
        self.assertFalse(r['execution_enabled'])

    def test_exact_batch_build_is_deterministic_and_still_proposed(self):
        with tempfile.TemporaryDirectory() as folder:
            a,r1 = build_profile(self.profile,self.bundle,Path(folder)/'one.json')
            b,r2 = build_profile(self.profile,self.bundle,Path(folder)/'two.json')
            self.assertEqual((Path(folder)/'one.json').read_bytes(),(Path(folder)/'two.json').read_bytes())
            self.assertEqual(r1,r2)
            self.assertEqual({f['function_id'] for f in a['functions']},
                {'expansion.radio_health','expansion.ssid_config','expansion.airtime_usage'})
            self.assertTrue(all(f['lifecycle']=='PROPOSED' for f in a['functions']))
            with self.assertRaisesRegex(PlanError,'runtime_read_lifecycle_required'):
                compile_registry(a,self.bundle['policy'],approved_digest=a['content_digest'])

    def test_duplicate_missing_and_foreign_mapping_rejected(self):
        for mutation in ('duplicate','missing','foreign'):
            bundle = copy.deepcopy(self.bundle)
            if mutation == 'duplicate': bundle['mapping'][1] = copy.deepcopy(bundle['mapping'][0])
            elif mutation == 'missing': bundle['mapping'].pop()
            else: bundle['mapping'][0]['skill_id'] = 'ZZ99'
            with self.subTest(mutation=mutation), self.assertRaises(PlanError):
                audit_mappings(bundle)

    def test_mapping_cannot_grant_execution_or_change_identity(self):
        for key,value in [('runtime_enabled',True),('suggestions_are_bindings',True),
                          ('requires_operator_review',False),('catalog_skill_id','gateway.other'),('domain','Z')]:
            bundle = copy.deepcopy(self.bundle);bundle['mapping'][0][key] = value
            with self.subTest(key=key), self.assertRaises(PlanError):
                audit_mappings(bundle)

    def test_dangling_function_and_wrong_mapping_scope_rejected(self):
        row = next(r for r in self.bundle['mapping'] if r['skill_id']=='B02')
        row['declared_v02_function_refs'] = ['expansion.unknown']
        with self.assertRaisesRegex(PlanError,'mapping_function_refs'):
            audit_mappings(self.bundle)
        self.bundle = copy.deepcopy(self.original)
        row = next(r for r in self.bundle['mapping'] if r['skill_id']=='B02')
        row['evidence_scope_set'] = ['client']
        with self.assertRaisesRegex(PlanError,'mapping_scope_claim'):
            audit_mappings(self.bundle)

    def test_multiple_function_versions_are_ambiguous_for_unversioned_design_mapping(self):
        f = copy.deepcopy(next(f for f in self.bundle['catalog']['functions'] if f['function_id']=='expansion.radio_health'))
        f['version']='2.0.0';f['skill_refs'][0]['version']='2.0.0'
        skill = copy.deepcopy(next(s for s in self.bundle['catalog']['skills'] if s['skill_id']=='gateway.b02'))
        skill['version']='2.0.0';skill['function_refs'][f['function_id']]='2.0.0'
        self.bundle['catalog']['functions'].append(f);self.bundle['catalog']['skills'].append(skill)
        with self.assertRaisesRegex(PlanError,'ambiguous_function_version'):
            audit_mappings(self.bundle)

    def test_selection_version_digest_and_source_drift_fail_closed(self):
        for field in ('version','digest','source'):
            profile = copy.deepcopy(self.profile)
            if field=='version': profile['selection']['functions']['expansion.radio_health']='99.0.0'
            elif field=='digest': profile['contract_digests']['functions']['expansion.radio_health@1.0.0']='0'*64
            else: profile['source_bundle_digest']='0'*64
            with self.subTest(field=field), self.assertRaises(PlanError):
                validate_profile(profile,self.bundle)

    def test_cross_scope_and_real_target_policy_are_denied(self):
        self.profile['scope']='client'
        self.profile['target_policy']['scope']='client'
        with self.assertRaisesRegex(PlanError,'profile_scope_mismatch'):
            validate_profile(self.profile,self.bundle)
        self.profile = copy.deepcopy(self.pinned)
        self.profile['target_policy']['target_id_prefix']='real-router-'
        with self.assertRaisesRegex(PlanError,'profile_target_policy'):
            validate_profile(self.profile,self.bundle)

    def test_client_identity_gap_blocks_selection(self):
        p = self.profile
        p['scope']='client';p['target_policy']['scope']='client'
        p['skill_refs']={'B04':{'skill_id':'gateway.b04','version':'1.0.0'}}
        p['selection']['functions']={'expansion.wireless_signal':'1.0.0'}
        p['selection']['ports']={'expansion.wireless_signal':'1.0.0'}
        with self.assertRaisesRegex(PlanError,'profile_identity_unresolved'):
            validate_profile(p,self.bundle)

    def test_graph_affinity_never_becomes_typed_dependency(self):
        r = coverage_report(self.profile,self.bundle)
        self.assertEqual(len(r['edge_reviews']),203)
        self.assertTrue(all(not e['runtime_approved'] and e['decision']=='NOT_APPLIED' for e in r['edge_reviews']))
        edge = next(e for e in r['edge_reviews'] if e['source']=='B05' and e['target']=='B06')
        self.assertEqual(edge['typed_witnesses'],[])
        self.assertEqual(edge['reason'],'NO_TYPED_WITNESS')
        self.assertTrue(all(not deps for deps in r['dependency_indexes']['dependencies'].values()))
        self.profile['edge_policy']='PROMOTE_PROPOSED'
        with self.assertRaisesRegex(PlanError,'unapproved_graph_policy'):
            validate_profile(self.profile,self.bundle)

    def test_bad_dependency_or_completion_is_not_inferred_from_graph(self):
        f = next(f for f in self.bundle['catalog']['functions'] if f['function_id']=='expansion.radio_health')
        f['inputs']['expansion.ssid_config']='99.0.0'
        with self.assertRaises(PlanError):
            validate_profile(self.profile,self.bundle)
        self.bundle = copy.deepcopy(self.original)
        skill = next(s for s in self.bundle['catalog']['skills'] if s['skill_id']=='gateway.b02')
        skill['completion_ports']={'foreign.port':'1.0.0'}
        with self.assertRaises(PlanError):
            validate_profile(self.profile,self.bundle)

    def test_foreign_fields_or_backend_do_not_register_code(self):
        for key,value in [('enabled',True),('execution_edges',[]),('backend',{'module':'os.system'})]:
            p = copy.deepcopy(self.profile);p[key]=value
            with self.subTest(key=key), self.assertRaises(PlanError):
                validate_profile(p,self.bundle)

    def test_cli_exports_metadata_without_runtime(self):
        from scripts.skill_profiles import main
        from contextlib import redirect_stdout
        from io import StringIO
        with tempfile.TemporaryDirectory() as folder, redirect_stdout(StringIO()) as output:
            self.assertEqual(main(['--registry-output',str(Path(folder)/'registry.json')]),0)
            report = json.loads(output.getvalue())
            self.assertFalse(report['execution_enabled'])
            self.assertEqual(report['coverage']['selected_skills'],3)

    def test_selected_contract_mutation_or_live_provenance_is_not_accepted(self):
        for mutation in ('contract','source'):
            b = copy.deepcopy(self.bundle)
            if mutation=='contract':
                next(f for f in b['catalog']['functions'] if f['function_id']=='expansion.radio_health')['description']='changed'
            else:
                next(p for p in b['catalog']['ports'] if p['port_id']=='expansion.radio_health')['provenance']='linux_client/'
            with self.subTest(mutation=mutation), self.assertRaises(PlanError):
                validate_profile(self.profile,b)
