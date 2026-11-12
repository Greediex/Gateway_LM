"""GATEWAY_DESIGN: resolver-selected evidence and GoS-ranked READY scheduling."""
import copy
from ..core import PlanError
from .planner import NodeState
from .planning_stage import FunctionPlanner
from .runner import GraphRunner
from .routing import FunctionRouter
from .execution_kernel import execute_ready_once


def acquire(case, registry, state, *, method="gos", k=4, max_calls=12, max_repairs=2,
            router=None, planner=None):
    goals = registry.goal_ports[case['workflow']]
    router = router if router is not None else FunctionRouter()
    planner = planner if planner is not None else FunctionPlanner()
    runner = GraphRunner(registry, case, state, max_calls=max_calls, max_repairs=max_repairs)
    contracts, retrievals = [], []
    while True:
        view = copy.copy(state)
        view.capabilities = state.capabilities - runner.excluded
        contract = router.route(registry, view, case['request'], goals=goals, method=method)
        contract['plan_revision'] = max(contract['plan_revision'],
                                        runner.plans[-1].revision + 1 if runner.plans else 1)
        contracts.append(contract)
        candidates = contract['function_candidates']
        if not candidates or runner.calls >= max_calls or contract['decision'] in {'BLOCKED', 'ASK_USER'}:
            break
        plan = planner.compile(registry, state, contract)
        before = runner.calls
        retrievals.extend(run_plan(runner, plan, goals, method=method, k=k))
        runner.excluded.update(n.function_id for p in runner.plans for n in p.nodes.values()
                               if n.state in (NodeState.FAILED, NodeState.INCONCLUSIVE))
        if runner.calls == before:
            break
    unavailable = {goal: contracts[-1]['decision'] for goal in goals if state.fact(goal) is None}
    return {'contract_0': contracts[0], 'contract_0_history': contracts,
            'plans': [p.export() for p in runner.plans], 'events': runner.events,
            'retrievals': retrievals, 'calls': runner.calls, 'repairs': runner.repairs,
            'spent_declared_cost': runner.spent, 'unavailable_goals': unavailable,
            'unverified_goals': [g for g in goals if state.fact(g) is None],
            'upstream_kernel_calls': sum(r['upstream_kernel_used'] for r in retrievals)}


def run_plan(runner, plan, goals, *, method="gos", k=4):
    """Schedule one plan against the case's existing budgets and evidence."""
    state = runner.state
    runner.attach(plan)
    retrievals = []
    while True:
        ready = runner.ready(plan)
        if not ready:
            break
        try:
            node, _ = execute_ready_once(
                runner, plan, goals, method=method, k=k,
                ready=ready, audit=retrievals,
            )
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
