"""Trusted Linux laptop application: Core → verified snapshot → feature rules."""
from __future__ import annotations

import functools
import re
import threading
from uuid import uuid4

from ..core import ROOT, PlanError
from ..adapters.bindings import BindingSelection, TargetContext, binding_digest, declare_binding
from ..adapters.linux_wifi import LinuxWifiBackend
from ..command_catalog.builder import build_registry
from ..command_catalog.loader import digest, load_catalog, read_json
from ..command_catalog.runtime import ReadRuntime
from ..features.registry import FeatureRegistry, read_feature_flags, read_feature_manifests
from ..features.laptop_network import diagnose_snapshot
from ..observability.snapshot import VerifiedSnapshot
from .feature_availability import AvailabilityService

_LOCK = threading.Lock()


@functools.lru_cache(maxsize=1)
def laptop_catalog():
    policy = read_json(ROOT/"config/catalog_policy.laptop_network.json")
    artifact = build_registry(load_catalog(ROOT/"examples/catalog_laptop_network"),
        read_json(ROOT/"config/catalog_selection.laptop_network.json"), policy,
        ROOT/"runs/laptop-network/registry.json")
    approval = read_json(ROOT/"config/laptop_network_approval.json")["registry_digest"]
    if artifact["content_digest"] != approval:
        raise PlanError("laptop_catalog_not_approved")
    return artifact, policy, approval


def create_runtime(backend):
    artifact, policy, approval = laptop_catalog()
    context = TargetContext("client", backend.client_id, backend.environment_id)
    # Reviewed local composition root: fixed provider/source and one local laptop.
    # Remote data never chooses backend, binding IDs, target or approval pins.
    rows = [declare_binding(artifact, f["function_id"], "local."+f["function_id"], "linux.laptop", backend, context)
            for f in artifact["functions"]]
    selection = BindingSelection(artifact, policy, rows, approved_digests=frozenset(binding_digest(b) for b in rows),
                                  backends={"linux.laptop": backend}, context=context)
    runtime = ReadRuntime(artifact, policy, approved_digest=approval, selection=selection, context=context,
                          permissions=frozenset({"network.read"}),
                          policy_context_id=digest({"principal": "local-laptop-operator", "acl_revision": 1}))
    features = FeatureRegistry(artifact, policy, read_feature_manifests(ROOT/"examples/features.laptop_network.json"),
                               read_feature_flags(ROOT/"config/feature_flags.laptop_network.json"))
    return runtime, features


def diagnose_network(*, backend=None, goals=None):
    """Python operator API only; HTTP uses no arguments. Measurements serialized."""
    with _LOCK:
        backend = LinuxWifiBackend() if backend is None else backend
        runtime, features = create_runtime(backend)
        capabilities = runtime.probe()
        availability_service = AvailabilityService(features)
        availability = {f["feature_id"]: availability_service.evaluate(f["feature_id"], context=runtime.context,
                         permissions=runtime.permissions, policy_context_id=runtime.policy_context_id,
                         capabilities=capabilities) for f in features.describe()}
        selected = {f.function_id for f in capabilities.functions if f.status == "AVAILABLE"}
        requested = set(goals) if goals is not None else set(runtime.registry.ports)
        enabled_ports = {pid for f in features.describe() if features.enabled(f["feature_id"])
                         for pid in {**f["required_ports"], **f["optional_ports"]}}
        requested &= enabled_ports | {"client.identity"} if enabled_ports else set()
        executable_goals = [pid for pid in sorted(requested)
                            if any(f.id in selected and pid in f.outputs for f in runtime.registry.functions.values())]
        if not executable_goals:
            case, state = runtime.new_case()
            runner, plan = None, None
        else:
            runner, plan = runtime.execute(executable_goals)
            state = runner.state
        contract_pins = {fid:f.digest() for fid,f in runtime.registry.functions.items()}
        def valid_context():
            return (backend.environment_id == runtime.context.environment_id
                    and {fid:f.digest() for fid,f in runtime.registry.functions.items()} == contract_pins)
        snapshot = VerifiedSnapshot.from_state(state, sorted(requested), context_valid=valid_context)
        view = snapshot.export()
        diagnoses = diagnose_snapshot(view, availability)
        if not view["context_valid"]:
            for f in diagnoses:
                f.update(availability="UNAVAILABLE", status="INCOMPLETE", code="ENVIRONMENT_CHANGED",
                         summary="Route, resolver hoặc Wi-Fi thay đổi trong lúc đo; cần đo lại.", evidence_ids=[])
        facts = view["facts"]
        route = facts.get("laptop.route", {}).get("value", {})
        wifi = facts.get("laptop.wifi", {}).get("value", {})
        timeline = []
        for i, call in enumerate(state.executed):
            fid = call["function_id"]
            row = next((r for r in facts.values() if r["function_id"] == fid), None)
            node = next((n for n in plan.nodes.values() if n.function_id == fid), None) if plan else None
            timeline.append({"index":i+1, "function_id":fid, "arguments":call["arguments"],
                             "evidence_id":row["evidence_id"] if row else None,
                             "value":row["value"] if row else None, "status":"OK" if row else "UNVERIFIED",
                             "node_state":node.state if node else "UNKNOWN", "reason":node.reason if node else ""})
        return {"mode":"linux_live", "generated_at":view["generated_at"], "expires_in_s":view["expires_in_s"],
                "expires_at":view["expires_at"], "snapshot":view, "features":diagnoses, "route_interface":route.get("interface", ""),
                "wifi_interface":wifi.get("interface", backend.interface),
                "route_uses_wifi":bool(route.get("interface") and route.get("interface") == wifi.get("interface")),
                "router_health":{"status":"UNAVAILABLE", "reason":"Chưa có backend đo CPU/RAM hoặc health từ router."},
                "calls":runner.calls if runner else 0, "timeline":timeline,
                "errors":[n.reason for n in plan.nodes.values() if n.failure] if plan else [],
                "evidence":[state.evidence_record(e) for e in state.evidence if e["port"] in facts] if runner else [],
                "plans":[plan.export()] if plan else [], "events":runner.events if runner else [],
                "contracts":{"a":[plan.export()] if plan else [], "b":runner.contract_b if runner else []}}


def chat_linux(request: str, *, method="bm25") -> dict:
    from ..live_intent import understand_live
    keys, intake = understand_live(request)
    from ..workflow import normalize
    if re.search(r"\b(?:chan (?:internet|wifi|wi fi|mang)|tat (?:wifi|wi fi|radio)|bat (?:wifi|wi fi|radio)|doi mat khau|reset|reboot|restart|block|disable|enable)\b", normalize(request)):
        keys = ("write",)
    if not keys:
        if "wifi" in normalize(request).replace("wi fi", "wifi"):
            keys = ("radio",)
    boundary = next((k for k in keys if k in {"write", "clients", "router_resources", "dhcp"}), None)
    if boundary or not keys:
        text = ("Chỉ đọc mạng của laptop này; chưa có quyền thay cấu hình, bảng client/DHCP hay CPU/RAM router."
                if boundary else "Bạn có thể hỏi Wi-Fi, gateway, Internet, DNS hoặc chất lượng mạng laptop này.")
        data = dict(features=[], calls=0, snapshot={"facts":{},"missing_ports":[]}, evidence=[],plans=[],events=[],errors=[],contracts={})
        status, action = ("BLOCKED", "DENY") if boundary == "write" else ("NEEDS_INPUT", "ASK_USER")
    else:
        # Rule-selected, bounded READ goals; no model/HTTP supplied tool/targets.
        if keys == ("gateway",):
            goals = ("laptop.route","laptop.gateway_probe")
        elif keys == ("dns",):
            goals = ("laptop.route","laptop.dns")
        elif keys == ("radio",):
            goals = ("laptop.wifi", "laptop.route")
        else:
            goals = None
        data = diagnose_network(goals=goals)
        relevant = [f for f in data["features"] if (f["feature_id"].endswith("wifi") if keys == ("radio",) else True)]
        facts = data["snapshot"]["facts"]
        if keys == ("gateway",):
            route = facts.get("laptop.route",{}).get("value",{})
            ping = facts.get("laptop.gateway_probe",{}).get("value",{})
            text = (f"Gateway: {route.get('gateway') or 'chưa có'}. Interface: {route.get('interface') or 'chưa có'}. "
                    + (f"Phản hồi ICMP {ping['received']}/{ping['sent']}, " + (f"latency {ping['latency_ms']:g} ms." if ping["latency_ms"] >= 0 else "chưa có số đo RTT.") if ping else "Chưa có phản hồi được xác minh."))
        elif keys == ("dns",):
            dns = facts.get("laptop.dns",{}).get("value",{})
            text = (f"DNS {dns['query']}: {'phân giải được' if dns['resolved'] else 'chưa phân giải được'}, interface {dns['interface']}."
                    if dns else "Chưa có evidence DNS còn hiệu lực; cần đo lại.")
        else:
            text = "\n".join(f["summary"] for f in relevant)
        if "throughput" in keys:
            text = "Chưa đo tốc độ tải lên/tải xuống Mbps. " + text
        status, action = ("PARTIAL" if data["snapshot"]["missing_ports"] else "MEASURED"), "REPORT"
    facts = data["snapshot"]["facts"]
    evidence = [{"id":r["evidence_id"],"function_id":r["function_id"],"port":pid,"scope":r["scope"],"target":r["target"],
                 "status":"OK","source":r["source"],"value":r["value"],"observed_at":r["observed_at"]} for pid,r in facts.items()]
    return {**data, "answer":text,"request":request,"mode":"linux_live","fixture_id":"LINUX-LIVE",
            "fixture":"Đo thật từ laptop Linux","method":"core","policy":"dynamic","workflow":"LAPTOP-NETWORK",
            "target":{"scope":"client","client_id":"local-laptop","selector":"Laptop Linux này"},
            "workflow_id":None,"session_id":uuid4().hex,"case_status":status,"action":action,"diagnosis":None,
            "evidence":evidence,"evidence_ids":[r["id"] for r in evidence],"status_ok_evidence_ids":[r["id"] for r in evidence],
            "timeline":data.get("timeline",[]),"stages":[],"repairs":0,"advice":[],"runbooks":[],"warnings":[],"intake":intake,
            "llm_advisor_requested":False,"llm_advisor_ready":False,"llm_advisor_used":False,
            "notice":"Phép đo READ từ laptop Linux tại " + data.get("generated_at", "lượt này") + "; kết quả là ảnh chụp thời điểm đo, không phải monitoring liên tục. IP/DNS phản hồi không chứng minh truy cập web. Router health chưa được đo."}
