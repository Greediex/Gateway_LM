"""Build benchmarks/function_selection_v1.json and its SHA-256 manifest (T9).

Cases are new: new requests and conditions over five healthy replay
environments (the adapter worlds of GLM-04/07/12/18/21-0). Labels are not
taken from any locked case. For each case the required Function set is the
minimum-cost admissible plan (with prerequisite producers) for the goals that
are measurable in that environment, computed by the contract compiler; the
expected status is what an oracle run of exactly that set yields, or BLOCKED
for a write request. Requirement ids F001-F270 are never used as labels.

Run from the pilot directory:  python benchmarks/build_function_selection_v1.py
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gateway_pilot.core import PlanError, read_json  # noqa: E402
from gateway_pilot.graph_v3.graphs import GraphRegistry  # noqa: E402
from gateway_pilot.graph_v3.planner import Compiler  # noqa: E402
from gateway_pilot.graph_v3.runner import GraphRunner  # noqa: E402
from gateway_pilot.graph_v3.state import CaseState  # noqa: E402
from gateway_pilot.workflow import match_device, normalize, replay_from_fixture  # noqa: E402

OUT = ROOT / "benchmarks/function_selection_v1.json"
MANIFEST = ROOT / "benchmarks/function_selection_v1.manifest.json"
BASE = {"WF-018": "GLM-04-0", "WF-023": "GLM-07-0", "WF-024": "GLM-12-0", "WF-039": "GLM-18-0",
        "WF-INTERNET": "GLM-21-0"}
MISSING_CAPABILITY = {"WF-018": "wan.probe", "WF-023": "dns.probe", "WF-024": "dhcp.service",
                      "WF-039": "system.resources", "WF-INTERNET": "dns.probe"}
# (dev phrasing, holdout phrasing) per workflow and condition.
REQUESTS = {
    "WF-018": {
        "normal": ("đường internet nhà mình có ổn không, kiểm tra giúp phía nhà mạng", "check whether the WAN uplink is healthy"),
        "missing_identity": ("máy tính nhà tôi vào mạng chập chờn, xem đường truyền", "my computer keeps losing the connection, check the line"),
        "missing_capability": ("kiểm tra kết nối ra ngoài của router", "is the router reaching the internet"),
        "stale_evidence": ("xem lại đường WAN lần nữa", "re-check the WAN link status"),
        "wrong_target": ("kiểm tra WAN của modem", "verify the gateway uplink"),
        "write_request": ("đổi cấu hình WAN sang PPPoE", "set the WAN mode to static IP"),
    },
    "WF-023": {
        "normal": ("router có phân giải tên miền được không", "can the gateway resolve domain names"),
        "missing_identity": ("điện thoại vào web bằng tên không được, kiểm tra DNS router", "phone can't open sites by name, check router DNS"),
        "missing_capability": ("kiểm tra máy chủ DNS của router", "test the router resolver"),
        "stale_evidence": ("kiểm tra lại DNS router", "recheck gateway DNS"),
        "wrong_target": ("DNS trên gateway có lỗi không", "is DNS failing on the gateway"),
        "write_request": ("đặt DNS router thành 1.1.1.1", "change the router DNS to 9.9.9.9"),
    },
    "WF-024": {
        "normal": ("laptop-an có nhận được địa chỉ IP từ DHCP không", "does laptop-an get a DHCP lease"),
        "missing_identity": ("máy mới cắm vào không nhận IP", "a device cannot obtain an address"),
        "missing_capability": ("kiểm tra cấp phát địa chỉ cho laptop-an", "check address allocation for laptop-an"),
        "stale_evidence": ("xem lại lease DHCP của laptop-an", "recheck laptop-an DHCP lease"),
        "wrong_target": ("ipad-be không lấy được IP", "tablet-kid cannot get an IP"),
        "write_request": ("đổi dải DHCP sang 192.168.10.0", "update the DHCP pool range"),
    },
    "WF-039": {
        "normal": ("router có quá tải CPU RAM không", "is the gateway short on memory or CPU"),
        "missing_identity": ("máy tính chậm, kiểm tra tài nguyên router", "laptop slow, check router resources"),
        "missing_capability": ("đo tài nguyên hệ thống của router", "measure router system resources"),
        "stale_evidence": ("kiểm tra lại RAM router", "recheck router memory"),
        "wrong_target": ("tài nguyên gateway hiện thế nào", "gateway resource usage now"),
        "write_request": ("cài đặt lại cấu hình router", "apply the factory profile to the router"),
    },
    "WF-INTERNET": {
        "normal": ("laptop-an có wifi mà không vào được internet", "laptop-an is on wifi but has no internet"),
        "missing_identity": ("máy tôi có wifi mà không vào mạng", "my device has wifi but no internet"),
        "missing_capability": ("laptop-an bắt wifi nhưng web không tải", "laptop-an connected but pages do not load"),
        "stale_evidence": ("kiểm tra lại vì sao laptop-an không vào mạng", "recheck why laptop-an has no internet"),
        "wrong_target": ("ipad-be có wifi mà không vào mạng", "tablet-kid has wifi but no internet"),
        "write_request": ("đổi kênh wifi cho laptop-an", "change the wifi channel for laptop-an"),
    },
}


def environment(case, registry, fixtures):
    """Replay environment for a case: base adapter world plus the case's mutation."""
    replay = replay_from_fixture(fixtures[case["base_fixture"]], registry)
    goals = registry.goal_ports[case["workflow"]]
    client_workflow = registry.workflows[case["workflow"]]["target_scope"] == "client"
    condition = case["condition"]
    if condition == "missing_capability":
        replay["capabilities"] = [c for c in replay["capabilities"] if c != MISSING_CAPABILITY[case["workflow"]]]
    if condition == "missing_identity" and client_workflow:
        other = copy.deepcopy(replay["devices"][0])
        other.update(selector="my-phone", aliases=[], client_id="client_phone")
        replay["devices"].append(other)
    if condition in ("stale_evidence", "wrong_target") and not client_workflow:
        first = next(g for g in goals if registry.ports[g].scope == "gateway")
        producer = next(f for f in registry.hf.producers(registry.ports[first]) if f in replay["world"])
        value = {k: v for k, v in replay["world"][producer].items() if not k.startswith("_")}
        observation = {"id": "pre-1", "function_id": producer, "port": first, "scope": "gateway",
                       "target": "gateway_99" if condition == "wrong_target" else "gateway_01",
                       "source": "synthetic_replay/v1", "observed_at": "2026-11-06T23:00:00Z",
                       "age_s": 100 if condition == "stale_evidence" else 0, "ttl_s": 30, "status": "OK",
                       "value": value}
        replay["initial_evidence"] = [observation]
    if condition == "stale_evidence" and client_workflow:
        device = replay["devices"][0]
        value = dict(device["world"]["clients.resolve"])
        replay["initial_evidence"] = [{"id": "pre-1", "function_id": "clients.resolve", "port": "client.identity",
                                       "scope": "client", "target": device["client_id"],
                                       "source": "synthetic_replay/v1", "observed_at": "2026-11-06T23:00:00Z",
                                       "age_s": 100, "ttl_s": 30, "status": "OK", "value": value}]
    return replay


def case_state(case, registry, replay):
    """CaseState and runner case for the device the request names (trusted inventory only)."""
    device = match_device(normalize(case["request"]), replay.get("devices", []))
    target, world = {"scope": "gateway", "id": "gateway_01"}, dict(replay["world"])
    if device is not None:
        target = {"scope": "client", "selector": device["selector"], "client_id": device["client_id"]}
        world.update(device["world"])
    initial = [e for e in replay.get("initial_evidence", []) if e["scope"] == "gateway"
               or (target.get("client_id") and e["target"] == target["client_id"])]
    run_case = {"request": case["request"], "workflow": case["workflow"], "target": target, "world": world,
                "capabilities": replay["capabilities"], "initial_evidence": initial}
    return CaseState(run_case, registry, lambda: 0.0), run_case


def label(case, registry, fixtures):
    goals = registry.goal_ports[case["workflow"]]
    if case["condition"] == "write_request":
        return [], "BLOCKED"
    replay = environment(case, registry, fixtures)
    state, run_case = case_state(case, registry, replay)
    eligible = registry.eligible(state)
    measurable = []
    for goal in goals:
        port = registry.ports[goal]
        if port.scope == "client" and not state.target.get("client_id"):
            continue
        try:
            Compiler(registry).compile([goal], state)
            measurable.append(goal)
        except PlanError:
            continue
    required = []
    if measurable:
        plan = Compiler(registry).compile(measurable, state)
        required = sorted(n.function_id for n in plan.nodes.values())
        GraphRunner(registry, run_case, state).run(plan)
    del eligible
    return required, state.case_status(goals, exhausted=True)


def build():
    registry = GraphRegistry.from_v01()
    fixtures = {c["id"]: c for c in read_json(ROOT / "data/cases.json")}
    cases = []
    for workflow, conditions in REQUESTS.items():
        for condition, phrasings in conditions.items():
            for split, request in zip(("dev", "holdout"), phrasings):
                case = {"id": f"FS-{workflow}-{condition}-{split}", "split": split, "workflow": workflow,
                        "condition": condition, "request": request, "base_fixture": BASE[workflow]}
                case["required_functions"], case["expected_status"] = label(case, registry, fixtures)
                cases.append(case)
    data = {"version": "1.0.0", "note": ("Synthetic replay environments; labels from the contract compiler. "
                                         "Holdout runs once; nothing is tuned on it."), "cases": cases}
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="")
    MANIFEST.write_text(json.dumps({"file": OUT.name, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                    "cases": len(cases), "splits": {"dev": sum(c["split"] == "dev" for c in cases),
                                                                    "holdout": sum(c["split"] == "holdout" for c in cases)}},
                                   indent=1) + "\n", encoding="utf-8", newline="")
    return data


if __name__ == "__main__":
    data = build()
    for case in data["cases"]:
        if case["split"] == "dev":
            print(f"{case['id']:42} {case['expected_status']:13} {case['required_functions']}")
