"""One typed read-only task entrypoint for measurement and Claim-based RCA.

This is a shared application-level state machine. It routes to existing
GoalAgent/RCAAgent (both use the same GraphRunner/READY kernel) without
creating arbitrary commands or treating measurement completion as RCA.
Legacy workflow-specific answer policies remain a separate migration task.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..core import PlanError
from .goal_agent import GoalAgent
from .graphs import GraphRegistry
from .rca_agent import RCAAgent
from .task_decomposer import TaskDecomposer


@dataclass(frozen=True)
class TaskRequest:
    request: str
    mode: str = "AUTO"  # AUTO, MEASURE, DIAGNOSE
    goals: tuple[str, ...] | None = None
    workflow: str | None = None


class TaskRuntime:
    """Control states: RECEIVED -> ROUTED -> EXECUTED -> VERIFIED -> TERMINAL."""

    STATES = ("RECEIVED", "ROUTED", "EXECUTED", "VERIFIED", "TERMINAL")

    def __init__(self, registry=None, *, method="bm25", max_calls=12,
                 goal_proposer=None, checkpoint=None, journal=None):
        self.registry = registry if registry is not None else GraphRegistry.from_v01()
        self.goal_agent = GoalAgent(
            self.registry, method=method, max_calls=max_calls,
            goal_proposer=goal_proposer, checkpoint=checkpoint, journal=journal,
        )
        self.rca_agent = RCAAgent(self.registry, method=method, max_calls=max_calls)

    def run(self, task: TaskRequest, case: dict):
        if (not isinstance(task, TaskRequest)
                or not isinstance(task.request, str)
                or not 1 <= len(task.request.strip()) <= 2000
                or not isinstance(case, dict)):
            raise ValueError("invalid_task_request")
        if task.mode not in {"AUTO", "MEASURE", "DIAGNOSE"}:
            raise ValueError("invalid_task_mode")
        mode = task.mode
        if mode == "AUTO":
            if task.goals is not None and task.workflow is not None:
                raise PlanError("ambiguous_task_contract")
            mode = "DIAGNOSE" if task.workflow is not None else "MEASURE"
        if mode == "MEASURE":
            if task.workflow is not None:
                raise PlanError("measurement_must_not_claim_diagnosis")
            if task.goals is not None and (
                not isinstance(task.goals, (list, tuple))
                or any(not isinstance(g, str) for g in task.goals)
            ):
                raise ValueError("invalid_task_goal_list")
        else:
            if task.goals is not None or not isinstance(task.workflow, str):
                raise PlanError("diagnosis_requires_registered_workflow")
            wf = getattr(self.registry, "workflows", {}).get(task.workflow)
            if (not isinstance(wf, dict) or wf.get("status") != "SUPPORTED"
                    or wf.get("kind") != "DIAGNOSE"):
                raise PlanError("diagnosis_requires_supported_workflow")
        if TaskDecomposer(self.registry).is_write_intent(task.request):
            return {
                "mode": mode, "status": "BLOCKED", "diagnosis": None,
                "trace": [
                    {"state": "RECEIVED", "reason": "typed_request"},
                    {"state": "ROUTED", "reason": "write_intent_blocked"},
                    {"state": "TERMINAL", "reason": "write_approval_required"},
                ],
                "result": {"status": "BLOCKED", "reason": "write_approval_required",
                           "calls": 0, "diagnosis": None},
            }
        trace = [
            {"state": "RECEIVED", "reason": "typed_request"},
            {"state": "ROUTED", "reason": "registered_" + mode.lower()},
        ]
        if mode == "MEASURE":
            result = self.goal_agent.run(
                task.request, case, goals=task.goals
            )
            # Measurement RESOLVED is still NOT_EVALUATED for RCA.
            if result["diagnosis"] != "NOT_EVALUATED":
                raise PlanError("measurement_cannot_claim_rca")
            evidence = len(result["goal_facts"])
        else:
            result = self.rca_agent.run(
                task.request, case, workflow=task.workflow
            )
            evidence = len(result.get("evidence_ids", ()))
        trace.extend([
            {"state": "EXECUTED", "reason": "common_graph_runner"},
            {"state": "VERIFIED", "reason": "evidence_count:" + str(evidence)},
            {"state": "TERMINAL", "reason": result["status"]},
        ])
        return {
            "mode": mode, "status": result["status"],
            "diagnosis": (result.get("diagnosis")
                          if mode == "DIAGNOSE" else None),
            "trace": trace,
            "result": result,
        }
