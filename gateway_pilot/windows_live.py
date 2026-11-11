"""Read-only measurements from the Windows client using its current IPv4 route."""

import os
import re
import subprocess
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path
from statistics import mean

from .core import ROOT, PlanError, Registry, read_json
from .graph_v3.dynamic_policy import DiagnosticPolicy, Stage
from .graph_v3.graphs import GraphRegistry
from .live_intent import combined_intent, understand_live
from .windows_icmp import sample_echo
from .workflow import Diagnostic, finish, verdict


SOURCE = "windows_live/v1"
CLIENT = "local-windows"
PROBE_IP = "1.1.1.1"
DOMAIN = "example.com"
SYSTEM32 = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
PING_FIELDS = {"address": "str", "replies": "bool", "sent": "number", "received": "number",
               "loss_pct": "number", "rtt_ms": "list"}
TOOLS = {
    "live.route": ({"gateway": "str", "source_ipv4": "str"}, "SK04", "Read the Windows IPv4 default route"),
    "live.gateway": (PING_FIELDS, "SK04", "Sample ICMP latency and loss to the current gateway"),
    "live.internet": (PING_FIELDS, "SK04", "Sample ICMP latency and loss to one Internet IPv4 address"),
    "live.dns": ({"query": "str", "resolved": "bool"}, "SK05", "Query an IPv4 record using Windows DNS"),
}


def _run(program, *args, timeout=5):
    if os.name != "nt":
        raise PlanError("windows_live_requires_windows")
    return subprocess.run([str(SYSTEM32 / program), *args], capture_output=True, timeout=timeout,
                          creationflags=subprocess.CREATE_NO_WINDOW)


def default_route():
    result = _run("route.exe", "print", "-4", "0.0.0.0")
    if result.returncode:
        raise PlanError("windows_route_unavailable")
    routes = []
    for gateway, source, metric in re.findall(
        rb"^[ \t]*0\.0\.0\.0[ \t]+0\.0\.0\.0[ \t]+(\S+)[ \t]+([\d.]+)[ \t]+(\d+)[ \t\r]*$",
        result.stdout, re.MULTILINE,
    ):
        routes.append((int(metric), gateway, source))
    if not routes:
        return {"gateway": "", "source_ipv4": ""}
    best = min(metric for metric, _, _ in routes)
    choices = {(gateway, source) for metric, gateway, source in routes if metric == best}
    if len(choices) != 1:
        raise PlanError("ambiguous_windows_default_route")
    gateway, source = choices.pop()
    try:
        return {"gateway": str(IPv4Address(gateway.decode())), "source_ipv4": str(IPv4Address(source.decode()))}
    except ValueError as exc:
        raise PlanError("windows_default_route_has_no_next_hop") from exc


def _dns():
    script = ("$ErrorActionPreference='Stop'; try { "
              f"$records=Resolve-DnsName -Name '{DOMAIN}.' -Type A -DnsOnly -NoHostsFile -QuickTimeout; "
              "if ($records | Where-Object Type -eq 'A') { exit 0 }; exit 1 } catch { exit 2 }")
    result = _run(r"WindowsPowerShell\v1.0\powershell.exe", "-NoProfile", "-NonInteractive",
                  "-Command", script, timeout=8)
    if result.returncode not in (0, 1, 2):
        raise PlanError("windows_dns_unavailable")
    return {"query": DOMAIN, "resolved": result.returncode == 0}


def read_observation(function, state):
    try:
        if function == "clients.resolve":
            data = {"client_id": CLIENT}
        elif function == "live.route":
            data = default_route()
        elif function in {"live.gateway", "live.internet", "live.dns"}:
            route_fact = state.fact("live.route")
            expected = route_fact["value"]
            if default_route() != expected:
                state.invalidate([route_fact["id"]])
                return {"_status": "ROUTE_CHANGED"}, SOURCE, datetime.now(UTC).isoformat()
            if function == "live.dns":
                data = _dns()
            else:
                destination = expected["gateway"] if function == "live.gateway" else PROBE_IP
                data = sample_echo(destination, expected["source_ipv4"])
            if default_route() != expected:
                state.invalidate([route_fact["id"]])
                data = {"_status": "ROUTE_CHANGED"}
        else:
            raise PlanError("windows_live_function_not_allowed")
    except subprocess.TimeoutExpired:
        data = {"_status": "TIMEOUT"}
    except (OSError, ValueError):
        data = {"_status": "UNAVAILABLE"}
    return data, SOURCE, datetime.now(UTC).isoformat()


def _registry():
    data = read_json(ROOT / "data/registry.json")
    for name, (fields, skill, description) in TOOLS.items():
        data["port_fields"][name] = fields
        requires = [] if name == "live.route" else ["live.route"]
        data["functions"].append({"id": name, "scope": "client", "skills": [skill], "risk": "READ",
                                  "requires": requires, "produces": [name], "description": description,
                                  "ttl_s": 90, "adapter": SOURCE, "version": "1.0.0"})
    registry = GraphRegistry(Registry(data=data), provenance="windows_live/")
    for name in TOOLS:
        registry.functions[name].timeout_ms = 19_000
    return registry


class WindowsPolicy(DiagnosticPolicy):
    def __init__(self, diag, intent):
        super().__init__(diag)
        self.intent = intent

    def decide(self):
        route_fact = self.diag.state.fact("live.route")
        if not route_fact:
            return (self.choices(Stage("read_current_windows_gateway", ("live.route",)))
                    or verdict("INCOMPLETE", "insufficient_evidence"))
        if not route_fact["value"]["gateway"]:
            return _terminal(self.diag, self.intent)
        stages = (Stage(TOOLS[name][2], (name,)) for name in self.intent.checks)
        return self.choices(*stages) or _terminal(self.diag, self.intent)


def diagnose_windows(request, *, method="gos", advisor=None, react=False):
    keys, intake = understand_live(request, advisor)
    write = keys == ("write",)
    intent = combined_intent(keys) if keys and not write else None
    workflow = intent.workflow if intent else "WF-WRITE" if write else None
    result = {"request": request, "workflow": workflow, "target": None, "intake": intake,
              "workflow_id": workflow if workflow and workflow.startswith("WF-") else None,
              "execution": "windows_live", "decision_source": "windows_live_policy"}
    if write:
        return finish(result, verdict("INCOMPLETE", "unsafe_change_denied"))
    if intent is None:
        return finish(result, {"action": "ASK_USER", "diagnosis": "intent_unclear", "evidence_ids": [],
                               "response": "Bạn muốn đo độ trễ và mất gói, kiểm tra DNS, hay xem gateway máy này đang dùng?"})
    if not intent.checks:
        return finish(result, {"action": "INCOMPLETE", "diagnosis": "live_capability_missing",
                               "response": intent.limitation, "evidence_ids": []})

    registry = _registry()
    target = {"scope": "client", "selector": "Máy Windows này", "client_id": CLIENT}
    case = {"request": request, "target": target, "workflow": result["workflow"], "permissions": ["network.read"],
            "capabilities": ["clients.resolve", *TOOLS], "live_reader": read_observation,
            "boot_id": "windows-live-session", "config_version": "windows-live-route-verified"}
    diag = Diagnostic(case, registry, method, 8, advisor)
    policy = WindowsPolicy(diag, intent)
    if react:
        from .graph_v3.react_runtime import run_react
        terminal, react_trace = run_react(diag, policy=policy)
    else:
        terminal = policy.run()
    trace = {**diag.trace(), "policy_steps": diag.policy_steps}
    if react:
        trace["react"] = react_trace
    terminal = terminal or verdict("INCOMPLETE", "insufficient_evidence")
    completed = finish({**result, "target": target, "graph": trace}, terminal)
    if terminal["action"] == "INCOMPLETE" and terminal["evidence_ids"]:
        completed["case_status"] = "PARTIAL"
    return completed


def _terminal(diag, intent):
    route_fact = diag.state.fact("live.route")
    if route_fact is None:
        return verdict("INCOMPLETE", "insufficient_evidence")
    gateway = route_fact["value"]["gateway"]
    ids = [route_fact["id"]]
    if not gateway:
        response = "Windows hiện không có tuyến mặc định IPv4."
        return {"action": "FINISH", "diagnosis": "windows_no_default_ipv4_route",
                "response": response, "evidence_ids": ids}
    lines = [intent.limitation] if intent.limitation else []
    probes = [diag.state.fact(check) for check in ("live.gateway", "live.internet")]
    dns = diag.state.fact("live.dns")
    if len(intent.checks) > 1 and all(probes) and dns:
        if all(fact["value"]["loss_pct"] == 0 for fact in probes) and dns["value"]["resolved"]:
            lines.append("Trong mẫu vừa đo, cả hai đích đều phản hồi đủ và truy vấn DNS thành công.")
        else:
            lines.append("Trong mẫu vừa đo, có đích phản hồi thiếu hoặc truy vấn DNS chưa thành công.")
    lines.append(f"Gateway IPv4 mặc định của máy Windows là {gateway}.")
    complete = not intent.limitation
    for check in intent.checks:
        fact = diag.state.fact(check)
        if not fact:
            complete = False
            lines.append({"live.gateway": "Chưa có kết quả ping gateway.",
                          "live.internet": "Chưa có kết quả ping IP Internet.",
                          "live.dns": "Chưa có kết quả truy vấn DNS."}[check])
            continue
        value = fact["value"]
        ids.append(fact["id"])
        if check == "live.dns":
            outcome = "nhận được bản ghi IPv4" if value["resolved"] else "chưa nhận được bản ghi IPv4"
            lines.append(f"Truy vấn DNS {value['query']} từ Windows {outcome}.")
        else:
            samples = value["rtt_ms"]
            label = "Gateway" if check == "live.gateway" else "Đích Internet"
            line = (f"{label} {value['address']}: {value['received']}/{value['sent']} phản hồi, "
                    f"mất gói ICMP {value['loss_pct']:g}%")
            if samples:
                line += f", độ trễ trung bình {mean(samples):g} ms ({min(samples)}–{max(samples)} ms)"
            else:
                line += ", chưa đo được độ trễ"
            lines.append(line + ".")
    if len(intent.checks) > 1:
        lines.append("Đây là mẫu ngắn từ máy Windows tới hai đích để đánh giá độ trễ và mất gói tại lúc đo.")
    return {"action": "FINISH" if complete else "INCOMPLETE", "diagnosis": "windows_live_measurements",
            "response": "\n".join(lines), "evidence_ids": ids}
