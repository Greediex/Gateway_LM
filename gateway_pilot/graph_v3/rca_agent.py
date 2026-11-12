"""Bounded, evidence-driven read-only RCA over versioned Claim contracts.

This is *claim-backed fault classification*, not a causal experiment or a
learned cross-layer root cause model. It chooses missing evidence ports from
declared Claim predicates, executes them via the common GraphRunner, and
rechecks the claims after each batch.
"""
from __future__ import annotations

import copy
from collections import Counter

from ..adapters import PROBE_OK
from ..core import PlanError
from .claims import claim_book
from .contracts import Truth
from .graphs import GraphRegistry
from .orchestrator import run_plan
from .planner import NodeState
from .runner import GraphRunner
from .state import CaseState


class EvidenceRCA:
    """Tri-state claim assessor and next-evidence proposal with no tool calls."""

    def __init__(self, registry, workflow: str):
        self.registry, self.workflow = registry, workflow
        book = claim_book(registry)
        wf = getattr(registry, "workflows", {}).get(workflow)
        if (not isinstance(wf, dict) or wf.get("status") != "SUPPORTED"
                or wf.get("kind") != "DIAGNOSE"
                or not wf.get("claims") or workflow not in book.workflows):
            raise PlanError("rca_requires_supported_diagnostic_workflow")
        self.book = book
        names = set(wf["claims"])
        self.claims = tuple(c for c in book.claims.values()
                            if c.diagnosis in names and c.workflow in (None, workflow))
        if not self.claims:
            raise PlanError("rca_without_registered_claims")
        self.target_scope = wf["target_scope"]

    def assess(self, state, *, excluded_ports=()):
        allowed = self.registry.eligible(state)
        rows = []
        fault, healthy, observations = [], [], []
        counts = Counter()
        excluded_ports = set(excluded_ports)
        for c in self.claims:
            value, evidence = c.evaluate(state)
            row = {
                "claim_id": c.claim_id, "diagnosis": c.diagnosis,
                "severity": c.severity, "scope": c.scope,
                "truth": value.value, "evidence_ids": list(evidence),
            }
            rows.append(row)
            if value == Truth.TRUE:
                if c.severity == "FAULT":
                    fault.append(row)
                elif c.severity == "HEALTHY":
                    healthy.append(row)
                else:
                    observations.append(row)
            elif value == Truth.UNKNOWN and c.severity in {"FAULT", "HEALTHY"}:
                for req in c.requires:
                    if req.evaluate(state)[0] != Truth.UNKNOWN:
                        continue
                    port = self.registry.ports.get(req.port)
                    if port is None or port.untrusted_text or req.port in excluded_ports:
                        continue
                    # A suggestion is not an authorization. Only verified
                    # read-only capability candidates may suggest a port.
                    producers = [
                        f for f in self.registry.functions.values()
                        if req.port in f.outputs and f.id in allowed
                    ]
                    if port.scope == "client" and not (
                        state.target.get("selector") or state.target.get("client_id")
                    ):
                        continue
                    if producers:
                        counts[req.port] += 2 if c.severity == "FAULT" else 1
        unknown_faults = [
            x for x in rows if x["severity"] == "FAULT" and x["truth"] == Truth.UNKNOWN.value
        ]
        if fault:
            decision = "VERIFIED_FAULT" if len(fault) == 1 else "MULTIPLE_FAULTS"
            conclusion = fault[0]["diagnosis"] if len(fault) == 1 else None
            proof = sorted({eid for row in fault for eid in row["evidence_ids"]})
        elif healthy and not unknown_faults:
            decision = "HEALTHY_OBSERVED"
            conclusion = healthy[0]["diagnosis"]
            proof = sorted({eid for row in healthy for eid in row["evidence_ids"]})
        else:
            decision, conclusion, proof = "INCONCLUSIVE", None, []
        next_goals = [
            p for p, _ in sorted(counts.items(), key=lambda row: (-row[1], row[0]))
        ]
        return {
            "decision": decision, "diagnosis": conclusion, "evidence_ids": proof,
            "workflow": self.workflow,
            "claim_results": rows,
            "candidate_goals": next_goals,
            "observed_patterns": observations,
            "disclaimer": "Verified Claim predicates, not causal proof or a repaired network",
        }


class RCAAgent:
    """Run inspect -> choose missing claim evidence -> measure -> reassess."""

    def __init__(self, registry=None, *, method="gos",
                 max_calls=10, max_rounds=10, max_repairs=2, retrieval_k=4):
        self.registry = registry or GraphRegistry.from_v01()
        if method not in {"gos", "bm25", "hybrid"}:
            raise ValueError("invalid_rca_method")
        if method == "hybrid" and getattr(self.registry, "_semantic_index", None) is None:
            raise ValueError("semantic_provider_required")
        if any(type(n) is not int or not 1 <= n <= 50 for n in (
                max_calls, max_rounds, retrieval_k)):
            raise ValueError("invalid_rca_budget")
        if type(max_repairs) is not int or not 0 <= max_repairs <= 10:
            raise ValueError("invalid_rca_repair_budget")
        self.method, self.max_calls, self.max_rounds = method, max_calls, max_rounds
        self.max_repairs, self.retrieval_k = max_repairs, retrieval_k

    def run(self, request: str, case: dict, *, workflow: str):
        if not isinstance(request, str) or not request.strip() or not isinstance(case, dict):
            raise ValueError("invalid_rca_request")
        registry = self.registry
        assessor = EvidenceRCA(registry, workflow)
        case = dict(case, request=request)
        state = CaseState(case, registry)
        if assessor.target_scope == "client" and not (
            state.target.get("selector") or state.target.get("client_id")
        ):
            return {
                "status": "NEEDS_INPUT", "reason": "client_target_required",
                "calls": 0, "diagnosis": None, "workflow": workflow, "events": [],
            }
        adapter = case.get("adapter")
        if adapter is not None:
            try:
                probe = adapter.probe()
            except (OSError, RuntimeError, ValueError, PlanError):
                probe = {}
            verified = {fid for fid, outcome in probe.items()
                        if outcome == PROBE_OK} if isinstance(probe, dict) else set()
            state.capabilities.intersection_update(verified)
            state.probe_capabilities.intersection_update(verified)
        runner = GraphRunner(registry, case, state,
                             max_calls=self.max_calls, max_repairs=self.max_repairs)
        excluded_ports, trace = set(), []
        reason = "evidence_insufficient"
        for iteration in range(self.max_rounds):
            assessment = assessor.assess(state, excluded_ports=excluded_ports)
            if assessment["decision"] in {"VERIFIED_FAULT", "MULTIPLE_FAULTS",
                                           "HEALTHY_OBSERVED"}:
                reason = "claim_supported_by_verified_evidence"
                break
            if runner.calls >= runner.max_calls:
                reason = "rca_call_budget_exhausted"
                break
            if not any(k in case for k in ("adapter", "world", "live_reader")):
                reason = "observation_source_not_configured"
                break
            chosen = None
            for goal in assessment["candidate_goals"]:
                try:
                    plan = runner.compiler().compile(
                        [goal], state,
                        revision=runner.plans[-1].revision + 1 if runner.plans else 1,
                    )
                except PlanError:
                    excluded_ports.add(goal)
                    continue
                chosen = goal
                break
            if chosen is None:
                reason = "no_admissible_evidence_goal"
                break
            before = runner.calls
            retrievals = run_plan(
                runner, plan, [chosen],
                method=self.method, k=self.retrieval_k,
            )
            trace.append({
                "iteration": iteration + 1, "goal": chosen,
                "calls_added": runner.calls - before,
                "verified": state.fact(chosen) is not None,
                "ready_trace": [
                    {"ready_set": row["ready_set"],
                     "selected_ready": row["selected_ready"]}
                    for row in retrievals
                ],
            })
            runner.excluded.update(
                n.function_id for p in runner.plans for n in p.nodes.values()
                if n.state in (NodeState.FAILED, NodeState.INCONCLUSIVE)
            )
            if state.fact(chosen) is None or runner.calls == before:
                excluded_ports.add(chosen)
            reason = "evidence_insufficient_replan"
        assessment = assessor.assess(state, excluded_ports=excluded_ports)
        return {
            "status": assessment["decision"],
            "reason": reason,
            "diagnosis": assessment["diagnosis"],
            "evidence_ids": assessment["evidence_ids"],
            "workflow": workflow,
            "calls": runner.calls, "repairs": runner.repairs,
            "claim_results": assessment["claim_results"],
            "candidate_goals": assessment["candidate_goals"],
            "steps": trace,
            "plans": [p.export() for p in runner.plans],
            "contract_b": copy.deepcopy(runner.contract_b),
            "contract_c": state.export_contract_c(
                registry.goal_ports.get(workflow, ()), exhausted=True,
            ),
            "errors": list(state.errors),
            "disclaimer": assessment["disclaimer"],
        }
