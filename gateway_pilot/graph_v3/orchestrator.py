"""Evidence-driven Core: persistent plan, GoS-ranked READY set, bounded repair."""
from ..core import PlanError
from .planner import Compiler, NodeState
from .runner import GraphRunner


def acquire(case, registry, state, *, method="gos", k=4, max_calls=12, max_repairs=2):
    goals = registry.goal_ports[case['workflow']]
    feasible, unavailable = [], {}
    for goal in goals:
        try:
            Compiler(registry).compile([goal], state)
            feasible.append(goal)
        except PlanError as exc:
            unavailable[goal] = str(exc)
    plan = Compiler(registry).compile(feasible, state)
    runner = GraphRunner(registry, case, state, max_calls=max_calls, max_repairs=max_repairs)
    retrievals = run_plan(runner, plan, goals, method=method, k=k)
    return {'plans': [p.export() for p in runner.plans], 'events': runner.events,
            'retrievals': retrievals, 'calls': runner.calls, 'repairs': runner.repairs,
            'spent_declared_cost': runner.spent, 'unavailable_goals': unavailable,
            'unverified_goals': [g for g in goals if state.fact(g) is None],
            'upstream_kernel_calls': sum(r['upstream_kernel_used'] for r in retrievals)}


def run_plan(runner, plan, goals, *, method="gos", k=4):
    """Schedule one plan against the case's existing budgets and evidence."""
    registry, case, state = runner.registry, runner.case, runner.state
    runner.attach(plan)
    retrievals = []
    while True:
        ready = runner.ready(plan)
        if not ready:
            break
        retrieval = registry.retrieve(case['request'], goals, state, k=k, method=method, excluded=runner.excluded)
        # Rank the eligible READY set with actual upstream scores. Dependencies
        # remain hard constraints; graph rank never makes a blocked node ready.
        preferred = min(ready, key=lambda n: (-retrieval['scores'].get('f:' + n.function_id, 0),
                                              registry.objective(n.function_id), n.id))
        retrieval['ready_set'] = [n.id for n in ready]
        retrieval['selected_ready'] = preferred.id
        retrievals.append(retrieval)
        try:
            node = runner.step(plan, preferred.id)
        except PlanError as exc:
            state.errors.append(str(exc))
            break
        if node is None:
            break
        if node.state in (NodeState.FAILED, NodeState.INCONCLUSIVE):
            try:
                plan = runner.repair(plan, node)
            except PlanError as exc:
                state.errors.append(str(exc))
                runner.events.append({'revision': plan.revision, 'repair_blocked': str(exc)})
    return retrievals
