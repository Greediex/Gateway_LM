"""FND-01: standalone metadata contracts, not execution authorization."""
import copy
import json
import unittest

from jsonschema import Draft202012Validator

from gateway_pilot.command_catalog.contracts import validate_contract
from gateway_pilot.core import PlanError, ROOT
from gateway_pilot.graph_v3.contracts import schema_subset, validate


CONTRACTS = ROOT / "docs/contracts/catalog-v02"


class ContractSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vectors = json.loads((CONTRACTS / "examples.json").read_text())

    def changed(self, kind, **changes):
        row = copy.deepcopy(self.vectors[kind])
        row.update(changes)
        return row

    def reject(self, row):
        with self.assertRaisesRegex(PlanError, "invalid_contract_v02:"):
            validate_contract(row)

    def test_schema_is_valid_and_all_examples_pass_without_mutation(self):
        schema = json.loads((CONTRACTS / "contract.schema.json").read_text())
        Draft202012Validator.check_schema(schema)
        before = copy.deepcopy(self.vectors)
        for name, row in self.vectors.items():
            with self.subTest(name=name):
                self.assertIsNone(validate_contract(row))
        self.assertEqual(self.vectors, before)

    def test_required_function_fields_are_not_defaulted(self):
        schema = json.loads((CONTRACTS / "contract.schema.json").read_text())
        for key in schema["$defs"]["function"]["required"]:
            with self.subTest(key=key):
                row = self.changed("function")
                del row[key]
                self.reject(row)

    def test_ids_and_exact_semver_references(self):
        for fid in ("wifi", "Wifi.read", "wifi..read", "wifi.read\n", "wifi.read;id", "w." + "x" * 100):
            with self.subTest(fid=fid):
                self.reject(self.changed("function", function_id=fid))
        for version in ("latest", "^1.0.0", "1.0", "01.0.0", "1.0.0\n", "1.0.0-01"):
            with self.subTest(version=version):
                self.reject(self.changed("function", version=version))
                self.reject(self.changed("function", inputs={"client.identity": version}))
        validate_contract(self.changed("function", version="1.0.0-rc.1+build.4"))

    def test_unknown_authority_and_executable_fields_are_rejected(self):
        for changes in ({"permission": "admin.all"}, {"risk": "READ"}, {"scope": "host"},
                        {"verifier": "custom.verifier"}, {"adapter": "linux"},
                        {"status": "PROBED_OK"}, {"capabilities": ["wifi.read"]},
                        {"command": "nmcli device show"}, {"source": "code.py"}):
            with self.subTest(changes=changes):
                self.reject(self.changed("function", **changes))

    def test_budget_and_retry_bounds(self):
        for key, bad_values in {
            "timeout_ms": (0, -1, True, 60001, float("nan"), float("inf")),
            "ttl_seconds": (0, -1, True, 86401),
            "cost": (-1, True, float("-inf")),
            "latency_ms": (-1, True),
        }.items():
            for value in bad_values:
                with self.subTest(key=key, value=value):
                    self.reject(self.changed("function", **{key: value}))
        for attempts in (0, 5, 1.5, True):
            self.reject(self.changed("function", retry={"max_attempts": attempts}))
        for attempts in (1, 4):
            validate_contract(self.changed("function", retry={"max_attempts": attempts}))

    def test_argument_bindings_and_predicate_local_references(self):
        self.reject(self.changed("function", argument_sources={"client_id": ["other.identity", "client_id"]}))
        self.reject(self.changed("function", argument_sources={"unknown": ["client.identity", "client_id"]}))
        self.reject(self.changed("function", argument_sources={}))
        self.reject(self.changed("function", preconditions=[{
            "port": "other.identity", "field": "client_id", "op": "exists", "value": True}]))
        self.reject(self.changed("function", preconditions=[{
            "port": "client.identity", "field": "client_id", "op": "gt", "value": True}]))
        self.reject(self.changed("function", order_after=[self.vectors["function"]["function_id"]]))
        self.reject(self.changed("function", effects=["missing.port"]))

    def test_write_is_design_metadata_with_no_retry_or_read_permission(self):
        row = self.changed("function", risk="WRITE", permission="network.write")
        validate_contract(row)
        row["retry"] = {"max_attempts": 2}
        self.reject(row)
        self.reject(self.changed("function", risk="WRITE"))
        self.reject(self.changed("function", permission="network.write"))
        self.reject(self.changed("function", effects=["client.wifi.link"]))
        validate_contract(self.changed("function", risk="PROBE"))

    def test_lifecycle_does_not_contain_runtime_availability_or_approval(self):
        for lifecycle in ("PROPOSED", "IMPLEMENTED", "VERIFIED", "DEPRECATED", "RETIRED"):
            validate_contract(self.changed("function", lifecycle=lifecycle))
        for lifecycle in ("AVAILABLE", "PROBED_OK", "PERMISSION_DENIED"):
            self.reject(self.changed("function", lifecycle=lifecycle))
        self.reject(self.changed("function", verified_on_hardware=True))

    def test_payload_schema_subset_and_local_consistency(self):
        for keyword, value in (("$ref", "https://example.org/schema"),
                               ("$ref", "#/$defs/hidden"), ("allOf", []), ("pattern", "x")):
            row = self.changed("port")
            row["schema"]["properties"]["associated"][keyword] = value
            self.reject(row)
        for schema in (
            {"type": "object", "properties": {}, "required": ["missing"], "additionalProperties": False},
            {"type": "number", "minimum": 10, "maximum": 1},
            {"type": "string", "minLength": 10, "maxLength": 1},
            {"type": "string", "enum": [1]},
            {"type": "string", "format": "ipv4", "const": "not-an-ip"},
            {"type": "string", "format": "ipv4", "enum": ["not-an-ip"]},
            {"type": "array"},
            {"type": "string", "properties": {}},
        ):
            row = self.changed("port")
            row["schema"]["properties"]["associated"] = schema
            self.reject(row)
        row = self.changed("port")
        row["schema"]["additionalProperties"] = True
        self.reject(row)

    def test_empty_outputs_duplicate_references_and_selection_versions(self):
        self.reject(self.changed("function", outputs={}))
        self.reject(self.changed("function", skill_refs=[{"skill_id": "SK01", "version": "1.0.0"}] * 2))
        self.reject(self.changed("function", skill_refs=[
            {"skill_id": "SK01", "version": "1.0.0"}, {"skill_id": "SK01", "version": "2.0.0"}]))
        row = self.changed("selection")
        row["functions"]["client.wifi.read"] = ["1.0.0", "2.0.0"]
        self.reject(row)
        row["functions"]["client.wifi.read"] = "latest"
        self.reject(row)

    def test_document_size_depth_and_json_types(self):
        self.reject(self.changed("function", description="x" * 2049))
        self.reject(self.changed("function", description=" " * 4))
        self.reject(self.changed("function", cost=complex(1, 2)))
        row = self.changed("port")
        row["schema"]["properties"]["associated"]["const"] = float("nan")
        self.reject(row)
        row = self.changed("port")
        node = row["schema"]
        for _ in range(21):
            node["properties"] = {"nested": {"type": "object"}}
            node = node["properties"]["nested"]
        self.reject(row)
        self.reject(self.changed("function", description="x" * 70000))

    def test_reference_paths_and_finite_schema_bounds(self):
        self.reject(self.changed("function", preconditions=[{
            "port": "client.identity", "field": "", "op": "eq", "value": True}]))
        row = self.changed("port")
        row["schema"]["properties"] = {"dotted.name": {"type": "string"}}
        row["schema"]["required"] = []
        self.reject(row)
        for source in ("https://example.org/schema/", "../trusted/", "linux_client/\n"):
            self.reject(self.changed("port", provenance=source))
        for key in ("minimum", "maximum"):
            row = self.changed("port")
            row["schema"]["properties"]["associated"] = {"type": "number", key: float("inf")}
            self.reject(row)

    def test_bytes_node_and_unicode_limits(self):
        row = self.changed("port")
        row["schema"]["properties"]["associated"] = {"type": "string", "const": "x" * 65536}
        self.reject(row)
        self.reject({"x": [None] * 50000})
        self.reject(self.changed("function", description="\ud800"))
        self.reject({1: "not a JSON object key"})
        self.reject([])

    def test_cross_catalog_references_are_not_fabricated_by_local_validation(self):
        # A syntactically valid reference is not proof the target exists.
        # Full resolution belongs to FND-03 and execution gates to FND-06.
        validate_contract(self.changed("function", outputs={"future.metric": "9.0.0"}))
        row = self.changed("selection")
        row["functions"] = {"future.read": "1.0.0"}
        validate_contract(row)

    def test_nested_payload_contract_uses_existing_core_semantics(self):
        row = self.changed("port")
        row["schema"] = {
            "type": "object", "properties": {
                "metrics": {"type": "array", "items": {"type": "number", "minimum": 0, "maximum": 100},
                            "minItems": 0, "maxItems": 4},
                "address": {"type": "string", "format": "ipv4"},
            }, "required": ["metrics", "address"], "additionalProperties": False,
        }
        validate_contract(row)
        self.assertTrue(schema_subset(row["schema"], row["schema"]))
        self.assertTrue(validate({"metrics": [0, 100], "address": "192.0.2.1"}, row["schema"]))
        self.assertFalse(validate({"metrics": [101], "address": "192.0.2.1"}, row["schema"]))
        self.assertFalse(validate({"metrics": [1], "address": "bad"}, row["schema"]))


if __name__ == "__main__":
    unittest.main()
