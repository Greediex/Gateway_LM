"""Registry-driven, read-only goal execution independent of a workflow ID.

This is an opt-in diagnostics API. Explicit goals are typed output-port names;
natural-language inference delegates to the existing calibrated Turn Router
and cannot create new Functions, permissions or evidence.
"""
from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Sequence

from ..core import ROOT, PlanError, read_json
from ..turn_router import route_turn
from .graphs import GraphRegistry
from .orchestrator import run_plan
from .planner import NodeState
from .runner import GraphRunner
from .state import CaseState
from .task_decomposer import TaskDecomposer
from .checkpoint import EvidenceCheckpoint
from .llm_goals import BoundedGoalProposer
from .job_journal import ReadOnlyJobJournal


class GoalAgent:
    """Bounded evidence-acquisition loop for one or many known output ports."""

    def __init__(self, registry=None, *, method="gos", max_calls=12,
                 max_repairs=2, max_rounds=3, retrieval_k=4, checkpoint=None,
                 goal_proposer=None, journal=None):
        if method not in {"gos", "bm25", "hybrid"}:
            raise ValueError("invalid_goal_method")
        if method == "hybrid" and getattr(registry, "_semantic_index", None) is None:
            raise ValueError("semantic_provider_required")
        if any(type(n) is not int or n <= 0 for n in (max_calls, max_rounds, retrieval_k)):
            raise ValueError("invalid_goal_budget")
        if type(max_repairs) is not int or max_repairs < 0:
            raise ValueError("invalid_goal_repair_budget")
        self.registry = registry if registry is not None else GraphRegistry()
        self.method = method
        self.max_calls = max_calls
        self.max_repairs = max_repairs
        self.max_rounds = max_rounds
        self.retrieval_k = retrieval_k
        if checkpoint is not None and not isinstance(checkpoint, EvidenceCheckpoint):
            raise ValueError("checkpoint_must_be_trusted_store")
        self.checkpoint = checkpoint
        if goal_proposer is not None and not isinstance(goal_proposer, BoundedGoalProposer):
            raise ValueError("goal_proposer_must_be_trusted")
        self.goal_proposer = goal_proposer
        if journal is not None and not isinstance(journal, ReadOnlyJobJournal):
            raise ValueError("journal_must_be_trusted_local")
        self.journal = journal

    def run(self, request: str, case: dict, *, goals: Sequence[str] | None = None,
            inventory=(), advisor=None):
        if not isinstance(request, str) or not request.strip() or not isinstance(case, dict):
            raise ValueError("invalid_goal_request")
        case = dict(case, request=request)
        registry = self.registry
        state = CaseState(case, registry)
        routing = None

        if goals is None:
            if not hasattr(registry, "workflows"):
                raise PlanError("goal_inference_requires_versioned_catalog")
            decomposer = TaskDecomposer(registry)
            decomposition = decomposer.decompose(request)
            # Preserve the existing compound-request refusal contract; the
            # single-intent gate applies only when decomposition abstains.
            if decomposition.decision == "NOT_APPLICABLE" and decomposer.is_write_intent(request):
                return self._result((), state, None,
                                    routing={"source": "write_policy", "action": "REFUSE"},
                                    status="BLOCKED",
                                    reason="write_intent_requires_approval")
            if decomposition.decision == "READY":
                goals = decomposition.goals
                routing = {
                    "source": "registered_goal_aliases",
                    "action": "RUN",
                    "reason": decomposition.reason,
                    "clauses": list(decomposition.clauses),
                    "matched_goals": list(decomposition.goals),
                }
            elif decomposition.decision in {"NEEDS_INPUT", "BLOCKED"}:
                routing = {
                    "source": "registered_goal_aliases",
                    "action": "ASK_USER" if decomposition.decision == "NEEDS_INPUT" else "REFUSE",
                    "reason": decomposition.reason,
                    "clauses": list(decomposition.clauses),
                    "unresolved": list(decomposition.unresolved),
                }
                return self._result(
                    (), state, None, routing=routing,
                    status=decomposition.decision, reason=decomposition.reason,
                )
            else:
                routed = route_turn(request, registry=registry, state=state,
                                    inventory=inventory, advisor=advisor)
                routing = {"turn_type": routed["turn_type"], "action": routed["action"],
                           "band": routed["band"], "reason": routed["reason"],
                           "source": "calibrated_workflow_router"}
                hint = routed.get("plan_hint")
                if routed["action"] != "RUN" or hint is None:
                    if self.goal_proposer is not None and routed["action"] in {
                        "ASK_USER", "ANSWER", "NO_ACTION", "REFUSE", "BLOCKED"
                    }:
                        proposed = self.goal_proposer.propose(request, registry, state, decomposer)
                        routing = {
                            "source": "bounded_llm_proposal",
                            "action": "RUN" if proposed.decision == "READY" else "ASK_USER",
                            "reason": proposed.reason,
                            "original_router": routing,
                        }
                        if proposed.decision == "READY":
                            goals = proposed.goals
                        else:
                            return self._result((), state, None, routing=routing,
                                                status=proposed.decision,
                                                reason=proposed.reason)
                    else:
                        return self._result((), state, None, routing=routing,
                                            status="NEEDS_INPUT" if routed["action"] == "ASK_USER"
                                            else "BLOCKED", reason=routed["reason"])
                else:
                    goals = hint["goals"]
        if isinstance(goals, (str, bytes)) or not isinstance(goals, Sequence):
            raise ValueError("invalid_goal_ports")
        goals = tuple(dict.fromkeys(goals))
        if not goals or any(not isinstance(g, str) or g not in registry.ports for g in goals):
            raise PlanError("unknown_or_empty_goal_ports")
        # Never resolve an unspecified client from replay's world/ground truth.
        client_goals = any(registry.ports[g].scope == "client" for g in goals)
        if client_goals and not (state.target.get("selector") or state.target.get("client_id")):
            return self._result(goals, state, None, routing=routing,
                                status="NEEDS_INPUT", reason="client_target_required")
        if self.checkpoint is not None:
            # Resume only signed, still-fresh observations under the same
            # Registry/target/firmware/ACL. Running nodes never auto-resume.
            self.checkpoint.restore(registry, state, request, goals)
        if all(state.fact(goal) is not None for goal in goals):
            result = self._result(goals, state, None, routing=routing,
                                  status="RESOLVED", reason="verified_evidence_reused")
            if self.journal is not None:
                result["journal_events"] = self.journal.recover(
                    registry, state, request, goals
                )
            return result
        if not any(key in case for key in ("world", "adapter", "live_reader")):
            return self._result(goals, state, None, routing=routing,
                                status="INCONCLUSIVE", reason="observation_source_not_configured")

        # Capability claims from the Case are not enough for an assigned
        # Adapter. Intersect with real probe results before planning.
        adapter = case.get("adapter")
        if adapter is not None:
            try:
                probe = adapter.probe()
            except (OSError, RuntimeError, ValueError, PlanError):
                probe = {}
            if not isinstance(probe, dict):
                probe = {}
            from ..adapters import PROBE_OK
            verified = {fid for fid, status in probe.items() if status == PROBE_OK}
            state.capabilities.intersection_update(verified)
            state.probe_capabilities.intersection_update(verified)

        if self.journal is not None:
            # Verify persisted HMAC chain before doing any further work.
            self.journal.recover(registry, state, request, goals)
        event_sink = (
            (lambda event: self.journal.append(registry, state, request, goals, event))
            if self.journal is not None else None
        )
        runner = GraphRunner(registry, case, state, max_calls=self.max_calls,
                             max_repairs=self.max_repairs, event_sink=event_sink)
        trace = []
        reason = "no_admissible_plan"
        for _ in range(self.max_rounds):
            if all(state.fact(g) is not None for g in goals):
                reason = "all_requested_goals_verified"
                break
            if runner.calls >= runner.max_calls:
                reason = "runner_call_budget"
                break
            try:
                # H_F chooses the actual typed producers. Compiler expands
                # Skill prerequisites and dependencies without a fixed workflow.
                plan = runner.compiler().compile(
                    goals, state,
                    revision=runner.plans[-1].revision + 1 if runner.plans else 1,
                )
            except PlanError as exc:
                reason = str(exc)
                state.errors.append(reason)
                break
            previous = runner.calls
            retrievals = run_plan(runner, plan, goals,
                                  method=self.method, k=self.retrieval_k)
            trace.extend({
                "ready_set": r["ready_set"], "selected_ready": r["selected_ready"],
                "method": r["method"], "upstream_kernel_used": r["upstream_kernel_used"],
            } for r in retrievals)
            if all(state.fact(g) is not None for g in goals):
                reason = "all_requested_goals_verified"
                break
            # A failed Function must not be silently retried forever. Recompile
            # with alternatives that remain admissible and currently probed.
            failed = {n.function_id for plan in runner.plans for n in plan.nodes.values()
                      if n.state in (NodeState.FAILED, NodeState.INCONCLUSIVE)}
            runner.excluded.update(failed)
            if runner.calls == previous:
                reason = "no_further_ready_work"
                break
            reason = "evidence_incomplete_replan"
        exhausted = True
        status = state.case_status(goals, exhausted=exhausted)
        result = self._result(goals, state, runner, routing=routing, status=status,
                              reason=reason, trace=trace)
        if self.checkpoint is not None:
            result["checkpoint_facts_saved"] = self.checkpoint.save(
                registry, state, request, goals
            )
        if self.journal is not None:
            result["journal_events"] = self.journal.recover(
                registry, state, request, goals
            )
        return result

    @staticmethod
    def _result(goals, state, runner, *, routing, status, reason, trace=()):
        # Goal satisfaction only means measurements were verified: it is not an
        # RCA claim or proof that network connectivity has been repaired.
        facts = [state.fact(g) for g in goals]
        return {
            "goals": list(goals),
            "status": status,
            "reason": reason,
            "diagnosis": "NOT_EVALUATED",
            "routing": routing,
            "goal_facts": [
                {"port": g, "evidence_id": e["id"], "value": copy.deepcopy(e["value"]),
                 "source": e["source"], "target": e["target"]}
                for g, e in zip(goals, facts) if e is not None
            ],
            "missing_goals": [g for g, e in zip(goals, facts) if e is None],
            "calls": runner.calls if runner is not None else 0,
            "repairs": runner.repairs if runner is not None else 0,
            "plans": [p.export() for p in runner.plans] if runner is not None else [],
            "ready_trace": list(trace),
            "contract_b": list(runner.contract_b) if runner is not None else [],
            "contract_c": state.export_contract_c(goals, exhausted=True),
            "errors": list(state.errors),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Bounded typed goal acquisition (synthetic replay pilot)")
    parser.add_argument("--fixture", default="GLM-04-0")
    parser.add_argument("--request", required=True)
    parser.add_argument("--goals", nargs="*", default=None,
                        help="Explicit output-port goals; omit for versioned-catalog inference")
    parser.add_argument("--registry", choices=("legacy", "v01"), default="legacy")
    parser.add_argument("--method", choices=("bm25", "gos", "hybrid"), default="bm25")
    parser.add_argument("--semantic-model-dir",
                        help="Trusted local sentence-transformers model directory; required for hybrid")
    parser.add_argument("--max-calls", type=int, default=12)
    args = parser.parse_args(argv)
    cases = read_json(ROOT / "data/cases.json")
    case = next((copy.deepcopy(x) for x in cases if x["id"] == args.fixture), None)
    if case is None:
        parser.error("unknown replay fixture")
    registry = GraphRegistry.from_v01() if args.registry == "v01" else GraphRegistry()
    if args.method == "hybrid":
        if not args.semantic_model_dir:
            parser.error("hybrid requires --semantic-model-dir (trusted local model)")
        from .semantic import LocalSentenceTransformerEncoder
        registry.configure_semantic(
            LocalSentenceTransformerEncoder(args.semantic_model_dir)
        )
    elif args.semantic_model_dir:
        parser.error("--semantic-model-dir requires --method hybrid")
    agent = GoalAgent(registry, method=args.method, max_calls=args.max_calls)
    result = agent.run(args.request, case, goals=args.goals)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "RESOLVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
