"""Gateway LM Web — stdlib local HTTP adapter around gateway_pilot.workflow.

Launch from the Gateway_LM repo root after copying web_gateway/ there:
    python -m web_gateway.server

Read-only. All diagnostic observations come from repo data/cases.json synthetic replay.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
import traceback
from collections import defaultdict, deque
from copy import deepcopy
from functools import lru_cache
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_REPO = PROJECT_DIR.parent
REPO = Path(os.environ.get("GATEWAY_LM_REPO", DEFAULT_REPO)).expanduser().resolve()
STATIC_DIR = PROJECT_DIR / "static"
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

# A compact display label for synthetic diagnostic templates; source of truth is
# the repository's data/cases.json, not these labels.
TEMPLATE_LABELS = {
    "wan_down": "WAN mất liên kết", "wan_route": "WAN thiếu default route",
    "wan_loss": "WAN mất gói", "wan_healthy": "WAN bình thường",
    "wan_timeout": "WAN probe timeout", "dns_fail": "DNS lỗi",
    "dns_healthy": "DNS bình thường", "dns_stale": "Evidence DNS hết hạn",
    "dns_wrong_target": "Evidence DNS sai thiết bị",
    "dhcp_pool": "DHCP hết IP", "dhcp_service": "DHCP service ngừng",
    "dhcp_healthy": "DHCP bình thường", "dhcp_ambiguous": "Không rõ thiết bị",
    "dhcp_wrong_client": "Evidence sai client", "sys_ram": "RAM thấp",
    "sys_cpu": "CPU cao", "sys_storage": "Bộ nhớ đầy",
    "sys_healthy": "Tài nguyên bình thường", "sys_missing": "Thiếu telemetry",
    "sys_parse": "Telemetry sai định dạng", "internet_unverified": "Internet: chưa rõ client",
    "wifi_weak": "Wi-Fi yếu", "write_denied": "Lệnh thay đổi bị chặn",
    "injection": "Log chứa nội dung độc hại",
}
WORKFLOW_LABELS = {
    "WF-018": "WAN", "WF-023": "DNS", "WF-024": "DHCP",
    "WF-039": "Hệ thống", "WF-INTERNET": "Wi-Fi / Internet", "WF-WRITE": "An toàn",
}
DEFAULT_FIXTURE = "GLM-21-1"
from gateway_pilot.adapters import ReplayAdapter  # noqa: E402  (needs REPO on sys.path)
from gateway_pilot.session import SessionStore  # noqa: E402

SESSIONS = SessionStore()  # process-wide, in memory (C4); nothing is persisted


def sessions():
    return SESSIONS


def comparison_fixtures(base):
    """Keep comparison scenarios separate from the frozen Gateway dataset."""
    if base is None or "client.probe" not in base["world"]:
        return ()
    fallback = deepcopy(base)
    fallback.update(id="WEB-WAN-TIMEOUT-1", template="web_wan_timeout")
    fallback["world"]["wan.probe"]["_status"] = "TIMEOUT"
    fallback["world"]["client.probe"]["loss_pct"] = 80
    fallback["capabilities"].append("client.probe")
    client_dns = deepcopy(base)
    client_dns.update(id="WEB-CLIENT-DNS-1", template="web_client_dns")
    client_dns["world"]["client.dns"] = {"query": "example.com", "rcode": "SERVFAIL"}
    client_dns["capabilities"].extend(("client.probe", "client.dns"))
    for case in (fallback, client_dns):
        case.pop("gold", None)
        case["initial_evidence"] = []
    return fallback, client_dns


TEMPLATE_LABELS.update(web_wan_timeout="WAN timeout · đo từ client",
                       web_client_dns="DNS lỗi từ client · router vẫn phân giải được")


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def fixture_catalog():
    path = REPO / "data" / "cases.json"
    if not path.is_file():
        raise FileNotFoundError(
            f"Không tìm thấy {path}. Hãy giải nén web_gateway vào thư mục gốc Gateway_LM "
            "hoặc đặt biến môi trường GATEWAY_LM_REPO."
        )
    cases = {case["id"]: case for case in _read_json(path)}
    cases.update((case["id"], case) for case in comparison_fixtures(cases.get(DEFAULT_FIXTURE)))
    return cases


def fixture_summaries():
    # Show one representative per scenario by default; all cases remain addressable.
    cases = fixture_catalog().values()
    return [{"id": c["id"], "template": c["template"],
             "label": TEMPLATE_LABELS.get(c["template"], c["template"].replace("_", " ")),
             "workflow": c["workflow"], "group": WORKFLOW_LABELS.get(c["workflow"], c["workflow"]),
             "request": c.get("request", ""), "target": c.get("target", {}).get("selector", "gateway"),
             "split": c.get("split", "")}
            for c in cases if c["id"].endswith("-1")]


def _status():
    status = {"connected": False, "mode": "synthetic_replay", "gos_available": False,
              "skill_context_available": False, "react_available": False,
              "llm_optional": True, "direct_router_access": False, "windows_live_available": os.name == "nt",
              "message": "Đang kiểm tra Gateway LM backend"}
    status.update(linux_live_available=platform.system() == "Linux" and bool(shutil.which("nmcli") and shutil.which("ip")),
                  live_platform="Windows" if os.name == "nt" else "Linux")
    status["live_available"] = status["windows_live_available"] or status["linux_live_available"]
    try:
        count = len(fixture_catalog())
        from gateway_pilot.workflow import workflow_registry
        workflow_registry()
        status.update(connected=True, fixture_count=count,
                      message="Đã nối với Gateway LM")
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        status["message"] = f"Chưa nạp được backend ({type(exc).__name__})."
    if status["connected"]:
        from gateway_pilot.graph_v3.upstream import kernel
        from gateway_pilot.graph_v3.skilldag import backend
        for key, load in (("gos_available", kernel), ("skill_context_available", backend)):
            try:
                load()
            except (RuntimeError, ImportError, OSError):
                continue
            status[key] = True
        if status["skill_context_available"]:
            try:
                from gateway_pilot.graph_v3.react_template.graph import build_graph
            except ImportError:
                pass
            else:
                status["react_available"] = callable(build_graph)
    return status


def analyze(payload: dict):
    """Dispatch a request to one explicit evidence source."""
    if not isinstance(payload, dict):
        raise ValueError("Body phải là JSON object")
    message = payload.get("message")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ValueError("Câu hỏi phải dài 1–2000 ký tự")
    method = payload.get("method", "bm25")
    if method not in ("bm25", "gos"):
        raise ValueError("Method chỉ hỗ trợ bm25 hoặc gos")
    source_mode = payload.get("source_mode", "replay")
    if source_mode not in ("replay", "live"):
        raise ValueError("Nguồn dữ liệu chỉ hỗ trợ live hoặc replay")
    live = source_mode == "live"
    if live and os.name != "nt" and platform.system() != "Linux":
        raise ValueError("Live yêu cầu Linux hoặc Windows")
    fixture_id = "WINDOWS-LIVE" if live else payload.get("fixture_id", DEFAULT_FIXTURE)
    if not live:
        cases = fixture_catalog()
        if not isinstance(fixture_id, str) or fixture_id not in cases:
            raise ValueError("Fixture không tồn tại trong data/cases.json")
    policy = payload.get("policy", "dynamic")
    if policy not in ("react", "dynamic", "core"):
        raise ValueError("Policy chỉ hỗ trợ react, dynamic hoặc core")
    for key in ("with_guide", "with_llm", "with_skill_context"):
        if key in payload and type(payload[key]) is not bool:
            raise ValueError(f"{key} phải là boolean")
    session_id = payload.get("session_id")
    if session_id is not None and (not isinstance(session_id, str) or not 1 <= len(session_id) <= 64):
        raise ValueError("session_id không hợp lệ")

    if live and platform.system() == "Linux" and os.name != "nt":
        forbidden = {"adapter", "backend", "world", "permissions", "capabilities", "profile", "command",
                     "interface", "target", "registry", "goals", "model_path", "approved_digest"}
        if forbidden.intersection(payload):
            raise ValueError("Không nhận cấu hình backend/target/quyền từ HTTP")
        from gateway_pilot.application.diagnose_network import chat_linux
        return chat_linux(message.strip(), method=method)

    # Important: never pass gold labels, template names or hidden world to the
    # planner/model directly. replay_from_fixture returns adapter inventory.
    from gateway_pilot.workflow import diagnose, replay_from_fixture, workflow_registry
    from gateway_pilot.rag import RunbookIndex, DEFAULT_CATALOG, REPLAY_PRODUCT, REPLAY_FIRMWARE

    warnings = []
    advisor = None
    if payload.get("with_llm") is True:
        from gateway_pilot.workflow_advisor import OllamaProbeAdvisor
        model = payload.get("model", "qwen3:1.7b")
        if not isinstance(model, str) or not 1 <= len(model) <= 80 or not all(
            c.isalnum() or c in "-._:/" for c in model
        ):
            raise ValueError("Tên model không hợp lệ")
        try:
            advisor = OllamaProbeAdvisor(model, endpoint="http://127.0.0.1:11434", timeout=25)
        except (OSError, ConnectionError, ValueError, RuntimeError, KeyError) as exc:
            warnings.append(f"Ollama advisor không khả dụng ({type(exc).__name__}); dùng thứ tự mặc định.")

    if live:
        from gateway_pilot.windows_live import diagnose_windows
        if policy == "core":
            raise ValueError("Core đối chứng dùng nguồn replay. Chọn Dynamic hoặc ReAct để đo thật.")
        result = diagnose_windows(message.strip(), method=method, advisor=advisor, react=policy == "react")
        initial_ids = set()
        fixture_label = "Đo thật từ máy Windows"
        session = sessions().get(session_id, environment="windows_live")
    else:
        fixture = cases[fixture_id]
        registry = workflow_registry()
        replay = replay_from_fixture(fixture, registry)
        replay["adapter"] = ReplayAdapter(registry, replay["capabilities"])  # T8 adapter boundary
        options = {"react": True} if policy == "react" else {}
        # One Case per session: a reply naming a device continues the pending request,
        # and fresh gateway evidence from earlier turns is reused, not measured again.
        session = sessions().get(session_id, environment=f"replay:{fixture_id}:{policy}")
        request = message.strip()
        device = session.pending_device(message, replay.get("devices", []))
        if device is not None:
            request, options["workflow"] = session.request, session.workflow
        result = diagnose(request, session.carry(replay), registry=registry, method=method,
                          max_calls=12, advisor=advisor, dynamic=policy != "core",
                          context_bytes=1800 if payload.get("with_skill_context") else None,
                          device_selector=device["selector"] if device else None, return_state=True, **options)
        session.remember(result, request=request)
        result.pop("case_state", None)
        initial_ids = {row["id"] for row in session.carry(replay).get("initial_evidence", [])}
        fixture_label = TEMPLATE_LABELS.get(fixture["template"], fixture["template"])
    graph = result.get("graph", {})
    evidence = graph.get("evidence", [])
    execution = graph.get("executed", [])
    events = graph.get("events", [])
    status_ok_ids = {e["id"] for e in evidence if e.get("status") == "OK"}
    by_function, by_node = defaultdict(deque), defaultdict(deque)
    for item in evidence:
        if item["id"] not in initial_ids and "function_id" in item:
            by_function[item["function_id"]].append(item)
    for item in events:
        if "node" in item:
            by_node[item["node"]].append(item)
    timeline = []
    for idx, item in enumerate(execution):
        fid = item["function_id"]
        e = by_function[fid].popleft() if by_function[fid] else None
        event = by_node[fid].popleft() if by_node[fid] else {}
        timeline.append({"index": idx+1, "function_id": fid, "arguments": item.get("arguments", {}),
                         "evidence_id": e["id"] if e else None,
                         "port": e.get("port") if e else None,
                         "value": e.get("value") if e else None,
                         "status": e.get("status", "UNKNOWN") if e else "UNKNOWN",
                         "node_state": event.get("state", "UNKNOWN"),
                         "revision": event.get("revision"), "reason": event.get("reason", "")})

    docs = []
    if not live and payload.get("with_guide", True) is True:
        try:
            guide = RunbookIndex(DEFAULT_CATALOG).retrieve(
                message, product=REPLAY_PRODUCT, firmware=REPLAY_FIRMWARE,
                permissions={"docs.read"}, method="closure", k=3, max_bytes=1800)
            docs = guide.get("documents", [])
        except (OSError, ValueError, KeyError) as exc:
            warnings.append(f"Không tải được runbook ({type(exc).__name__}).")

    terminal = result["terminal"]
    return {
        "request": result.get("request", message.strip()), "workflow_id": result.get("workflow_id"),
        "session_id": session.session_id, "session_turn": session.turns, "adapter": graph.get("adapter"),
        "route": "resolver" if result.get("decision_source") == "function_resolver" else "fastpath",
        "contracts": {"c0": graph.get("contract_0", []), "a": graph.get("contract_a", []),
                      "b": graph.get("contract_b", []), "c": graph.get("contract_c", {})},
        "revisions": [{"revision": p.get("revision"), "operators": [a.get("operator") for a in p.get("audit", [])]}
                      for p in graph.get("plans", [])],
        "intake": result.get("intake"),
        "answer": terminal.get("response", "Không có kết luận"),
        "diagnosis": terminal.get("diagnosis"), "action": terminal.get("action"),
        "case_status": result.get("case_status"), "workflow": result.get("workflow"),
        "target": result.get("target"), "decision_source": result.get("decision_source"),
        "mode": "windows_live" if live else "synthetic_replay", "fixture_id": fixture_id,
        "fixture": fixture_label,
        "method": method, "policy": policy, "llm_advisor_requested": payload.get("with_llm", False),
        "llm_advisor_ready": advisor is not None,
        "llm_advisor_used": bool(graph.get("advice")) or result.get("intake", {}).get("source") == "llm",
        "calls": graph.get("calls", 0), "repairs": graph.get("repairs", 0),
        "timeline": timeline, "stages": graph.get("stages", []),
        "policy_steps": graph.get("policy_steps", []), "skill_context": result.get("skill_context"),
        "react": graph.get("react"),
        "plans": graph.get("plans", []), "events": events,
        "evidence": evidence, "evidence_ids": terminal.get("evidence_ids", []),
        "status_ok_evidence_ids": sorted(status_ok_ids),
        "advice": graph.get("advice", []), "errors": graph.get("errors", []),
        "retrievals": graph.get("retrievals", []),
        "runbooks": docs, "warnings": warnings,
        "notice": ("Phép đo trực tiếp từ máy Windows đang dùng gateway mặc định."
                   if live else "Kết quả dựa trên synthetic replay đã chọn, KHÔNG phản ánh trạng thái router thật.")
    }


def analyze_goals(payload: dict):
    """Opt-in typed GoalAgent HTTP endpoint: replay fixture only, read-only.

    The request may select an existing fixture and registered output ports,
    but cannot supply adapter instances, world data, permissions or arbitrary
    Function IDs. Unsupported goals are rejected before any execution.
    """
    if not isinstance(payload, dict):
        raise ValueError("Body phải là JSON object")
    message = payload.get("message")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ValueError("Câu hỏi phải dài 1–2000 ký tự")
    if payload.get("source_mode", "replay") != "replay":
        raise ValueError("Goal endpoint hiện chỉ hỗ trợ replay")
    fixture_id = payload.get("fixture_id", DEFAULT_FIXTURE)
    cases = fixture_catalog()
    if not isinstance(fixture_id, str) or fixture_id not in cases:
        raise ValueError("Fixture không tồn tại trong data/cases.json")
    method = payload.get("method", "bm25")
    if method not in ("bm25", "gos"):
        raise ValueError("Method chỉ hỗ trợ bm25 hoặc gos")
    registry_version = payload.get("registry", "legacy")
    if registry_version not in ("legacy", "v01"):
        raise ValueError("Registry chỉ hỗ trợ legacy hoặc v01")
    goals = payload.get("goals")
    if (goals is not None and
            (not isinstance(goals, list) or not 1 <= len(goals) <= 8 or
             any(not isinstance(g, str) or not 1 <= len(g) <= 128 for g in goals))):
        raise ValueError("goals phải là danh sách 1–8 output port hợp lệ")
    if goals is None and registry_version != "v01":
        raise ValueError("Suy luận goal cần registry v01 có workflow catalog")
    max_calls = payload.get("max_calls", 12)
    if type(max_calls) is not int or not 1 <= max_calls <= 12:
        raise ValueError("max_calls phải là số nguyên từ 1 đến 12")
    from gateway_pilot.core import PlanError
    from gateway_pilot.graph_v3.goal_agent import GoalAgent
    from gateway_pilot.graph_v3.graphs import GraphRegistry

    registry = GraphRegistry.from_v01() if registry_version == "v01" else GraphRegistry()
    fixture = deepcopy(cases[fixture_id])
    fixture.pop("gold", None)  # Labels belong to offline scoring only.
    agent = GoalAgent(registry, method=method, max_calls=max_calls)
    try:
        return agent.run(message, fixture, goals=goals)
    except PlanError as exc:
        raise ValueError("Goal không được hỗ trợ hoặc không hợp lệ: " + str(exc)) from exc


def analyze_rca(payload: dict):
    """Opt-in Claim-backed RCA from trusted replay fixtures only.

    User JSON can select a workflow/fixture, not override the trusted world,
    Function registry, device permissions, Adapter or evidence.
    """
    if not isinstance(payload, dict):
        raise ValueError("Body phải là JSON object")
    message = payload.get("message")
    if not isinstance(message, str) or not 1 <= len(message.strip()) <= 2000:
        raise ValueError("Câu hỏi phải dài 1–2000 ký tự")
    if payload.get("source_mode", "replay") != "replay":
        raise ValueError("RCA endpoint hiện chỉ hỗ trợ replay")
    fixture_id = payload.get("fixture_id", DEFAULT_FIXTURE)
    cases = fixture_catalog()
    if not isinstance(fixture_id, str) or fixture_id not in cases:
        raise ValueError("Fixture không tồn tại trong data/cases.json")
    method = payload.get("method", "bm25")
    if method not in ("bm25", "gos"):
        raise ValueError("Method chỉ hỗ trợ bm25 hoặc gos")
    workflow = payload.get("workflow")
    if not isinstance(workflow, str) or not 1 <= len(workflow) <= 32:
        raise ValueError("Workflow DIAGNOSE phải được chỉ định rõ")
    max_calls = payload.get("max_calls", 10)
    if type(max_calls) is not int or not 1 <= max_calls <= 12:
        raise ValueError("max_calls phải là số nguyên từ 1 đến 12")

    from gateway_pilot.core import PlanError
    from gateway_pilot.graph_v3.rca_agent import RCAAgent
    from gateway_pilot.graph_v3.graphs import GraphRegistry

    registry = GraphRegistry.from_v01()
    fixture = deepcopy(cases[fixture_id])
    fixture.pop("gold", None)
    agent = RCAAgent(registry, method=method, max_calls=max_calls)
    try:
        result = agent.run(message.strip(), fixture, workflow=workflow)
    except PlanError as exc:
        raise ValueError("Workflow RCA không được hỗ trợ: " + str(exc)) from exc
    result["mode"] = "synthetic_replay"
    result["fixture_id"] = fixture_id
    return result


class Handler(BaseHTTPRequestHandler):
    server_version = "GatewayLMWeb/1.0"

    def log_message(self, fmt, *args):
        sys.stderr.write("[web] " + fmt % args + "\n")

    def _json(self, body, status=HTTPStatus.OK):
        data = json.dumps(body, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)

    def _local_request(self):
        port = self.server.server_port
        hosts = {f"{host}:{port}" for host in ("127.0.0.1", "localhost")}
        if port == 80:
            hosts.update(("127.0.0.1", "localhost"))
        host = self.headers.get("Host", "").lower()
        origin = self.headers.get("Origin")
        if host in hosts and (origin is None or origin == f"http://{host}"):
            return True
        self._json({"error": "Chỉ chấp nhận yêu cầu từ giao diện localhost."}, HTTPStatus.FORBIDDEN)
        return False

    def do_GET(self):
        if not self._local_request():
            return
        path = urlparse(self.path).path
        if path == "/api/health":
            status = _status()
            if getattr(self.server, "default_source", "replay") == "live":
                status["mode"] = "windows_live" if os.name == "nt" else "linux_live"
            return self._json(status)
        if path == "/api/config":
            try:
                status = _status()
                default_source = getattr(self.server, "default_source", "replay")
                if default_source == "live":
                    status["mode"] = "windows_live" if os.name == "nt" else "linux_live"
                return self._json({"status": status, "fixtures": fixture_summaries(),
                                   "default_fixture_id": DEFAULT_FIXTURE,
                                   "default_source": default_source,
                                   "default_method": "gos" if status["gos_available"] else "bm25",
                                   "react_available": status["react_available"],
                                   "default_policy": "react" if status["react_available"] else "dynamic"})
            except (OSError, ValueError):
                return self._json({"error": "Không nạp được danh sách replay.", "status": _status(), "fixtures": []},
                                  HTTPStatus.SERVICE_UNAVAILABLE)
        static_paths = {"/": "index.html", "/index.html": "index.html",
                        "/app.css": "app.css", "/app.js": "app.js"}
        filename = static_paths.get(path)
        if not filename:
            return self._json({"error": "Không tìm thấy"}, HTTPStatus.NOT_FOUND)
        file = STATIC_DIR / filename
        content_type = ("text/html" if filename.endswith("html") else
                        "text/css" if filename.endswith("css") else "text/javascript")
        try:
            raw = file.read_bytes()
        except OSError:
            return self._json({"error": "File giao diện không tồn tại"}, HTTPStatus.NOT_FOUND)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; "
                         "script-src 'self'; style-src 'self'; connect-src 'self'; base-uri 'none'; "
                         "form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def do_POST(self):
        if not self._local_request():
            return
        endpoint = urlparse(self.path).path
        if endpoint not in ("/api/chat", "/api/goals", "/api/rca", "/api/network"):
            return self._json({"error": "Không tìm thấy"}, HTTPStatus.NOT_FOUND)
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self._json({"error": "Content-Type phải là application/json"}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 0 < length <= 16000:
            return self._json({"error": "Request JSON quá lớn hoặc rỗng"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
        try:
            data = json.loads(self.rfile.read(length))
            if endpoint == "/api/network":
                if type(data) is not dict or data:
                    raise ValueError("Network API chỉ nhận JSON object rỗng; cấu hình lấy từ server")
                if platform.system() != "Linux" or os.name == "nt" or getattr(self.server, "default_source", "replay") != "live":
                    raise ValueError("Network overview chỉ có trong Linux live mode")
                from gateway_pilot.application.diagnose_network import diagnose_network
                return self._json(diagnose_network())
            if isinstance(data, dict):
                data.setdefault("source_mode", getattr(self.server, "default_source", "replay"))
            result = (analyze_goals(data) if endpoint == "/api/goals" else
                      analyze_rca(data) if endpoint == "/api/rca" else analyze(data))
            return self._json(result)
        except ValueError as exc:
            return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
        except (RuntimeError, ImportError, OSError, KeyError) as exc:
            return self._json({"error": f"Không chạy được backend ({type(exc).__name__}).",
                               "hint": "Kiểm tra dữ liệu replay và các dependency của chế độ đang chọn."},
                              HTTPStatus.SERVICE_UNAVAILABLE)
        except Exception as exc:
            traceback.print_exc()
            return self._json({"error": f"Backend error ({type(exc).__name__}). Xem terminal để biết chi tiết."},
                              HTTPStatus.INTERNAL_SERVER_ERROR)


def main():
    parser = argparse.ArgumentParser(description="Gateway LM v2 local laptop live / replay")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="Mặc định chỉ truy cập từ máy này")
    parser.add_argument("--source", choices=("replay", "live"), default="replay")
    args = parser.parse_args()
    if args.host not in ("127.0.0.1", "localhost"):
        parser.error("Chỉ cho phép localhost")
    if args.source == "live" and os.name != "nt" and platform.system() != "Linux":
        parser.error("Nguồn live yêu cầu Linux hoặc Windows")
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    with ThreadingHTTPServer((args.host, args.port), Handler) as httpd:
        httpd.default_source = args.source
        print(f"Gateway LM Web: http://{args.host}:{httpd.server_port}")
        print(_status()["message"])
        print("Nguồn mặc định: đo từ " + ("Windows." if os.name == "nt" else "Linux laptop.") if args.source == "live" else "Nguồn mặc định: synthetic replay.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nĐã dừng.")


if __name__ == "__main__":
    main()
