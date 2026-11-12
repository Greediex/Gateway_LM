"""Optional bounded LLM goal *proposal*, never a tool/Function authorization.

The model may only nominate existing read-only evidence ports. Exact snippets
from the user's request are required to make proposals auditable. Permissions,
target, dependency closure and runtime probes remain independent gates.
"""
from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence

from ..core import PlanError
from ..workflow import normalize
from .task_decomposer import GoalDecomposition


class BoundedGoalProposer:
    """Trusted local model interface: propose_goals(request, catalog) -> JSON.

    'catalog' contains only port names/descriptions and no live secrets or
    evidence. Model output is untrusted structured data; unsupported goals,
    insufficient grounding and unsafe actions always fail closed.
    """

    def __init__(self, model, *, min_confidence=0.85, max_goals=5):
        if getattr(model, "local_only", None) is not True or not callable(
            getattr(model, "propose_goals", None)
        ):
            raise ValueError("goal_model_must_be_trusted_local")
        if (type(min_confidence) not in (int, float)
                or not math.isfinite(min_confidence)
                or not 0.5 <= min_confidence <= 1.0
                or type(max_goals) is not int or not 1 <= max_goals <= 8):
            raise ValueError("invalid_goal_proposal_limits")
        self.model, self.min_confidence, self.max_goals = model, min_confidence, max_goals

    def propose(self, request, registry, state, decomposer):
        # A model can never turn a change into a read-side effect, including
        # compound requests containing a WRITE/restart/delete command.
        if decomposer.is_write_intent(request):
            return GoalDecomposition("BLOCKED", (), (request,),
                                     reason="write_intent_requires_approval")
        allowed = sorted({
            name
            for f in registry.functions.values()
            if registry.contract_allowed(f) and state.allowed(f)
            for name in f.outputs
            if not registry.ports[name].untrusted_text
        })
        if not allowed:
            return GoalDecomposition("NEEDS_INPUT", (), (request,),
                                     reason="no_authorized_read_goals")
        # The model may inspect names + catalog descriptions only. Even if a
        # model invents tools or arguments they will not enter this contract.
        docs = []
        for name in allowed:
            producers = [f.description[:200] for f in registry.functions.values()
                         if name in f.outputs and registry.contract_allowed(f) and state.allowed(f)]
            docs.append({"port": name, "description": " ".join(producers)[:320]})
        try:
            output = self.model.propose_goals(request, tuple(docs))
        except (OSError, RuntimeError, ValueError, TypeError, TimeoutError):
            return GoalDecomposition("NEEDS_INPUT", (), (request,),
                                     reason="model_unavailable")
        if isinstance(output, str):
            if len(output) > 8192:
                return GoalDecomposition("NEEDS_INPUT", (), (request,), reason="invalid_model_output")
            try:
                output = json.loads(output)
            except (ValueError, TypeError):
                return GoalDecomposition("NEEDS_INPUT", (), (request,), reason="invalid_model_output")
        if not isinstance(output, Mapping) or set(output) != {
            "goals", "confidence", "spans", "needs_clarification"
        }:
            return GoalDecomposition("NEEDS_INPUT", (), (request,), reason="invalid_model_output")
        goals = output["goals"]
        score = output["confidence"]
        spans = output["spans"]
        if (type(score) not in (int, float) or not math.isfinite(score)
                or not 0 <= score <= 1 or score < self.min_confidence
                or type(output["needs_clarification"]) is not bool
                or output["needs_clarification"]
                or not isinstance(goals, list) or not 1 <= len(goals) <= self.max_goals
                or any(not isinstance(g, str) for g in goals)
                or len(set(goals)) != len(goals)
                or any(g not in allowed for g in goals)
                or not isinstance(spans, dict) or set(spans) != set(goals)):
            return GoalDecomposition("NEEDS_INPUT", (), (request,),
                                     reason="unsupported_or_uncertain_model_goals")
        plain = normalize(request)
        if any(not isinstance(spans[g], str) or
               not 2 <= len(spans[g]) <= 128 or
               normalize(spans[g]) not in plain or
               not normalize(spans[g]).strip() for g in goals):
            return GoalDecomposition("NEEDS_INPUT", (), (request,),
                                     reason="model_goals_not_grounded_in_request")
        return GoalDecomposition("READY", tuple(goals), (request,),
                                 reason="model_proposed_registered_read_goals")
