"""One READY-node selection policy shared by resolver and retrieval execution.

Dependency, permission, risk, target and data validity checks remain in
GraphRunner.ready()/step(). Scores are ordering hints only, never authority.
"""
from __future__ import annotations

from ..core import PlanError


class ReadySelector:
    @staticmethod
    def choose(ready, *, registry=None, scores=None, ordered_ids=(), favored=None):
        if not ready:
            return None
        if favored is not None:
            chosen = next((n for n in ready if n.function_id == favored), None)
            if chosen is not None:
                return chosen
        if ordered_ids:
            priority = {fid: i for i, fid in enumerate(ordered_ids)}
            return min(ready, key=lambda n: (priority.get(n.function_id, len(priority)),
                                              n.id))
        if scores is not None:
            if registry is None:
                raise PlanError("selector_registry_required_for_scores")
            return min(ready, key=lambda n: (-scores.get("f:" + n.function_id, 0),
                                              registry.objective(n.function_id), n.id))
        # Runner.run() and direct tests preserve compiler's original order.
        return ready[0]
