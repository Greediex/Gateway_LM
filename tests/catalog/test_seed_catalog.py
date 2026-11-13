"""FND-02: checked-in READ seed catalog, never a runtime directory loader."""
import copy
import json
import unittest

from gateway_pilot.command_catalog.contracts import validate_contract
from gateway_pilot.core import PlanError, ROOT
from gateway_pilot.graph_v3.contracts import schema_subset, validate


CATALOG = ROOT / "catalog"


def documents(folder):
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted((CATALOG / folder).rglob("*.json"))]


class SeedCatalogTests(unittest.TestCase):
    def setUp(self):
        self.functions = documents("functions")
        self.ports = documents("ports")
        self.skills = documents("skills")

    def test_seed_inventory_is_small_unique_and_locally_valid(self):
        self.assertEqual((len(self.functions), len(self.ports), len(self.skills)), (3, 3, 2))
        for rows, key in ((self.functions, "function_id"), (self.ports, "port_id"), (self.skills, "skill_id")):
            identities = [(row[key], row["version"]) for row in rows]
            self.assertEqual(len(identities), len(set(identities)))
            for row in rows:
                with self.subTest(key=row[key]):
                    validate_contract(row)
        for path in (CATALOG / "functions").rglob("*.json"):
            self.assertEqual(path.parent.name, json.loads(path.read_text())["domain"])
        self.assertEqual({row["domain"] for row in self.functions}, {"clients", "wifi", "lan"})

    def test_all_ports_skills_and_argument_fields_resolve_with_exact_versions(self):
        ports = {(p["port_id"], p["version"]): p for p in self.ports}
        skills = {(s["skill_id"], s["version"]): s for s in self.skills}
        for f in self.functions:
            for pid, version in {**f["inputs"], **f["outputs"]}.items():
                self.assertIn((pid, version), ports)
                self.assertEqual(ports[pid, version]["scope"], f["scope"])
            for ref in f["skill_refs"]:
                skill = skills[ref["skill_id"], ref["version"]]
                self.assertEqual(skill["function_refs"][f["function_id"]], f["version"])
            for argument, (pid, field) in f["argument_sources"].items():
                source = ports[pid, f["inputs"][pid]]["schema"]["properties"][field]
                self.assertTrue(schema_subset(source, f["arguments_schema"]["properties"][argument]))

    def test_identity_and_connectivity_skill_are_shared_across_domains(self):
        consumers = [f for f in self.functions if "client.identity" in f["inputs"]]
        producers = [f for f in self.functions if "client.identity" in f["outputs"]]
        self.assertEqual(len(producers), 1)
        self.assertEqual({f["domain"] for f in consumers}, {"wifi", "lan"})
        shared = set.intersection(*({(s["skill_id"], s["version"]) for s in f["skill_refs"]} for f in consumers))
        self.assertTrue(shared)
        functions = {f["function_id"]: f for f in self.functions}
        ports = {p["port_id"]: p for p in self.ports}
        for skill in self.skills:
            for fid, version in skill["function_refs"].items():
                f = functions[fid]
                self.assertEqual(f["version"], version)
                self.assertIn({"skill_id": skill["skill_id"], "version": skill["version"]}, f["skill_refs"])
            for pid, version in {**skill["requires"], **skill["produces"]}.items():
                self.assertEqual(ports[pid]["version"], version)

    def test_selection_pins_exactly_the_seed_inventory(self):
        selection = json.loads((ROOT / "config/catalog_selection.example.json").read_text())
        validate_contract(selection)
        self.assertEqual(selection["functions"], {f["function_id"]: f["version"] for f in self.functions})
        self.assertEqual(selection["ports"], {p["port_id"]: p["version"] for p in self.ports})

    def test_seed_does_not_advertise_execution_or_live_hardware_support(self):
        self.assertTrue(self.functions)
        for f in self.functions:
            self.assertEqual(f["risk"], "READ_ONLY")
            self.assertEqual(f["permission"], "network.read")
            self.assertEqual(f["lifecycle"], "PROPOSED")
            self.assertEqual(f["effects"], [])
        self.assertTrue(all(p["provenance"] == "synthetic_replay/" for p in self.ports))
        self.assertFalse((CATALOG / "bindings").exists())
        self.assertFalse((ROOT / "data/registry_v02.json").exists())

    def test_tightening_legacy_schemas_has_explicit_major_versions(self):
        old = json.loads((ROOT / "data/registry_v01.json").read_text())
        old_functions = {f["function_id"]: f for f in old["functions"]}
        for f in self.functions:
            self.assertEqual(f["version"], "4.0.0")
            self.assertEqual(old_functions[f["function_id"]]["version"], "3.0.0")
        for p in self.ports:
            self.assertEqual(p["version"], "2.0.0")
            self.assertFalse(p["schema"]["additionalProperties"])
            self.assertTrue(old["ports"][p["port_id"]]["schema"]["additionalProperties"])
        # Never relabel nmcli signal percent as the RSSI dBm expected here.
        wifi = next(p for p in self.ports if p["port_id"] == "wifi.station")
        self.assertTrue(validate({"associated": True, "rssi_dbm": -60}, wifi["schema"]))
        self.assertFalse(validate({"associated": True, "signal_pct": 80}, wifi["schema"]))

    def test_skill_contract_rejects_runtime_rights_and_invalid_local_references(self):
        self.assertTrue(self.skills)
        for changes in ({"permission": "network.write"}, {"status": "PROBED_OK"},
                        {"function_refs": {"wifi.station": "latest"}},
                        {"completion_ports": {"missing.port": "1.0.0"}},
                        {"required_capabilities": ["wifi.station"]},
                        {"write_set": ["wifi.station"]}):
            with self.subTest(changes=changes):
                skill = copy.deepcopy(self.skills[0])
                skill.update(changes)
                with self.assertRaisesRegex(PlanError, "invalid_contract_v02:"):
                    validate_contract(skill)


if __name__ == "__main__":
    unittest.main()
