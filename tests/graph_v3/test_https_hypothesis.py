"""Allowed HTTPS hypothesis transport with no real credential or egress."""
from __future__ import annotations

import io
import json
import unittest
from unittest.mock import Mock

from gateway_pilot.graph_v3.https_hypothesis import HTTPSHypothesisBackend


class Response(io.BytesIO):
    status = 200


class HTTPSHypothesisTests(unittest.TestCase):
    def setUp(self):
        self.backend = HTTPSHypothesisBackend(
            "https://trusted.example.org/v1/hypothesis",
            allowed_hosts={"trusted.example.org"},
            bearer_token="test-token-not-a-real-secret-123456",
        )
        self.payload = {
            "purpose": "CROSS_LAYER_RCA",
            "requested_output": "unverified_hypothesis_only",
            "context": {
                "summary": "verified_numeric_gateway_metrics_only",
                "telemetry": [{"port": "wan.status", "metrics": {"link_up": True}}],
            },
        }

    def test_reject_external_host_insecure_url_and_redirect_gadgets(self):
        for url in (
            "http://trusted.example.org/v1/hypothesis",
            "https://evil.example.org/v1/hypothesis",
            "https://trusted.example.org@evil.example.org/v1/hypothesis",
            "https://trusted.example.org/v1/hypothesis?redirect=evil",
            "https://trusted.example.org/anything-else",
        ):
            with self.subTest(url=url), self.assertRaises(ValueError):
                HTTPSHypothesisBackend(
                    url, allowed_hosts={"trusted.example.org"},
                    bearer_token="test-token-not-a-real-secret-123456",
                )

    def test_request_contains_only_aggregate_verified_fields(self):
        seen = []
        def open_mock(request, *, timeout):
            seen.append((request, timeout))
            return Response(json.dumps({"hypothesis": "Potential uplink issue"}).encode())
        self.backend._opener.open = open_mock
        result = self.backend.analyze(self.payload)
        self.assertEqual(result, {"hypothesis": "Potential uplink issue"})
        request, timeout = seen[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, "https://trusted.example.org/v1/hypothesis")
        self.assertEqual(timeout, 8)
        self.assertIn("Bearer test-token", request.get_header("Authorization"))
        sent = json.loads(request.data)
        self.assertEqual(sent, self.payload)
        self.assertNotIn("request", sent)
        self.assertNotIn("commands", sent)

    def test_reject_raw_client_data_and_extra_remote_fields(self):
        invalid = [
            {**self.payload, "command": "reboot"},
            {**self.payload, "context": {"summary": "raw", "telemetry": []}},
            {**self.payload, "context": {
                "summary": "verified_numeric_gateway_metrics_only",
                "telemetry": [{"port": "client.identity", "metrics": {"name": "device1"}}],
            }},
        ]
        for entry in invalid:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                self.backend.analyze(entry)

    def test_invalid_json_or_oversized_remote_response_is_rejected(self):
        for data in (b"not json", b'{"commands":["reboot"]}',
                     b'{"hypothesis":"' + b"x"*5000 + b'"}'):
            with self.subTest(length=len(data)):
                self.backend._opener.open = lambda *_args, **_kwargs: Response(data)
                with self.assertRaises(OSError):
                    self.backend.analyze(self.payload)

    def test_no_redirect_handler_installed(self):
        # The transport supplies a redirect handler whose redirect_request
        # returns None; 302/307 responses cannot be automatically followed.
        handlers = self.backend._opener.handlers
        redirect_handlers = [
            h for h in handlers if h.__class__.__name__ == "_NoRedirect"
        ]
        self.assertEqual(len(redirect_handlers), 1)
        self.assertIsNone(redirect_handlers[0].redirect_request(
            None, None, 302, "redirect", {}, "https://evil.example.org"
        ))


if __name__ == "__main__":
    unittest.main()
