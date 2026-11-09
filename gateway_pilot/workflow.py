"""Text-first, evidence-driven diagnostic workflow for the read-only replay pilot."""

import argparse
import json
import re
import sys
import unicodedata

from .core import ROOT, PlanError, Registry, read_json, support
from .graph_v3.graphs import GraphRegistry
from .graph_v3.context import retrieve_context
from .graph_v3.dynamic_policy import run_client_probes
from .graph_v3.orchestrator import run_plan
from .graph_v3.runner import GraphRunner
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
ROUTER_FAULTS = {"wan_link_down", "wan_no_route", "wan_packet_loss", "gateway_dns_failure"}
PARTIAL_OBSERVATIONS = {"client_path_unverified", "client_ip_reachable", "client_path_loss",
                        "client_no_lease"}


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


def finish(result, terminal):
    action, diagnosis = terminal["action"], terminal["diagnosis"]
    if action == "ASK_USER":
        status = "NEEDS_INPUT"
    elif diagnosis in {"unsafe_change_denied", "read_permission_denied"}:
        status = "BLOCKED"
    elif diagnosis in PARTIAL_OBSERVATIONS or (result["workflow"] == "WF-INTERNET" and diagnosis in ROUTER_FAULTS):
        status = "PARTIAL"
    else:
        status = "RESOLVED" if action == "FINISH" else "INCONCLUSIVE"
    return {**result, "terminal": terminal, "case_status": status}


class Diagnostic:
    def __init__(self, case, registry, method, max_calls, advisor):
        self.case = case
        self.state = CaseState(case, registry)
        self.runner = GraphRunner(registry, case, self.state, max_calls=max_calls)
        self.method = method
        self.advisor = advisor
        self.advice = []
        self.stages = []
        self.retrievals = []
        self.policy_steps = []

    def observe(self, port, reason, *, plan=None):
        stage = {"goal": port, "reason": reason, "after_call": self.runner.calls}
        self.stages.append(stage)
        fact = self.state.fact(port)
        if fact is None:
            try:
                if plan is None:
                    revision = self.runner.plans[-1].revision + 1 if self.runner.plans else 1
                    plan = self.runner.compiler().compile([port], self.state, revision=revision)
                self.retrievals.extend(run_plan(self.runner, plan, [port], method=self.method))
            except PlanError as exc:
                stage["error"] = str(exc)
            fact = self.state.fact(port)
        stage["evidence_id"] = fact["id"] if fact else None
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

    def proof(self, *diagnoses):
        for diagnosis in diagnoses:
            supported, ids = support(diagnosis, self.state, self.case)
            if supported and ids:
                return verdict("FINISH", diagnosis, ids)
        return None

    def observed(self, action, diagnosis, *ports):
        facts = [self.state.fact(port) for port in ports]
        if all(facts):
            return verdict(action, diagnosis, [fact["id"] for fact in facts])
        return None

    def unresolved_client(self):
        if any(e["port"] == "client.identity" and e["status"] == "AMBIGUOUS"
               for e in self.state.evidence):
            return verdict("ASK_USER", "target_ambiguous")
        return verdict("INCOMPLETE", "insufficient_evidence")

    def trace(self):
        return {"stages": self.stages, "advice": self.advice, "plans": [p.export() for p in self.runner.plans],
                "events": self.runner.events, "retrievals": self.retrievals,
                "calls": self.runner.calls, "repairs": self.runner.repairs,
                "errors": self.state.errors, "executed": self.state.executed,
                "evidence": self.state.public()["evidence"]}


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


def internet_workflow(diag, *, dynamic=False):
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
    if dynamic:
        return run_client_probes(diag)
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
             context_bytes=None, dynamic=False):
    """Run from request text and trusted replay inventory, with no fixture verdict as input."""
    text = normalize(request)
    workflow = route(text)
    result = {"request": request, "workflow": workflow, "workflow_id": HTML_WORKFLOW_IDS.get(workflow),
              "target": None,
              "execution": "synthetic_replay", "decision_source": "core_rules"}
    if workflow is None:
        return finish(result, verdict("ASK_USER", "intent_unclear"))
    if workflow == "WF-WRITE":
        return finish(result, verdict("INCOMPLETE", "unsafe_change_denied"))
    permission = "system.read" if workflow == "WF-039" else "network.read"
    if "permissions" in replay and permission not in replay["permissions"]:
        return finish(result, verdict("INCOMPLETE", "read_permission_denied"))

    registry = registry or workflow_registry()
    target = {"scope": "gateway", "id": "gateway_01"}
    world = dict(replay["world"])
    if workflow in ("WF-024", "WF-INTERNET"):
        device = match_device(text, replay.get("devices", []))
        if device is None:
            return finish(result, verdict("ASK_USER", "target_ambiguous"))
        target = {"scope": "client", "selector": device["selector"]}
        if device.get("client_id"):
            target["client_id"] = device["client_id"]
        world.update(device["world"])
    # Only the replay executor consumes observations. Planner sees verified facts.
    initial = [e for e in replay.get("initial_evidence", []) if e["scope"] == "gateway"
               or (target.get("client_id") and e["target"] == target["client_id"])]
    case = {"request": request, "workflow": workflow, "target": target, "world": world,
            "capabilities": replay["capabilities"], "initial_evidence": initial}
    if "permissions" in replay:
        case["permissions"] = replay["permissions"]
    diag = Diagnostic(case, registry, method, max_calls, advisor)
    if context_bytes is not None:
        result["skill_context"] = retrieve_context(registry, diag.state, request,
                                                   registry.goal_ports[workflow], max_bytes=context_bytes, method=method)
    if dynamic and workflow == "WF-INTERNET":
        terminal = internet_workflow(diag, dynamic=True)
        result["decision_source"] = "dynamic_client_policy"
    else:
        terminal = WORKFLOWS[workflow](diag)
    trace = diag.trace()
    if result["decision_source"] == "dynamic_client_policy":
        trace["policy_steps"] = diag.policy_steps
    return finish({**result, "target": target, "graph": trace},
                  terminal or verdict("INCOMPLETE", "insufficient_evidence"))


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
    parser.add_argument("--model", help="Optional local Ollama advisor with fewer than 3B parameters")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--guide", action="store_true", help="Attach local runbooks for this replay profile")
    parser.add_argument("--context-bytes", type=int, help="Include compiler-checked skill bundles in the trace")
    parser.add_argument("--trace", action="store_true", help="Print the structured decision and graph")
    parser.add_argument("--dynamic", action="store_true", help="Use evidence-driven client probe selection")
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
                      dynamic=args.dynamic)
    if args.guide:
        guide = RunbookIndex(DEFAULT_CATALOG).retrieve(args.request, product=REPLAY_PRODUCT,
                                                      firmware=REPLAY_FIRMWARE, permissions={"docs.read"})
        result["explanation"] = explain(guide, result)
    sys.stdout.reconfigure(encoding="utf-8")
    response = result["explanation"]["response"] if args.guide else result["terminal"]["response"]
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.trace else response)


if __name__ == "__main__":
    main()
