"""HTTPS transport for a trusted Cloud hypothesis service (explicit opt-in).

The endpoint is configured by the trusted service operator, not the user or
LLM. No provider URL, credentials or network calls are built into the app.
Only privacy-filtered payloads from CloudHypothesisAdapter may be sent.
"""
from __future__ import annotations

import json
import re
import ssl
from urllib.parse import urlparse
from urllib.request import Request, HTTPRedirectHandler, HTTPSHandler, build_opener


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class HTTPSHypothesisBackend:
    """Backend contract: POST JSON -> exact {hypothesis: str}."""

    def __init__(self, endpoint, *, allowed_hosts, bearer_token, timeout_s=8):
        if not isinstance(endpoint, str):
            raise ValueError("cloud_invalid_endpoint")
        parsed = urlparse(endpoint)
        if (parsed.scheme != "https" or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment
                or parsed.path not in {"/v1/hypothesis", "/v1/hypothesis/"}
                or not isinstance(allowed_hosts, (set, frozenset, tuple, list))
                or parsed.hostname.lower() not in {
                    host.lower() for host in allowed_hosts if isinstance(host, str)
                }):
            raise ValueError("cloud_https_allowlisted_endpoint_required")
        if (not isinstance(bearer_token, str) or not 16 <= len(bearer_token) <= 2048
                or re.search(r"[\s\r\n]", bearer_token)):
            raise ValueError("cloud_token_must_be_trusted_secret")
        if type(timeout_s) not in (int, float) or not 0 < timeout_s <= 30:
            raise ValueError("cloud_timeout_invalid")
        self.endpoint, self.timeout_s = endpoint, timeout_s
        self._token = bearer_token
        self._opener = build_opener(
            HTTPSHandler(context=ssl.create_default_context()),
            _NoRedirect(),
        )

    @staticmethod
    def _validate_payload(payload):
        if not isinstance(payload, dict) or set(payload) != {
            "purpose", "context", "requested_output"
        } or payload["purpose"] not in {
            "CROSS_LAYER_RCA", "FLEET_REFERENCE", "LONG_CONTEXT"
        } or payload["requested_output"] != "unverified_hypothesis_only":
            raise ValueError("cloud_invalid_payload_contract")
        context = payload["context"]
        if (not isinstance(context, dict) or set(context) != {"telemetry", "summary"}
                or context["summary"] != "verified_numeric_gateway_metrics_only"
                or not isinstance(context["telemetry"], list)
                or not 1 <= len(context["telemetry"]) <= 20):
            raise ValueError("cloud_unapproved_telemetry")
        for row in context["telemetry"]:
            if (not isinstance(row, dict) or set(row) != {"port", "metrics"}
                    or not isinstance(row["port"], str)
                    or not re.fullmatch(r"[A-Za-z0-9_.-]{2,120}", row["port"])
                    or not isinstance(row["metrics"], dict) or not row["metrics"]):
                raise ValueError("cloud_unapproved_telemetry")
            for key, value in row["metrics"].items():
                if (not isinstance(key, str)
                        or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", key)
                        or type(value) not in (bool, int, float)):
                    raise ValueError("cloud_unapproved_telemetry")

    def analyze(self, payload):
        self._validate_payload(payload)
        raw = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, allow_nan=False,
            separators=(",", ":"),
        ).encode("utf-8")
        if len(raw) > 4096:
            raise ValueError("cloud_payload_too_large")
        request = Request(self.endpoint, data=raw, method="POST", headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": "Bearer " + self._token,
            "User-Agent": "Gateway-LM-Hypothesis/0.1",
        })
        # No redirects; prevents a trusted endpoint from forwarding the
        # authorization header or sanitized payload to arbitrary origins.
        with self._opener.open(request, timeout=self.timeout_s) as response:
            if getattr(response, "status", None) != 200:
                raise OSError("cloud_unexpected_http_status")
            body = response.read(4097)
        if len(body) > 4096:
            raise OSError("cloud_response_too_large")
        try:
            result = json.loads(body)
        except (TypeError, ValueError, UnicodeError) as exc:
            raise OSError("cloud_response_invalid_json") from exc
        if (not isinstance(result, dict) or set(result) != {"hypothesis"}
                or not isinstance(result["hypothesis"], str)
                or not 1 <= len(result["hypothesis"]) <= 1000):
            raise OSError("cloud_response_wrong_contract")
        return result
