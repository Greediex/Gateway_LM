"""Evidence verification boundary: adapter observations cannot directly justify claims."""
from __future__ import annotations

import copy

from ..core import PlanError
from .planner import NodeState
from .repair import classify


class EvidenceVerifier:
    """Validate schema, scope, provenance, freshness and timeout for each output."""

    @staticmethod
    def ttl_seconds(runner, function):
        ttl = getattr(function, "ttl_seconds", None)
        return ttl if ttl is not None else runner.registry.legacy.functions[function.id]["ttl_s"]

    @staticmethod
    def annotate(runner, evidence, node, function, state):
        port = function.outputs.get(evidence["port"])
        if evidence.get("source", "").startswith("synthetic_replay"):
            evidence["observed_at"] = runner.state.observed_at()
        evidence.update(
            evidence_id=evidence["id"],
            case_id=runner.state.case_id,
            skill_context=node.skill_context,
            ttl_seconds=evidence.get("ttl_s"),
            raw=copy.deepcopy(evidence.get("value")),
        )
        evidence["validator_result"] = state.validator(evidence, port) if port is not None else {}
        evidence["assertions"] = state.assertions_for(evidence) if evidence["status"] == "OK" else []

    @staticmethod
    def export_contract_b(node, observations, adapter_status, simulated_ms, elapsed_ms, function):
        """Contract B reports tool/validation results, never a goal claim."""
        statuses = set(adapter_status.values())
        if "TIMEOUT" in statuses or max(simulated_ms, elapsed_ms) > function.timeout_ms:
            tool = "TIMEOUT"
        elif statuses <= {"OK", "PARSE_ERROR"}:
            tool = "EXIT_OK"
        else:
            tool = "EXIT_ERROR"
        return {
            "node_id": node.id,
            "tool_status": tool,
            "observations": [
                {
                    "evidence_id": e["id"],
                    "kind": e["port"],
                    "target": e["target"],
                    "scope": e["scope"],
                    "result": e["status"],
                    "source": e["source"],
                } for e in observations
            ],
            "goal_claim": "NOT_EVALUATED",
        }

    def verify(self, runner, node, function, state, observations, *, simulated_ms, elapsed_ms):
        """Fail closed before accepting an incomplete/foreign observation set."""
        expected = set(function.outputs)
        if (not isinstance(observations, list)
                or len(observations) != len(expected)
                or any(not isinstance(e, dict) for e in observations)):
            raise PlanError("observation_count_mismatch")
        required = {"id", "port", "scope", "target", "status", "source", "value"}
        if (any(not required.issubset(e) or e.get("function_id") != function.id for e in observations)
                or {e["port"] for e in observations} != expected):
            raise PlanError("observation_contract_mismatch")
        if len({e["id"] for e in observations}) != len(observations):
            raise PlanError("observation_duplicate_id")
        adapter_status = {e["id"]: e["status"] for e in observations}
        for evidence in observations:
            evidence["ttl_s"] = self.ttl_seconds(runner, function)
            if (node.context_target and evidence["scope"] == "client"
                    and evidence["target"] != node.context_target["client_id"]):
                evidence["_scope_mismatch"] = True
                evidence["_invalidated"] = True
                evidence["status"] = "VERIFICATION_FAILED"
            state.record(evidence)
            if max(simulated_ms, elapsed_ms) > function.timeout_ms:
                evidence["status"] = "TIMEOUT"
            evidence["verifier"] = function.verifier
            evidence["contract_digest"] = function.digest()
            if (evidence["status"] == "OK"
                    and state.fact(evidence["port"], function.outputs[evidence["port"]]) is not evidence):
                evidence["status"] = "VERIFICATION_FAILED"
            self.annotate(runner, evidence, node, function, state)
        runner.contract_b.append(
            self.export_contract_b(node, observations, adapter_status, simulated_ms, elapsed_ms, function)
        )
        runner.state.refresh_revision()
        if all(e["status"] == "OK" for e in observations):
            node.output_evidence = {e["port"]: e["id"] for e in observations}
            node.transition(NodeState.SUCCEEDED, "schema_scope_source_freshness_verified")
        else:
            status = next(e["status"] for e in observations if e["status"] != "OK")
            node.failure = {"type": classify(status), "status": status, "message": status}
            node.transition(NodeState.FAILED if status == "TIMEOUT" else NodeState.INCONCLUSIVE, status)
