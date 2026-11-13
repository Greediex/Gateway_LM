"""Pinned v0.1 digests and existing compile-time contract binding."""
import hashlib
import json
import unittest
from pathlib import Path

from gateway_pilot.core import PlanError, ROOT
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.planner import Compiler
from gateway_pilot.graph_v3.registry_v01 import load_registry
from gateway_pilot.graph_v3.runner import GraphRunner
from gateway_pilot.graph_v3.state import CaseState


class ContractCompatibilityTests(unittest.TestCase):
    def test_v01_registry_and_all_runtime_digests_match_pre_fnd01_snapshot(self):
        snapshot = json.loads((Path(__file__).parent / "fixtures/v01_contract_digests.json").read_text())
        self.assertEqual(hashlib.sha256((ROOT / "data/registry_v01.json").read_bytes()).hexdigest(),
                         snapshot["registry_sha256"])
        registry = load_registry()
        self.assertEqual({fid: f.digest() for fid, f in registry.functions.items()}, snapshot["functions"])

    def test_v01_version_or_timeout_change_cannot_execute_a_pinned_plan(self):
        for field, value in (("version", "99.0.0"), ("timeout_ms", 999)):
            with self.subTest(field=field):
                registry = GraphRegistry.from_v01()
                case = {"id": "contract-binding-test", "target": {"scope": "gateway"},
                        "capabilities": list(registry.functions), "permissions": ["network.read"], "world": {}}
                state = CaseState(case, registry)
                plan = Compiler(registry).compile(["wan.status"], state)
                original = registry.functions["wan.status"].digest()
                self.assertTrue(all(node.contract_digest == original for node in plan.nodes.values()))
                setattr(registry.functions["wan.status"], field, value)
                runner = GraphRunner(registry, case, state)
                with self.assertRaisesRegex(PlanError, "contract_changed_after_compile"):
                    runner.run(plan)
                self.assertEqual(state.evidence, [])


if __name__ == "__main__":
    unittest.main()
