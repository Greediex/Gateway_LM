"""Declarative, transactional read-only extension overlay regression tests.

New Function/Skill metadata is loaded from JSON; executable capability still
requires a separately assigned and probed Adapter. Ubus transport is mocked.
"""
from __future__ import annotations

import copy
import unittest

from gateway_pilot.adapters import CompositeAdapter, UbusReadAdapter, UbusReadBinding
from gateway_pilot.core import ROOT, PlanError, read_json
from gateway_pilot.graph_v3.extension_loader import install_extension
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.state import CaseState


class FakeUbus:
    def __init__(self):
        self.calls = []

    def probe(self, obj, method):
        return (obj, method) == ("gateway.sensor", "temperature")

    def read(self, obj, method, arguments):
        self.calls.append((obj, method, arguments))
        return {"celsius": 42.5}


class ExtensionLoaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.template = read_json(ROOT / "examples/extensions/gateway_temperature_read.json")
        cls.fixture = next(x for x in read_json(ROOT / "data/cases.json")
                           if x["template"] == "wan_healthy")

    def setUp(self):
        self.registry = GraphRegistry()
        self.manifest = copy.deepcopy(self.template)

    def test_legacy_registry_extension_executes_via_explicit_mock_adapter(self):
        receipt = install_extension(self.registry, self.manifest)
        self.assertEqual(receipt["status"], "METADATA_ONLY")
        self.assertEqual(receipt["functions"], ["gateway.temperature.read"])
        self.assertEqual(self.registry.functions["gateway.temperature.read"].skills, ("SK99",))
        self.assertIn("gateway.temperature", self.registry.ports)
        self.assertEqual(self.registry.ports["gateway.temperature"].provenance, "ubus/")
        self.assertIn("gateway.temperature.read", self.registry.legacy.functions)

        case = copy.deepcopy(self.fixture)
        case.pop("world", None)
        case["capabilities"].append("gateway.temperature.read")
        case["adapter"] = CompositeAdapter({
            "gateway.temperature.read": UbusReadAdapter(
                self.registry,
                {"gateway.temperature.read":
                 UbusReadBinding("gateway.sensor", "temperature")},
                transport := FakeUbus(),
            )
        })
        result = GoalAgent(self.registry, method="bm25").run(
            "Read gateway temperature", case, goals=("gateway.temperature",)
        )
        self.assertEqual(result["status"], "RESOLVED")
        self.assertEqual(result["calls"], 1)
        self.assertEqual(result["goal_facts"][0]["value"], {"celsius": 42.5})
        self.assertEqual(result["diagnosis"], "NOT_EVALUATED")
        self.assertEqual(transport.calls, [("gateway.sensor", "temperature", {})])

    def test_versioned_registry_installs_as_unverified_only(self):
        registry = GraphRegistry.from_v01()
        receipt = install_extension(registry, self.manifest)
        self.assertEqual(receipt["status"], "METADATA_ONLY")
        f = registry.functions["gateway.temperature.read"]
        self.assertEqual(f.status, "PROPOSED_NOT_VERIFIED")
        self.assertEqual(f.risk, "READ_ONLY")
        self.assertEqual(f.adapter, "openwrt_ubus")
        case = copy.deepcopy(self.fixture)
        case["capabilities"].append("gateway.temperature.read")
        state = CaseState(case, registry)
        self.assertNotIn(f.id, registry.eligible(state))
        self.assertFalse(registry.contract_allowed(f))
        self.assertIn(f.id, registry.legacy.functions)

    def test_manifest_never_enables_write_privilege(self):
        for forbidden in (
            {"risk": "WRITE"},
            {"status": "PROBED_OK"},
            {"adapter": "python.exec"},
            {"command": "reboot"},
        ):
            with self.subTest(forbidden=forbidden):
                manifest = copy.deepcopy(self.manifest)
                manifest["functions"][0].update(forbidden)
                original = set(self.registry.functions)
                with self.assertRaisesRegex(PlanError, "extension_invalid_fields"):
                    install_extension(self.registry, manifest)
                self.assertEqual(set(self.registry.functions), original)

    def test_duplicate_id_never_overwrites_existing_function_or_port(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["ports"][0]["id"] = "wan.status"
        with self.assertRaisesRegex(PlanError, "extension_duplicate_or_overwrite"):
            install_extension(self.registry, manifest)
        self.assertNotIn("SK99", self.registry.skills)
        self.assertNotIn("gateway.temperature.read", self.registry.functions)

    def test_external_schema_ref_and_open_property_schema_rejected(self):
        for mutate, reason in (
            (lambda p: p["schema"].update({"$ref": "https://example.net/external"}),
             "extension_remote_schema_references_forbidden"),
            (lambda p: p["schema"].update({"additionalProperties": True}),
             "extension_requires_closed_schema"),
        ):
            with self.subTest(reason=reason):
                manifest = copy.deepcopy(self.manifest)
                mutate(manifest["ports"][0])
                with self.assertRaisesRegex(PlanError, reason):
                    install_extension(self.registry, manifest)
                self.assertEqual(self.registry._registry_revision, 1)

    def test_failed_skill_cycle_is_transactional(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["skills"][0]["depends_on"] = ["SK99"]
        old_revision = self.registry._registry_revision
        with self.assertRaises(PlanError):
            install_extension(self.registry, manifest)
        self.assertEqual(self.registry._registry_revision, old_revision)
        self.assertNotIn("SK99", self.registry.skills)
        self.assertNotIn("gateway.temperature", self.registry.ports)

    def test_manifest_with_unknown_skill_or_new_capability_rejected(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["functions"][0]["skills"] = ["SK_NOT_REGISTERED"]
        with self.assertRaisesRegex(PlanError, "extension_invalid_id|extension_unknown_skill_membership"):
            install_extension(self.registry, manifest)
        manifest = copy.deepcopy(self.manifest)
        manifest["functions"][0]["inputs"] = ["wan.status"]
        with self.assertRaisesRegex(PlanError, "extension_requires_zero_input_single_output"):
            install_extension(self.registry, manifest)

    def test_extension_receipt_has_digest_and_revision_increases(self):
        old = self.registry._registry_revision
        receipt = install_extension(self.registry, self.manifest)
        self.assertEqual(len(receipt["digest_sha256"]), 64)
        self.assertEqual(self.registry._registry_revision, old + 1)
        with self.assertRaisesRegex(PlanError, "extension_duplicate_or_overwrite"):
            install_extension(self.registry, self.manifest)
        self.assertEqual(len(self.registry.extension_history), 1)


if __name__ == "__main__":
    unittest.main()
