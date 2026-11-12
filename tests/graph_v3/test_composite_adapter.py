"""Contract tests for the optional multi-backend Adapter composition."""
import unittest

from gateway_pilot.adapters import (
    Adapter, CompositeAdapter, PROBE_FAILED, PROBE_OK, gate_capabilities,
)
from gateway_pilot.core import PlanError


class FakeAdapter(Adapter):
    def __init__(self, capabilities):
        self.capabilities = dict(capabilities)
        self.calls = []
        self.probe_calls = 0

    def probe(self):
        self.probe_calls += 1
        return dict(self.capabilities)

    def call(self, function_id, arguments, state, case):
        self._check(function_id, arguments)
        self.calls.append((function_id, arguments, state, case))
        return {"function_id": function_id, "arguments": arguments}


class ThrowingAdapter(FakeAdapter):
    def probe(self):
        raise OSError("disconnected")


class MalformedProbeAdapter(FakeAdapter):
    def probe(self):
        return ["unexpected_response"]


class CompositeAdapterTests(unittest.TestCase):
    def test_explicit_function_ownership_and_dispatch(self):
        network = FakeAdapter({"wan.status": PROBE_OK, "secret.write": PROBE_OK})
        wireless = FakeAdapter({"wifi.station": PROBE_OK})
        composite = CompositeAdapter({"wan.status": network, "wifi.station": wireless})
        self.assertEqual(composite.probe(), {"wan.status": PROBE_OK, "wifi.station": PROBE_OK})
        self.assertEqual(network.probe_calls, 1)
        state, case = object(), {"case_id": "c1"}
        result = composite.call("wifi.station", {"client_id": "c1"}, state, case)
        self.assertEqual(result["function_id"], "wifi.station")
        self.assertEqual(wireless.calls[-1], ("wifi.station", {"client_id": "c1"}, state, case))
        with self.assertRaises(PlanError):
            composite.call("secret.write", {}, state, case)
        self.assertEqual(network.calls, [])

    def test_missing_probe_fails_closed_and_blocks_dispatch(self):
        adapter = FakeAdapter({"wan.status": PROBE_OK})
        composite = CompositeAdapter({"wan.status": adapter, "wan.routes": adapter})
        self.assertEqual(composite.probe(), {"wan.status": PROBE_OK, "wan.routes": PROBE_FAILED})
        allowed, failed = gate_capabilities(["wan.status", "wan.routes"], composite.probe())
        self.assertEqual(allowed, ["wan.status"])
        self.assertEqual(failed, {"wan.routes": PROBE_FAILED})
        with self.assertRaises(PlanError):
            composite.call("wan.routes", {}, None, {})
        self.assertEqual(adapter.calls, [])

    def test_lost_capability_is_revalidated_at_execution(self):
        adapter = FakeAdapter({"wan.status": PROBE_OK})
        composite = CompositeAdapter({"wan.status": adapter})
        self.assertEqual(composite.probe()["wan.status"], PROBE_OK)
        adapter.capabilities["wan.status"] = PROBE_FAILED
        with self.assertRaises(PlanError):
            composite.call("wan.status", {}, None, {})
        self.assertEqual(adapter.calls, [])

    def test_faulty_or_malformed_probe_never_unlocks_function(self):
        for backend in (ThrowingAdapter({}), MalformedProbeAdapter({})):
            with self.subTest(backend=type(backend).__name__):
                composite = CompositeAdapter({"wan.status": backend})
                self.assertEqual(composite.probe(), {"wan.status": PROBE_FAILED})
                with self.assertRaises(PlanError):
                    composite.call("wan.status", {}, None, {})
                self.assertEqual(backend.calls, [])

    def test_bad_assignments_and_untyped_calls_are_rejected(self):
        for invalid in ({}, {"": FakeAdapter({})}, {"wan.status": object()}, []):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    CompositeAdapter(invalid)
        composite = CompositeAdapter({"wan.status": FakeAdapter({"wan.status": PROBE_OK})})
        for fid, arguments in ((123, {}), ("wan.status", None), ("wan.status", "{}")):
            with self.subTest(fid=fid, arguments=arguments):
                with self.assertRaises(PlanError):
                    composite.call(fid, arguments, None, {})


if __name__ == "__main__":
    unittest.main()
