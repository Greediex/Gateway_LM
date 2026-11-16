"""Real v0.2 Core tests; run after non-destructive install into a v2 checkout.

Standalone package: explicitly skips, never falsely reports integration success.
"""
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
IN_REPO=all((ROOT/p).is_file() for p in (
    'gateway_pilot/command_catalog/validator.py',
    'gateway_pilot/command_catalog/runtime.py',
    'gateway_pilot/graph_v3/runner.py',
    'docs/contracts/catalog-v02/contract.schema.json'))

@unittest.skipUnless(IN_REPO,'requires actual Gateway_LM v2 checkout; not verified in standalone package')
class CoreIntegrationSmoke(unittest.TestCase):
    def test_v02_catalog_contracts_and_registry_builder(self):
        from scripts.validate_overlay_v2 import validate
        result=validate()
        self.assertTrue(result['contracts_valid'])
        self.assertEqual(result['functions'],72)
        self.assertEqual(result['skills'],72)
        self.assertFalse(result['execution_enabled'])

    def test_proposed_catalog_cannot_become_executable_by_pinning_hash(self):
        from tempfile import TemporaryDirectory
        from gateway_pilot.command_catalog.loader import load_catalog
        from gateway_pilot.command_catalog.builder import build_registry
        from gateway_pilot.command_catalog.compatibility import compile_registry
        from gateway_pilot.core import PlanError
        catalog = load_catalog(ROOT/'proposed_catalog_v02')
        policy = {'schema_version':'0.2.0','allowed_probe_ids':[f['capability_probe'] for f in catalog['functions']]}
        selection = {'schema_version':'0.2.0','kind':'selection',
                     'functions':{f['function_id']:f['version'] for f in catalog['functions']},
                     'ports':{p['port_id']:p['version'] for p in catalog['ports']}}
        with TemporaryDirectory() as tmp:
            artifact = build_registry(catalog,selection,policy,Path(tmp)/'registry.json')
            with self.assertRaisesRegex(PlanError,'runtime_read_lifecycle_required'):
                compile_registry(artifact,policy,approved_digest=artifact['content_digest'])
        self.assertTrue(all(f['lifecycle']=='PROPOSED' for f in catalog['functions']))

    def test_gateway_replay_through_shared_core(self):
        from scripts.core_replay_smoke_v2 import smoke
        result=smoke('expansion.radio_health')
        self.assertTrue(result['verified_fact_present'])
        self.assertTrue(result['used_existing_graph_runner'])
        self.assertFalse(result['operator_approved_for_real_network'])

    def test_client_replay_through_shared_core(self):
        from scripts.core_replay_smoke_v2 import smoke
        result=smoke('expansion.wireless_signal')
        self.assertTrue(result['verified_fact_present'])
        self.assertEqual(result['skill'],'B04')
        self.assertTrue(result['verified_identity_present'])
        self.assertEqual(result['core_calls'],2)

    def test_system_replay_through_shared_core(self):
        from scripts.core_replay_smoke_v2 import smoke
        result=smoke('expansion.services_health')
        self.assertTrue(result['verified_fact_present'])

if __name__=='__main__':unittest.main()
