"""Text-first, evidence-driven diagnostic workflow for the read-only replay pilot."""

import argparse
import copy
import json
import re
import sys
import unicodedata

from .core import ROOT, PlanError, Registry, read_json
from .adapters import gate_capabilities
from .graph_v3.claims import claim_book
from .graph_v3.graphs import GraphRegistry
from .graph_v3.context import retrieve_context
from .graph_v3.dynamic_policy import DiagnosticPolicy
from .graph_v3.orchestrator import run_plan
from .graph_v3.runner import GraphRunner
from .graph_v3.selection import ReadySelector
from .graph_v3.resolver import resolve
from .graph_v3.state import CaseState
from .workflow_advisor import OllamaProbeAdvisor
from .rag import DEFAULT_CATALOG, REPLAY_FIRMWARE, REPLAY_PRODUCT, RunbookIndex, explain


def normalize(text):
    text = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(re.findall(r"\w+", text))


TOPICS = {
    "WF-018": r"\b(?:wan|uplink|default route|dinh tuyen|mat goi)\b",
    "WF-023": r"\b(?:dns|resolver|phan giai ten mien)\b",
    "WF-024": r"\b(?:dhcp|cap ip|cap dia chi ip|khong co ip|chua co ip|chua nhan duoc ip|no ip)\b",
    "WF-039": r"\b(?:cpu|ram|luu tru|qua tai|tai nguyen|suc khoe|resources?|(?:system|gateway|router) health)\b",
}
CLIENT_WORDS = r"\b(?:laptop|dien thoai|phone|may tinh|tablet|thiet bi)\b"
INTERNET_WORDS = r"\b(?:wi fi|wifi|internet|vao mang|truy cap mang|mat mang|mang cham|mang chap chon)\b"
CHANGE_REQUEST = (
    r"^(?:hay |vui long |lam on |please )?(?:tu )?"
    r"(?:doi|thay|sua|dat|cai dat|cap nhat|ap dung|change|set|apply|update)\b"
)


def route(text):
    """Use the request alone. An unmatched or conflicting intent needs clarification."""
    if re.search(CHANGE_REQUEST, text):
        return "WF-WRITE"
    matches = [workflow for workflow, pattern in TOPICS.items() if re.search(pattern, text)]
    has_client = re.search(CLIENT_WORDS, text)
    has_gateway = re.search(r"\b(?:gateway|router|modem)\b", text)
    client_symptom = (re.search(INTERNET_WORDS, text)
                      and (has_client or re.search(r"\b(?:wi fi|wifi)\b", text)))
    if client_symptom and set(matches) <= {"WF-018", "WF-023"}:
        return "WF-INTERNET"
    if matches == ["WF-023"] and has_client and not has_gateway:
        return "WF-INTERNET"
    if matches:
        return matches[0] if len(matches) == 1 else None
    if re.search(INTERNET_WORDS, text):
        return "WF-018" if has_gateway else "WF-INTERNET"
    return None


def match_device(text, devices):
    matches = []
    padded = f" {text} "
    for device in devices:
        aliases = [normalize(alias) for alias in (device["selector"], *device.get("aliases", []))]
        if any(alias and f" {alias} " in padded for alias in aliases):
            matches.append(device)
    return matches[0] if len(matches) == 1 else None


_rule_route = route


def intake_supported(text, workflow):
    """Require a compatible symptom before allowing an LLM proposal to route a read."""
    dns_symptom = r"\b(?:dns|ten mien|phan giai|resolver)\b"
    if workflow == "WF-INTERNET":
        return bool(re.search(CLIENT_WORDS, text) and re.search(dns_symptom + "|" + INTERNET_WORDS, text))
    if workflow == "WF-023":
        return bool(re.search(r"\b(?:router|gateway|modem)\b", text) and re.search(dns_symptom, text))
    if workflow == "WF-024":
        return bool(re.search(TOPICS[workflow] + r"|\b(?:chua duoc cap ip|lay dia chi mai khong duoc)\b", text))
    return bool(re.search(TOPICS[workflow], text))


MESSAGES = {
    "intent_unclear": "Bạn đang gặp sự cố gì và trên thiết bị nào?",
    "target_ambiguous": "Bạn đang hỏi thiết bị nào? Cho mình tên thiết bị để kiểm tra đúng máy.",
    "unsafe_change_denied": "Luồng chẩn đoán này chỉ đọc trạng thái thiết bị.",
    "read_permission_denied": "Phiên này chưa có quyền đọc trạng thái cần kiểm tra.",
    "insufficient_evidence": "Chưa đủ dữ liệu kiểm tra để xác định nguyên nhân.",
    "client_path_unverified": "Các phép kiểm tra WAN và DNS từ router đều đạt. Chưa đo được kết nối từ thiết bị nên chưa xác định được nguyên nhân.",
    "client_not_associated": "Tại thời điểm kiểm tra, thiết bị chưa kết nối vào Wi-Fi của router.",
    "client_ipv4_unconfigured": "Thiết bị đã vào Wi-Fi nhưng chưa có địa chỉ IPv4 được cấu hình.",
    "client_path_loss": "Phép thử IP từ thiết bị ghi nhận mất gói cao. Chưa xác định được vị trí gây mất gói.",
    "client_ip_reachable": "Thiết bị tới được IP đã thử. Cần thêm dữ liệu về trang hoặc ứng dụng đang gặp lỗi để tìm nguyên nhân.",
    "client_dns_failure": "Thiết bị tới được IP đã thử nhưng truy vấn DNS từ chính thiết bị thất bại. Router phân giải được cùng tên miền.",
    "wan_link_down": "Router ghi nhận cổng WAN mất liên kết.",
    "wan_no_route": "Cổng WAN đã lên nhưng router thiếu tuyến mặc định.",
    "wan_packet_loss": "Phép thử IP từ router ghi nhận mất gói cao.",
    "gateway_dns_failure": "Router tới được IP đã thử nhưng truy vấn qua DNS của router thất bại.",
    "gateway_ip_reachable_dns_unverified": "Router tới được IP đã thử. Chưa xác minh được DNS của router.",
    "wifi_weak_signal": "Router đo được tín hiệu Wi-Fi yếu của thiết bị.",
    "dhcp_pool_exhausted": "Thiết bị chưa có lease và dải địa chỉ DHCP đã hết chỗ.",
    "dhcp_service_down": "Thiết bị chưa có lease và dịch vụ DHCP đang dừng.",
    "client_no_lease": "Thiết bị chưa có lease DHCP. Chưa xác định được nguyên nhân.",
    "system_memory_pressure": "Dung lượng RAM khả dụng trên router đang thấp.",
    "system_cpu_load": "Mức sử dụng CPU của router đang cao.",
    "system_storage_full": "Bộ nhớ lưu trữ của router gần đầy.",
    "no_fault_observed": "Các phép kiểm tra trong phạm vi yêu cầu đều đạt.",
}

HTML_WORKFLOW_IDS = {"WF-INTERNET": "WF-018", "WF-023": "WF-023",
                     "WF-024": "WF-024", "WF-039": "WF-039"}


def workflow_registry():
    """Extend the replay catalog for this entry point without changing frozen fixtures."""
    data = read_json(ROOT / "data" / "registry.json")
    data["port_fields"]["client.dns"] = {"rcode": "str", "query": "str"}
    data["functions"].append({
        "id": "client.dns", "produces": ["client.dns"], "requires": ["client.ipv4"],
        "scope": "client", "skills": ["SK05"], "description": "Measure DNS from the identified client",
        "risk": "READ", "ttl_s": 30, "version": "0.1.0", "adapter": "synthetic_replay/v1",
    })
    return GraphRegistry(Registry(data=data))


def verdict(action, diagnosis, evidence_ids=()):
    return {"action": action, "diagnosis": diagnosis, "evidence_ids": list(evidence_ids),
            "response": MESSAGES[diagnosis]}


def finish(result, terminal, book=None):
    """Case status from the concluded claim's scope/severity (C4); non-claim verdicts as before."""
    action, diagnosis = terminal["action"], terminal["diagnosis"]
    claimed = book.status(diagnosis, action, result["workflow"]) if book is not None else None
    if action == "ASK_USER":
        status = "NEEDS_INPUT"
    elif diagnosis in {"unsafe_change_denied", "read_permission_denied"}:
        status = "BLOCKED"
    elif claimed is not None:
        status = claimed
    else:
        status = "RESOLVED" if action == "FINISH" else "INCONCLUSIVE"
    return {**result, "terminal": terminal, "case_status": status}


def verify_terminal(terminal, diag):
    """Every concluded claim is re-checked on Case State; the Core supplies its evidence ids."""
    if terminal is None or terminal["action"] == "ASK_USER":
        return terminal
    claim = diag.claims.lookup(terminal["diagnosis"], diag.case.get("workflow"))
    if claim is None:
        return terminal
    truth, ids = claim.evaluate(diag.state)
    if truth.value != "TRUE":
        return verdict("INCOMPLETE", "insufficient_evidence")
    return {**terminal, "evidence_ids": ids}


class Diagnostic:
    def __init__(self, case, registry, method, max_calls, advisor, selection="resolver"):
        if selection not in ("resolver", "nba"):
            raise ValueError("invalid_selection")
        self.selection = selection
        self.case = case
        self.state = CaseState(case, registry)
        self.runner = GraphRunner(registry, case, self.state, max_calls=max_calls)
        self.method = method
        self.advisor = advisor
        self.advice = []
        self.stages = []
        self.retrievals = []
        self.policy_steps = []
        self.contracts = []

    def run_resolver(self, *, goals=None, intent=None, reroute=None, goal_only=False, selected_skills=()):
        """GATEWAY_DESIGN: re-resolve after each verified runner batch.

        The existing policy is consulted only for terminal evidence checks;
        its stages never choose resolver functions or their execution order.
        Optional C2 goals/reroute reuse this runner and its verified CaseState.
        Every terminal verdict is re-checked by the claim contracts (C4).
        """
        registry, runner = self.runner.registry, self.runner
        goals = registry.goal_ports[self.case["workflow"]] if goals is None else goals
        terminal_policy = DiagnosticPolicy(self)
        while True:
            view = copy.copy(self.state)
            view.capabilities = self.state.capabilities - runner.excluded
            contract = resolve(registry, view, self.case["request"], goals=goals, method=self.method,
                               intent=intent, selected_skills=selected_skills)
            previous = self.contracts[-1]["plan_revision"] if self.contracts else 0
            contract["plan_revision"] = max(previous + 1, contract["plan_revision"])
            self.contracts.append(contract)
            if goal_only and all(self.state.fact(g) is not None for g in goals):
                return None
            terminal = None if goal_only else terminal_policy.decide()
            if isinstance(terminal, dict):
                return terminal
            candidates = contract["function_candidates"]
            if (runner.calls >= runner.max_calls or not candidates
                    or contract["decision"] in {"BLOCKED", "ASK_USER"}):
                break
            try:
                compiler = runner.compiler()
                compiler.excluded.update(set(registry.functions) - set(candidates))
                plan = compiler.compile((), self.state, requested=candidates,
                                        revision=contract["plan_revision"], skill_context=contract["skill_context"])
                runner.attach(plan)
                ready = runner.ready(plan)
                if not ready:
                    break
                # selection="nba": deterministic next-best-action over the claim contracts
                # (HTML 08/07). Default keeps the resolver's ranking: on the 288 replay runs
                # NBA changed no diagnosis but spent 5 more calls.
                best = (self.claims.next_best_action(registry, self.state, self.case.get("workflow"),
                                                     [n.function_id for n in ready])
                        if self.selection == "nba" else None)
                preferred = ReadySelector.choose(ready, ordered_ids=candidates, favored=best)
                node = runner.step(plan, preferred.id)
            except PlanError as exc:
                self.state.errors.append(str(exc))
                break
            if node is None:
                break
            # A batch is one invocation (possibly several verified outputs).
            # Failed probes are not silently replayed under a fresh plan.
            outputs = registry.functions[node.function_id].outputs
            if not self.state.completed(registry.functions[node.function_id]):
                runner.excluded.add(node.function_id)
            terminal_policy.attempted.update(outputs)
            if reroute is not None:
                revised = reroute(self)
                if revised is not None:
                    self.case["workflow"] = revised["workflow"]
                    goals = revised["goals"]
                    selected_skills = registry.workflows[revised["workflow"]]["skill_ids"]
                    terminal_policy = DiagnosticPolicy(self)
                    goal_only = False
                    reroute = None
            terminal = None if goal_only else terminal_policy.decide()
            if isinstance(terminal, dict):
                return terminal
        # Reuse the policy's existing partial/unresolved terminal paths once
        # no admissible evidence remains, without executing policy stages.
        if goal_only:
            return None
        terminal_policy.attempted.update(registry.ports)
        terminal = terminal_policy.decide()
        return terminal if isinstance(terminal, dict) else None

    def observe_stage(self, goals, reason, *, plan=None):
        stage = {"goal": goals[0], "reason": reason, "after_call": self.runner.calls}
        if len(goals) > 1:
            stage["goals"] = list(goals)
        self.stages.append(stage)
        if any(self.state.fact(port) is None for port in goals):
            try:
                if plan is None:
                    revision = self.runner.plans[-1].revision + 1 if self.runner.plans else 1
                    plan = self.runner.compiler().compile(goals, self.state, revision=revision)
                self.retrievals.extend(run_plan(self.runner, plan, goals, method=self.method))
            except PlanError as exc:
                stage["error"] = str(exc)
        facts = {port: self.state.fact(port) for port in goals}
        if len(goals) > 1:
            stage["evidence_ids"] = {port: fact["id"] for port, fact in facts.items() if fact}
        else:
            fact = facts[goals[0]]
            stage["evidence_id"] = fact["id"] if fact else None
        return facts

    def observe(self, port, reason):
        fact = self.observe_stage((port,), reason)[port]
        return fact["value"] if fact else {}

    def order_probes(self, goals, *, prechecked=False):
        if self.advisor is None or self.runner.calls >= self.runner.max_calls:
            return goals
        eligible = []
        for goal in goals:
            if self.state.fact(goal):
                continue
            if not prechecked:
                try:
                    self.runner.compiler().compile([goal], self.state)
                except PlanError:
                    continue
            eligible.append(goal)
        if len(eligible) < 2:
            return goals
        facts = {}
        for port, key in (("wifi.station", "associated"), ("client.ipv4", "configured"),
                          ("wan.status", "link_up"), ("wan.routes", "default_route"),
                          ("wan.probe", "loss_pct")):
            fact = self.state.fact(port)
            if fact:
                facts[port] = {"id": fact["id"], key: fact["value"][key]}
        event = {"skill": "SK10", "candidates": eligible, "selected": goals[0], "accepted": False}
        self.advice.append(event)
        try:
            selection = self.advisor(self.case["request"], facts, tuple(eligible))
        except (OSError, KeyError, TypeError, ValueError) as exc:
            event["reason"] = type(exc).__name__
            return goals
        if not isinstance(selection, str) or selection not in eligible:
            event["reason"] = "outside_admissible_probes"
            return goals
        event.update(selected=selection, accepted=True)
        return (selection, *(goal for goal in goals if goal != selection))

    @property
    def claims(self):
        return claim_book(self.runner.registry)

    def proof(self, *diagnoses):
        for diagnosis in diagnoses:
            supported, ids = self.claims.support(diagnosis, self.state, self.case.get("workflow"))
            if supported and ids:
                return verdict("FINISH", diagnosis, ids)
        return None

    def observed(self, action, diagnosis, *ports):
        facts = [self.state.fact(port) for port in ports]
        if not all(facts):
            return None
        claim = self.claims.lookup(diagnosis, self.case.get("workflow"))
        if claim is None:
            return verdict(action, diagnosis, [fact["id"] for fact in facts])
        truth, ids = claim.evaluate(self.state)
        return verdict(action, diagnosis, ids) if truth.value == "TRUE" else None

    def unresolved_client(self):
        if any(e["port"] == "client.identity" and e["status"] == "AMBIGUOUS"
               for e in self.state.evidence):
            return verdict("ASK_USER", "target_ambiguous")
        return verdict("INCOMPLETE", "insufficient_evidence")

    def trace(self):
        trace = {"stages": self.stages, "advice": self.advice, "plans": [p.export() for p in self.runner.plans],
                "events": self.runner.events, "retrievals": self.retrievals,
                "calls": self.runner.calls, "repairs": self.runner.repairs,
                "errors": self.state.errors, "executed": self.state.executed,
                "evidence": self.state.public()["evidence"]}
        if self.contracts:
            trace["contract_0"] = self.contracts
        # T7: runner -> evidence (B) and evidence -> planner (C) after this run.
        trace["contract_a"] = []
        for plan in self.runner.plans:
            try:
                trace["contract_a"].append(plan.export_contract_a())
            except PlanError as exc:  # a plan rejected by structural validation is reported, not hidden
                trace["contract_a"].append({"revision": plan.revision, "error": str(exc)})
        trace["contract_b"] = self.runner.contract_b
        trace["contract_c"] = self.state.export_contract_c(
            self.runner.registry.goal_ports.get(self.case.get("workflow"), ()), exhausted=True)
        return trace


def wan(diag):
    link = diag.observe("wan.status", "check_physical_link")
    if link.get("link_up") is not True:
        return diag.proof("wan_link_down")
    route_state = diag.observe("wan.routes", "link_up_check_default_route")
    if route_state.get("default_route") is not True:
        return diag.proof("wan_no_route")
    diag.observe("wan.probe", "route_exists_probe_external_ip")
    return diag.proof("wan_packet_loss")


def wan_workflow(diag):
    return wan(diag) or diag.proof("no_fault_observed")


def dns_workflow(diag):
    if diag.observe("dns.probe", "check_configured_resolver"):
        wan(diag)
    return diag.proof("gateway_dns_failure", "no_fault_observed")


def dhcp(diag):
    lease = diag.observe("dhcp.leases", "check_lease_for_selected_device")
    if diag.state.fact("client.identity") is None:
        return diag.unresolved_client()
    if not lease:
        return None
    diag.observe("dhcp.pool", "check_available_addresses")
    fault = diag.proof("dhcp_pool_exhausted")
    if fault:
        return fault
    diag.observe("dhcp.service", "check_dhcp_service")
    return diag.proof("dhcp_service_down", "client_no_lease")


def dhcp_workflow(diag):
    return dhcp(diag) or diag.proof("no_fault_observed")


def system_workflow(diag):
    diag.observe("system.resources", "measure_cpu_memory_storage")
    return diag.proof("system_memory_pressure", "system_cpu_load",
                      "system_storage_full", "no_fault_observed")


def internet_workflow(diag):
    wifi = diag.observe("wifi.station", "check_client_association_and_signal")
    if diag.state.fact("client.identity") is None:
        return diag.unresolved_client()
    if wifi.get("associated") is False:
        return diag.observed("FINISH", "client_not_associated", "wifi.station")
    if wifi.get("associated") is not True:
        return None
    weak = diag.proof("wifi_weak_signal")
    if weak:
        return weak
    ip = diag.observe("client.ipv4", "check_client_address")
    if ip.get("configured") is False:
        return dhcp(diag) or diag.observed("FINISH", "client_ipv4_unconfigured",
                                          "wifi.station", "client.ipv4")
    if not ip.get("configured") or not ip.get("address"):
        return None
    wan_fault = wan(diag)
    if wan_fault:
        return wan_fault
    wan_proof = diag.state.fact("wan.probe")
    if not wan_proof or wan_proof["value"]["loss_pct"] != 0:
        return None
    reasons = {"dns.probe": "external_ip_reachable_check_gateway_dns",
               "client.probe": "verify_ip_path_from_client"}
    measured = {}
    for goal in diag.order_probes(tuple(reasons)):
        measured[goal] = diag.observe(goal, reasons[goal])
        if goal == "dns.probe":
            dns_fault = diag.proof("gateway_dns_failure")
            if dns_fault:
                return dns_fault
        elif measured[goal].get("loss_pct", 0) >= 50:
            return diag.observed("FINISH", "client_path_loss", "client.probe")
    dns, client = measured["dns.probe"], measured["client.probe"]
    if client.get("loss_pct") == 0:
        query = dns.get("query")
        if (dns.get("rcode") == "NOERROR" and isinstance(query, str) and query.rstrip(".")
                and "client.dns" in diag.state.capabilities):
            client_dns = diag.observe("client.dns", "compare_dns_from_client_and_router")
            if (client_dns.get("query", "").rstrip(".").casefold() == query.rstrip(".").casefold()
                    and client_dns.get("rcode") in {"SERVFAIL", "TIMEOUT", "REFUSED"}):
                return diag.observed("FINISH", "client_dns_failure", "client.dns", "client.probe", "dns.probe")
        return diag.observed("INCOMPLETE", "client_ip_reachable", "client.probe")
    if dns.get("rcode") == "NOERROR" and not client:
        return diag.observed("INCOMPLETE", "client_path_unverified", "dns.probe", "wan.probe")
    return None


WORKFLOWS = {"WF-018": wan_workflow, "WF-023": dns_workflow, "WF-024": dhcp_workflow,
             "WF-039": system_workflow, "WF-INTERNET": internet_workflow}


def diagnose(request, replay, *, registry=None, method="gos", max_calls=12, advisor=None,
             context_bytes=None, dynamic=True, react=False, route="auto", workflow=None, turn_type=None,
             plan_hint=None, reroute=None, selection="resolver", device_selector=None,
             return_state=False):
    """Run from request text and trusted replay inventory, with no fixture verdict as input."""
    text = normalize(request)
    if route not in {"auto", "fastpath", "resolver"}:
        raise ValueError("invalid_diagnostic_route")
    workflow = _rule_route(text) if workflow is None else workflow
    intent = turn_type or ("CHANGE" if workflow == "WF-WRITE" else None)
    registry = registry or workflow_registry()
    intake = {"source": "rules"}
    understand = getattr(advisor, "understand_request", None)
    if workflow is None and react and callable(understand):
        intake = {"source": "llm", "model": advisor.model, "accepted": False}
        try:
            proposed = understand(request)
        except (OSError, KeyError, TypeError, ValueError) as exc:
            intake["reason"] = type(exc).__name__
        else:
            if isinstance(proposed, str) and proposed in WORKFLOWS and intake_supported(text, proposed):
                workflow = proposed
                intake["accepted"] = True
    chosen_route = route
    if route == "auto":
        chosen_route = "fastpath" if workflow in WORKFLOWS and registry.goal_ports.get(workflow) else "resolver"
    result = {"request": request, "workflow": workflow, "workflow_id": HTML_WORKFLOW_IDS.get(workflow),
              "route": chosen_route,
              "target": None, "intake": intake,
              "execution": "synthetic_replay", "decision_source": "core_rules"}
    def intake_contract():
        empty_case = {"target": {}, "capabilities": replay["capabilities"]}
        if "permissions" in replay:
            empty_case["permissions"] = replay["permissions"]
        goals = registry.goal_ports.get(workflow, ())
        contract = resolve(registry, CaseState(empty_case, registry), request, goals=goals, method=method,
                           intent=intent)
        return {"contract_0": [contract], "calls": 0, "executed": []}

    if chosen_route == "resolver" and (workflow is None or workflow == "WF-WRITE"):
        result["graph"] = intake_contract()
        # Direct callers retain legacy clarification. assistant.answer supplies
        # the workflow and turn type from the confidence-aware C2 router.
    if workflow is None:
        return finish(result, verdict("ASK_USER", "intent_unclear"))
    if workflow == "WF-WRITE" or intent == "CHANGE":
        return finish(result, verdict("INCOMPLETE", "unsafe_change_denied"))
    permission = "system.read" if workflow == "WF-039" else "network.read"
    if "permissions" in replay and permission not in replay["permissions"]:
        if chosen_route == "resolver":
            result["graph"] = intake_contract()
        return finish(result, verdict("INCOMPLETE", "read_permission_denied"))

    target = {"scope": "gateway", "id": "gateway_01"}
    world = dict(replay["world"])
    client_plan = plan_hint is not None and any(registry.ports[g].scope == "client" for g in plan_hint["goals"])
    if (plan_hint is None and workflow in ("WF-024", "WF-INTERNET") and turn_type != "LOOKUP") or client_plan:
        # A session reply names the device explicitly; it must still be in the trusted inventory.
        device = (next((d for d in replay.get("devices", []) if d["selector"] == device_selector), None)
                  if device_selector is not None else match_device(text, replay.get("devices", [])))
        if device is None:
            if chosen_route == "resolver":
                result["graph"] = intake_contract()
            return finish(result, verdict("ASK_USER", "target_ambiguous"))
        target = {"scope": "client", "selector": device["selector"]}
        if device.get("client_id"):
            target["client_id"] = device["client_id"]
        world.update(device["world"])
    # Only the replay executor consumes observations. Planner sees verified facts.
    initial = [e for e in replay.get("initial_evidence", []) if e["scope"] == "gateway"
               or (target.get("client_id") and e["target"] == target["client_id"])]
    capabilities, probe_failures = replay["capabilities"], {}
    adapter = replay.get("adapter")
    if adapter is not None:  # T8: a Function whose probe failed never reaches the planner
        capabilities, probe_failures = gate_capabilities(replay["capabilities"], adapter.probe())
    case = {"request": request, "workflow": workflow, "target": target, "world": world,
            "capabilities": capabilities, "initial_evidence": initial}
    if adapter is not None:
        case["adapter"] = adapter
    if "permissions" in replay:
        case["permissions"] = replay["permissions"]
    diag = Diagnostic(case, registry, method, max_calls, advisor, selection=selection)
    if context_bytes is not None:
        result["skill_context"] = retrieve_context(registry, diag.state, request,
                                                   registry.goal_ports[workflow], max_bytes=context_bytes, method=method)
    if chosen_route == "resolver":
        terminal = diag.run_resolver(
            goals=plan_hint["goals"] if plan_hint else None, intent=intent, reroute=reroute,
            goal_only=bool(plan_hint and (turn_type == "LOOKUP" or plan_hint.get("reroute_after_evidence")
                                          or len(plan_hint.get("workflows", [])) > 1
                                          or workflow not in WORKFLOWS)),
            selected_skills=tuple(dict.fromkeys(s for wid in plan_hint.get("workflows", [workflow])
                                                for s in registry.workflows[wid]["skill_ids"])) if plan_hint else ())
        if diag.case["workflow"] != workflow:
            workflow = diag.case["workflow"]
            result.update(workflow=workflow, workflow_id=HTML_WORKFLOW_IDS.get(workflow))
        result["decision_source"] = "function_resolver"
    elif react:
        from .graph_v3.react_runtime import run_react
        terminal, react_trace = run_react(diag)
        result["decision_source"] = "langgraph_react"
    elif dynamic:
        terminal = DiagnosticPolicy(diag).run()
        result["decision_source"] = "dynamic_policy"
    else:
        terminal = WORKFLOWS[workflow](diag)
    trace = diag.trace()
    if plan_hint and (turn_type == "LOOKUP" or len(plan_hint.get("workflows", [])) > 1
                      or plan_hint.get("reroute_after_evidence")):
        result["goal_facts"] = [fact for g in plan_hint["goals"]
                                if (fact := diag.state.fact(g)) is not None]
    if react or dynamic:
        trace["policy_steps"] = diag.policy_steps
    if react and chosen_route == "fastpath":
        trace["react"] = react_trace
    terminal = verify_terminal(terminal, diag)
    trace["claims"] = diag.claims.evaluate_all(diag.state, workflow)
    if adapter is not None:
        trace["adapter"] = {"name": adapter.name, "probe_failures": probe_failures}
    if return_state:  # live CaseState for session continuity; not JSON-serialisable
        result["case_state"] = diag.state
    concluded = finish({**result, "target": target, "graph": trace},
                       terminal or verdict("INCOMPLETE", "insufficient_evidence"), diag.claims)
    # Contract C reports the Case decision the claims reached, not only the goal gap:
    # a proven FAULT claim answers the question before every goal is measured.
    contract_c = trace["contract_c"]
    contract_c["decision"] = concluded["case_status"]
    if diag.claims.lookup(concluded["terminal"]["diagnosis"], workflow) is not None:
        contract_c["concluded_claim"] = concluded["terminal"]["diagnosis"]
    return concluded


def replay_from_fixture(fixture, registry):
    """Convert the old single-device replay fixture to a trusted adapter inventory."""
    world = fixture["world"]
    gateway = {fid: data for fid, data in world.items()
               if registry.functions[fid].scope == "gateway"}
    devices = []
    selector = fixture["target"].get("selector")
    if selector:
        aliases = {"my-phone": ["điện thoại của tôi", "my phone"],
                   "laptop-an": ["laptop của tôi", "my laptop"]}.get(selector, [])
        device_world = {fid: data for fid, data in world.items()
                        if registry.functions[fid].scope == "client"}
        devices.append({"selector": selector, "aliases": aliases, "world": device_world,
                        "client_id": device_world.get("clients.resolve", {}).get("client_id")})
    return {"world": gateway, "devices": devices, "capabilities": fixture["capabilities"],
            "initial_evidence": fixture.get("initial_evidence", [])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--fixture", required=True, help="Selects the simulated adapter environment")
    parser.add_argument("--method", choices=("gos", "bm25"), default="gos")
    parser.add_argument("--route", choices=("fastpath", "resolver", "auto"), default="auto")
    parser.add_argument("--model", help="Optional local Ollama advisor with fewer than 3B parameters")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--guide", action="store_true", help="Attach local runbooks for this replay profile")
    parser.add_argument("--context-bytes", type=int, help="Include compiler-checked skill bundles in the trace")
    parser.add_argument("--trace", action="store_true", help="Print the structured decision and graph")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dynamic", dest="dynamic", action="store_true", help="Use the evidence-driven policy (default)")
    mode.add_argument("--core", dest="dynamic", action="store_false", help="Use the original Core workflow for comparison")
    mode.add_argument("--react", action="store_true", help="Use the LangGraph ReAct template with SkillDAG validation")
    parser.set_defaults(dynamic=True)
    args = parser.parse_args()
    fixture = next((c for c in read_json(ROOT / "data/cases.json") if c["id"] == args.fixture), None)
    if fixture is None:
        parser.error("Unknown replay fixture")
    if args.context_bytes is not None and not 2 <= args.context_bytes <= 32_000:
        parser.error("--context-bytes must be in [2, 32000]")
    registry = workflow_registry()
    advisor = None
    if args.model:
        try:
            advisor = OllamaProbeAdvisor(args.model, args.endpoint)
        except OSError as exc:
            print(f"Ollama unavailable, using Core probe order ({type(exc).__name__})", file=sys.stderr)
        except ValueError as exc:
            parser.error(str(exc))
    result = diagnose(args.request, replay_from_fixture(fixture, registry),
                      registry=registry, method=args.method, advisor=advisor, context_bytes=args.context_bytes,
                      dynamic=args.dynamic, react=args.react, route=args.route)
    if args.guide:
        guide = RunbookIndex(DEFAULT_CATALOG).retrieve(args.request, product=REPLAY_PRODUCT,
                                                      firmware=REPLAY_FIRMWARE, permissions={"docs.read"})
        result["explanation"] = explain(guide, result)
    sys.stdout.reconfigure(encoding="utf-8")
    response = result["explanation"]["response"] if args.guide else result["terminal"]["response"]
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.trace else response)


if __name__ == "__main__":
    main()
