"""Opt-in Edge/Cloud decision and privacy-minimized *hypothesis* delegation.

No network transport is included: a trusted application may inject a cloud
adapter. Remote output is NEVER evidence, tool authority, an executable plan,
or a verified RCA Claim. Edge remains the default.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass

from ..core import PlanError


PURPOSES = frozenset({"CROSS_LAYER_RCA", "FLEET_REFERENCE", "LONG_CONTEXT"})


@dataclass(frozen=True)
class CloudDecision:
    route: str  # EDGE, CLOUD, BLOCKED or NEEDS_APPROVAL
    reason: str
    reserved_cost_usd: float = 0.0


class EdgeCloudPolicy:
    """Trusted budget/privacy controls independent of LLM-generated content."""

    def __init__(self, *, enabled=False, max_requests=3,
                 max_cost_usd=0.10, max_context_bytes=1536):
        if type(enabled) is not bool or type(max_requests) is not int or not 1 <= max_requests <= 30:
            raise ValueError("invalid_cloud_policy")
        if (type(max_cost_usd) not in (int, float) or not math.isfinite(max_cost_usd)
                or not 0 < max_cost_usd <= 100):
            raise ValueError("invalid_cloud_budget")
        if type(max_context_bytes) is not int or not 128 <= max_context_bytes <= 4096:
            raise ValueError("invalid_cloud_context_limit")
        self.enabled = enabled
        self.max_requests = max_requests
        self.max_cost_usd = float(max_cost_usd)
        self.max_context_bytes = max_context_bytes
        self.calls, self.spent_usd = 0, 0.0

    def decide(self, purpose: str, *, edge_can_resolve: bool, consent: bool,
               privacy: str, estimated_cost_usd: float, backend_present: bool):
        if type(edge_can_resolve) is not bool or type(consent) is not bool or type(backend_present) is not bool:
            raise ValueError("invalid_cloud_decision_flags")
        if edge_can_resolve:
            return CloudDecision("EDGE", "edge_first")
        if purpose not in PURPOSES:
            return CloudDecision("BLOCKED", "unsupported_cloud_purpose")
        if not self.enabled:
            return CloudDecision("BLOCKED", "cloud_disabled")
        if privacy != "AGGREGATED_ONLY":
            return CloudDecision("BLOCKED", "privacy_not_aggregated")
        if not consent:
            return CloudDecision("NEEDS_APPROVAL", "explicit_cloud_consent_required")
        if not backend_present:
            return CloudDecision("BLOCKED", "cloud_backend_not_configured")
        if (type(estimated_cost_usd) not in (int, float)
                or not math.isfinite(estimated_cost_usd) or estimated_cost_usd <= 0):
            raise ValueError("invalid_estimated_cloud_cost")
        if (self.calls >= self.max_requests or
                self.spent_usd + estimated_cost_usd > self.max_cost_usd):
            return CloudDecision("BLOCKED", "cloud_budget_exceeded")
        return CloudDecision("CLOUD", "approved_aggregated_hypothesis_only",
                             float(estimated_cost_usd))

    def reserve(self, decision):
        if not isinstance(decision, CloudDecision) or decision.route != "CLOUD":
            raise PlanError("cloud_reservation_not_approved")
        if (self.calls >= self.max_requests or
                self.spent_usd + decision.reserved_cost_usd > self.max_cost_usd):
            raise PlanError("cloud_budget_exceeded")
        # Reserve *before* adapter call; errors must consume allowance.
        self.calls += 1
        self.spent_usd += decision.reserved_cost_usd


def minimal_cloud_context(registry, state, *, max_items=8, max_bytes=1536):
    """Extract only verified numeric/bool gateway telemetry.

    No free-text logs, client identity, IP addresses, MACs, requests, raw
    evidence identifiers or Function arguments are ever transmitted.
    """
    if type(max_items) is not int or not 1 <= max_items <= 20:
        raise ValueError("invalid_cloud_items")
    if type(max_bytes) is not int or not 128 <= max_bytes <= 4096:
        raise ValueError("invalid_cloud_bytes")
    rows = []
    for name in sorted(registry.ports):
        port = registry.ports[name]
        if port.scope != "gateway" or port.untrusted_text:
            continue
        # A previously recorded fact is not exportable after its read
        # authorization was withdrawn. Recheck trusted Function policy.
        if not any(
            name in f.outputs and registry.contract_allowed(f) and state.allowed(f)
            for f in registry.functions.values()
        ):
            continue
        fact = state.fact(name, port)
        if fact is None or not isinstance(fact.get("value"), dict):
            continue
        values = {key: value for key, value in fact["value"].items()
                  if (type(value) in (bool, int, float)
                      and (type(value) is not float or math.isfinite(value))
                      and key in port.schema.get("properties", {})
                      and port.schema["properties"][key].get("type")
                      in {"number", "integer", "boolean"})}
        if not values:
            continue
        trial = rows + [{"port": name, "metrics": values}]
        if len(trial) > max_items or len(json.dumps(trial, sort_keys=True)) > max_bytes:
            break
        rows = trial
    return {"telemetry": rows, "summary": "verified_numeric_gateway_metrics_only"}


class CloudHypothesisAdapter:
    """No built-in cloud client. Trusted backend implements analyze(payload)."""

    def __init__(self, backend, policy: EdgeCloudPolicy):
        if not callable(getattr(backend, "analyze", None)) or not isinstance(policy, EdgeCloudPolicy):
            raise ValueError("trusted_cloud_backend_required")
        self.backend, self.policy = backend, policy

    def request(self, registry, state, *, purpose, consent=False,
                estimated_cost_usd=0.01, edge_can_resolve=True):
        decision = self.policy.decide(
            purpose, edge_can_resolve=edge_can_resolve,
            consent=consent, privacy="AGGREGATED_ONLY",
            estimated_cost_usd=estimated_cost_usd, backend_present=True,
        )
        if decision.route != "CLOUD":
            return {"route": decision.route, "reason": decision.reason,
                    "status": "NOT_SENT"}
        context = minimal_cloud_context(
            registry, state, max_bytes=self.policy.max_context_bytes,
        )
        if not context["telemetry"]:
            return {"route": "BLOCKED", "reason": "no_shareable_evidence",
                    "status": "NOT_SENT"}
        self.policy.reserve(decision)
        payload = {"purpose": purpose, "context": context,
                   "requested_output": "unverified_hypothesis_only"}
        try:
            response = self.backend.analyze(payload)
        except (OSError, RuntimeError, ValueError, TimeoutError):
            return {"route": "CLOUD", "status": "ERROR",
                    "reason": "cloud_backend_failed"}
        if not isinstance(response, dict) or set(response) != {"hypothesis"} or (
            not isinstance(response["hypothesis"], str)
            or not 1 <= len(response["hypothesis"]) <= 1000
        ):
            return {"route": "CLOUD", "status": "REJECTED",
                    "reason": "cloud_invalid_response"}
        return {"route": "CLOUD", "status": "HYPOTHESIS_UNVERIFIED",
                "hypothesis": response["hypothesis"],
                "reason": "cloud_cannot_verify_or_execute"}
