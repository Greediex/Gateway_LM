"""Common READY selection and execution boundary for all diagnostic routes.

The policy may propose an order or scored preference, but all execution still
passes through GraphRunner.ready()/step() with typed authorization, capability,
scope, evidence verification and budgets. No alternative tool-call bypass.
"""
from __future__ import annotations

from .selection import ReadySelector


def execute_ready_once(runner, plan, goals=(), *, method="gos", k=4,
                       ordered_ids=None, favored=None, audit=None, ready=None):
    """Execute exactly one admissible READY node.

    `ordered_ids` is the Resolver/NBA policy order. With no explicit order,
    the GoS/BM25/Hybrid retrieval scores select among READY nodes.
    The audit entry is appended before execution so a failing invocation
    preserves the selected-node trace for postmortem analysis.
    """
    ready = runner.ready(plan) if ready is None else ready
    if not ready:
        return None, None
    retrieval = None
    if ordered_ids is not None:
        preferred = ReadySelector.choose(
            ready, ordered_ids=ordered_ids, favored=favored
        )
    else:
        retrieval = runner.registry.retrieve(
            runner.case["request"], goals, runner.state,
            k=k, method=method, excluded=runner.excluded,
        )
        preferred = ReadySelector.choose(
            ready, registry=runner.registry, scores=retrieval["scores"]
        )
        retrieval["ready_set"] = [node.id for node in ready]
        retrieval["selected_ready"] = preferred.id
        if audit is not None:
            audit.append(retrieval)
    # A stale explicit preferred node is now rejected by GraphRunner.step.
    return runner.step(plan, preferred.id), retrieval
