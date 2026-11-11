"""Run the upstream ReAct graph with Gateway's local diagnostic policy and tool."""

from ..core import PlanError
from .dynamic_policy import DiagnosticPolicy
from .skilldag import check_skills


UPSTREAM_COMMIT = "d3b771365dbe01e92bdd28286ee41610cd69302f"
MAX_MODEL_REVIEWS = 2
REVIEW_FIELDS = {
    "wifi.station": ("associated", "rssi_dbm"),
    "client.ipv4": ("configured",),
    "wan.status": ("link_up",),
    "wan.routes": ("default_route",),
    "wan.probe": ("loss_pct",),
    "client.probe": ("loss_pct",),
    "dhcp.leases": ("lease_valid",),
    "dhcp.pool": ("free_addresses",),
    "dhcp.service": ("running",),
    "live.gateway": ("replies", "loss_pct"),
    "live.internet": ("replies", "loss_pct"),
    "live.dns": ("resolved",),
}


def review_stage(diag, candidates, event):
    """Ask the model at a branch or after a failed check, within a fixed budget."""
    default = next(iter(candidates))
    last = next((item for item in reversed(diag.runner.events) if "node" in item), {})
    failed_check = ({"function": last["node"], "state": last["state"]}
                    if last.get("state") in {"FAILED", "INCONCLUSIVE"} else None)
    branch = len(candidates) > 1 and all(len(stage.goals) == 1 for stage in candidates)
    if len(diag.advice) >= MAX_MODEL_REVIEWS or not (branch or (len(candidates) == 1 and failed_check)):
        return default

    facts = {}
    for port, fields in REVIEW_FIELDS.items():
        fact = diag.state.fact(port)
        if fact is not None:
            facts[port] = {"id": fact["id"], **{key: fact["value"][key] for key in fields if key in fact["value"]}}
    choices = {stage.label: {"purpose": stage.reason, "functions": plan.topological()}
               for stage, plan in candidates.items()}
    evidence_ids = {fact["id"] for fact in facts.values()}
    advice = {"skill": "SK10", "model": diag.advisor.model, "candidates": list(choices),
              "selected": default.label, "accepted": False, "after_call": diag.runner.calls,
              "input_evidence_ids": sorted(evidence_ids), "failed_check": failed_check}
    event["advice_index"] = len(diag.advice)
    diag.advice.append(advice)
    try:
        result = diag.advisor.reason_next(diag.case["request"], facts, choices, failed_check)
    except (OSError, KeyError, TypeError, ValueError) as exc:
        advice["reason"] = type(exc).__name__
        return default

    if not isinstance(result, dict):
        result = {}
    proposed, hypothesis, cited = (result.get(key) for key in ("next_stage", "hypothesis", "evidence_ids"))
    if not isinstance(proposed, str) or proposed not in choices:
        advice["reason"] = "outside_admissible_stages"
        return default
    if (not isinstance(hypothesis, str) or not 1 <= len(hypothesis.strip()) <= 240
            or not isinstance(cited, list) or len(cited) > 4 or (evidence_ids and not cited)
            or any(not isinstance(key, str) or key not in evidence_ids for key in cited)):
        advice["reason"] = "invalid_hypothesis_or_evidence"
        return default
    advice.update(selected=proposed, accepted=True, hypothesis=hypothesis.strip(),
                  evidence_ids=list(dict.fromkeys(cited)))
    return next(stage for stage in candidates if stage.label == proposed)


def run_react(diag, *, policy=None):
    from langchain_core.messages import AIMessage, HumanMessage
    from langchain_core.tools import tool
    from langsmith import tracing_context

    from .react_template.graph import build_graph
    from .react_template.state import State

    policy = policy or DiagnosticPolicy(diag)
    runner = diag.runner
    terminal, pending = None, None
    steps = []

    def choose_stage(candidates, event):
        return review_stage(diag, candidates, event)

    stage_advisor = choose_stage if callable(getattr(diag.advisor, "reason_next", None)) else None

    def verify_skill_bundle(plan):
        skills = dict.fromkeys(node.skill_context for node in plan.nodes.values())
        checked = check_skills(runner.registry.gs, skills)
        if checked["conflicts"]:
            raise PlanError("skilldag_conflict")
        plan.audit.append({"operator": "SKILLDAG_CHECK", "revision": plan.revision, **checked})

    @tool
    def run_verified_stage(stage_label: str) -> dict:
        """Execute the single stage selected by the local Gateway policy."""
        nonlocal pending
        if pending is None or pending[0].label != stage_label:
            raise PlanError("react_stage_not_selected")
        stage, plan = pending
        pending = None
        facts = policy.execute_stage(stage, plan)
        observation = {port: fact["id"] if fact else None for port, fact in facts.items()}
        steps.append({"node": "tools", "stage": stage.label, "evidence": observation})
        return observation

    def call_model(state: State):
        nonlocal terminal, pending
        selection = policy.select_stage(choose_stage=stage_advisor)
        if isinstance(selection, tuple) and not state.is_last_step:
            pending = selection
            stage = selection[0]
            steps.append({"node": "call_model", "stage": stage.label})
            return {"messages": [AIMessage(content="", tool_calls=[{
                "name": run_verified_stage.name, "args": {"stage_label": stage.label},
                "id": f"gateway-stage-{len(steps)}",
            }])]}
        terminal = selection if isinstance(selection, dict) else None
        steps.append({"node": "call_model", "action": terminal["action"] if terminal else "INCOMPLETE"})
        return {"messages": [AIMessage(content=terminal["response"] if terminal else "")]}

    graph = build_graph(call_model, [run_verified_stage])
    # Each stage consumes at least one distinct goal, even if its tool fails.
    limit = 2 * len(runner.registry.ports) + 5
    runner.plan_validator = verify_skill_bundle
    try:
        with tracing_context(enabled=False):
            graph.invoke({"messages": [HumanMessage(content=diag.case["request"])]},
                         config={"recursion_limit": limit})
    finally:
        runner.plan_validator = None
    return terminal, {"engine": "langgraph", "upstream_commit": UPSTREAM_COMMIT, "steps": steps}
