"""Evidence-driven probe policy for a client Internet diagnosis."""

from ..core import PlanError


def probe_candidates(runner, goals):
    """Return only goals with a compiler-checked plan for this session."""
    revision = runner.plans[-1].revision + 1 if runner.plans else 1
    candidates, rejected = {}, {}
    for goal in goals:
        try:
            plan = runner.compiler().compile([goal], runner.state, revision=revision)
        except PlanError as exc:
            rejected[goal] = str(exc)
            continue
        if len(plan.nodes) > runner.max_calls - runner.calls:
            rejected[goal] = "insufficient_call_budget"
        else:
            candidates[goal] = plan
    return candidates, rejected


def run_client_probes(diag):
    """Choose the next evidence goal when the previous stage has settled."""
    attempted = set()

    def value(port, key):
        fact = diag.state.fact(port)
        return fact["value"].get(key) if fact else None

    while True:
        wan_ok = (value("wan.status", "link_up") is True
                  and value("wan.routes", "default_route") is True
                  and value("wan.probe", "loss_pct") == 0)
        client_loss = value("client.probe", "loss_pct")
        dns_code = value("dns.probe", "rcode")
        if wan_ok and (fault := diag.proof("gateway_dns_failure")):
            return fault
        if client_loss is not None and client_loss >= 50:
            return diag.observed("FINISH", "client_path_loss", "client.probe")

        reasons = {}
        if client_loss is None:
            reasons["client.probe"] = ("verify_ip_path_from_client" if wan_ok
                                       else "wan_unverified_measure_client_path")
        if wan_ok and dns_code is None:
            reasons["dns.probe"] = "external_ip_reachable_check_gateway_dns"
        query = value("dns.probe", "query")
        if client_loss == 0 and dns_code == "NOERROR" and query and query.rstrip("."):
            client_query = value("client.dns", "query")
            if client_query and client_query.rstrip(".").casefold() == query.rstrip(".").casefold():
                if value("client.dns", "rcode") in {"SERVFAIL", "TIMEOUT", "REFUSED"}:
                    return diag.observed("FINISH", "client_dns_failure", "client.dns", "client.probe", "dns.probe")
            if value("client.dns", "rcode") is None:
                reasons["client.dns"] = "compare_dns_from_client_and_router"

        if diag.runner.calls >= diag.runner.max_calls:
            break
        pending = tuple(goal for goal in reasons if goal not in attempted)
        if not pending:
            break
        candidates, rejected = probe_candidates(diag.runner, pending)
        attempted.update(rejected)
        event = {"after_call": diag.runner.calls, "wan_verified": wan_ok,
                 "candidates": {goal: plan.topological() for goal, plan in candidates.items()},
                 "rejected": rejected, "selected": None}
        diag.policy_steps.append(event)
        if not candidates:
            break
        goal = diag.order_probes(tuple(candidates), prechecked=True)[0]
        event.update(selected=goal, reason=reasons[goal])
        attempted.add(goal)
        diag.observe(goal, reasons[goal], plan=candidates[goal])

    if value("client.probe", "loss_pct") == 0:
        return diag.observed("INCOMPLETE", "client_ip_reachable", "client.probe")
    if wan_ok and dns_code == "NOERROR" and value("client.probe", "loss_pct") is None:
        return diag.observed("INCOMPLETE", "client_path_unverified", "dns.probe", "wan.probe")
    return None
