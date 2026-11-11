"""Build benchmarks/conversation_v1.json and its SHA-256 manifest (C5).

Environment: the GLM-21-1 replay adapter world with two inventory devices
(laptop-an, my-phone). Dev and holdout sentences are new; the holdout also
contains the 26 sentences the C2 review wrote for its independent check, which
were never given to the implementer nor used to tune the router. For runnable
DIAGNOSE / LOOKUP turns the required Function set and the expected case status
come from the contract compiler and an oracle run, as in T9.

Run from the pilot directory:  python benchmarks/build_conversation_v1.py
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

OUT = ROOT / "benchmarks/conversation_v1.json"
MANIFEST = ROOT / "benchmarks/conversation_v1.manifest.json"

# (message, turn_type, workflow or lookup port or None, expected action)
# action: RUN | ASK_USER | UNSUPPORTED | ANSWER | REFUSE
D, L, K, C, X, S, O = "DIAGNOSE", "LOOKUP", "KNOWLEDGE", "CAPABILITY", "CHANGE", "SMALLTALK", "OUT_OF_SCOPE"
DEV = [
    # DIAGNOSE WF-018 (gateway, no target needed)
    ("mạng nhà tôi mất kết nối ra ngoài từ trưa", D, "WF-018", "RUN"),
    ("internet nha toi bi dut lien tuc", D, "WF-018", "RUN"),
    ("the internet connection drops every few minutes", D, "WF-018", "RUN"),
    ("họp zoom bị đứng hình liên tục cả nhà", D, "WF-018", "RUN"),
    ("duong truyen cap quang nha minh co van de khong", D, "WF-018", "RUN"),
    ("is my ISP link down right now", D, "WF-018", "RUN"),
    # WF-023
    ("gõ tên trang web thì không vào được nhưng gõ IP thì được", D, "WF-023", "RUN"),
    ("khong phan giai duoc ten mien tren router", D, "WF-023", "RUN"),
    ("websites will not load by name only by address", D, "WF-023", "RUN"),
    ("trình duyệt báo không tìm thấy địa chỉ máy chủ", D, "WF-023", "RUN"),
    ("dns cua modem co hoat dong khong", D, "WF-023", "RUN"),
    ("name resolution keeps failing on the gateway", D, "WF-023", "RUN"),
    # WF-024 (client)
    ("laptop-an không nhận được địa chỉ IP", D, "WF-024", "RUN"),
    ("laptop-an bao dang lay dia chi ip mai khong xong", D, "WF-024", "RUN"),
    ("laptop-an is stuck acquiring an address", D, "WF-024", "RUN"),
    ("máy mới cắm dây không lấy được IP", D, "WF-024", "ASK_USER"),
    ("my-phone khong duoc cap phat dia chi", D, "WF-024", "RUN"),
    ("a new device cannot get an address from dhcp", D, "WF-024", "ASK_USER"),
    # WF-039
    ("router chạy rất chậm, có phải đầy bộ nhớ không", D, "WF-039", "RUN"),
    ("modem nong va treo lien tuc", D, "WF-039", "RUN"),
    ("is the router running out of ram", D, "WF-039", "RUN"),
    ("cục phát wifi ì ạch, CPU có cao không", D, "WF-039", "RUN"),
    ("bo nho luu tru cua router co day khong", D, "WF-039", "RUN"),
    ("gateway feels overloaded today", D, "WF-039", "RUN"),
    # WF-INTERNET (client)
    ("laptop-an có wifi nhưng không vào được trang nào", D, "WF-INTERNET", "RUN"),
    ("laptop-an bat duoc wifi ma khong len mang", D, "WF-INTERNET", "RUN"),
    ("laptop-an shows full wifi bars but nothing loads", D, "WF-INTERNET", "RUN"),
    ("điện thoại của tôi có sóng wifi mà không lướt web được", D, "WF-INTERNET", "ASK_USER"),
    ("my-phone ket noi wifi roi nhung khong vao mang", D, "WF-INTERNET", "RUN"),
    ("my laptop says connected but the browser times out", D, "WF-INTERNET", "ASK_USER"),
    # two intents
    ("wan chập chờn và router có quá tải không", D, "WF-018+WF-039", "RUN"),
    ("dns loi va laptop-an khong lay duoc ip", D, "WF-023+WF-024", "RUN"),
    # CATALOG_ONLY
    ("đèn LOS trên ONT nhấp nháy đỏ", D, "UNSUPPORTED", "UNSUPPORTED"),
    ("vpn ve cong ty khong ket noi duoc", D, "UNSUPPORTED", "UNSUPPORTED"),
    ("set up a guest wifi schedule for the kids", D, "UNSUPPORTED", "UNSUPPORTED"),
    # LOOKUP
    ("cổng WAN đang lên hay xuống", L, "wan.status", "RUN"),
    ("router con bao nhieu ram trong", L, "system.resources", "RUN"),
    ("what dns server is the router using", L, "dns.config", "RUN"),
    ("dải DHCP còn bao nhiêu địa chỉ trống", L, "dhcp.pool", "RUN"),
    ("is the default route present", L, "wan.routes", "RUN"),
    ("dich vu dhcp co dang chay khong", L, "dhcp.service", "RUN"),
    ("cpu của router đang dùng bao nhiêu phần trăm", L, "system.resources", "RUN"),
    ("is the wan link up", L, "wan.status", "RUN"),
    # KNOWLEDGE
    ("DHCP là gì", K, None, "ANSWER"),
    ("dns hoat dong nhu the nao", K, None, "ANSWER"),
    ("what is a default route", K, None, "ANSWER"),
    ("cách kiểm tra máy có nhận IP không", K, None, "ANSWER"),
    ("lam sao de biet wifi bi nhieu", K, None, "ANSWER"),
    ("how to read a dhcp lease", K, None, "ANSWER"),
    ("mất gói nghĩa là gì", K, None, "ANSWER"),
    # CAPABILITY
    ("bạn làm được những gì", C, None, "ANSWER"),
    ("ban ho tro kiem tra gi", C, None, "ANSWER"),
    ("what can you do", C, None, "ANSWER"),
    ("bạn có đo được tốc độ mạng không", C, None, "ANSWER"),
    ("ban giup duoc gi cho mang nha toi", C, None, "ANSWER"),
    ("what can you check on my router", C, None, "ANSWER"),
    ("bạn hỗ trợ những gì", C, None, "ANSWER"),
    ("bạn kiểm tra được những gì cho router", C, None, "ANSWER"),
    # CHANGE
    ("đổi mật khẩu wifi thành abc12345", X, None, "REFUSE"),
    ("doi dns sang 1.1.1.1", X, None, "REFUSE"),
    ("set the wifi channel to 11", X, None, "REFUSE"),
    ("cập nhật firmware cho router", X, None, "REFUSE"),
    ("apply a qos profile for gaming", X, None, "REFUSE"),
    ("thay doi dai dhcp", X, None, "REFUSE"),
    ("please change the admin password", X, None, "REFUSE"),
    # SMALLTALK
    ("chào bạn", S, None, "ANSWER"),
    ("cam on nhe", S, None, "ANSWER"),
    ("hello there", S, None, "ANSWER"),
    ("cảm ơn bạn", S, None, "ANSWER"),
    ("thanks a lot", S, None, "ANSWER"),
    ("tam biet", S, None, "ANSWER"),
    ("hi", S, None, "ANSWER"),
    # OUT_OF_SCOPE
    ("hôm nay ăn gì ngon", O, None, "ANSWER"),
    ("viet giup toi mot bai tho", O, None, "ANSWER"),
    ("who won the football match yesterday", O, None, "ANSWER"),
    ("giá bitcoin hôm nay", O, None, "ANSWER"),
    ("dich cau nay sang tieng nhat", O, None, "ANSWER"),
    ("recommend a good movie", O, None, "ANSWER"),
    ("lịch thi đấu bóng đá tuần này", O, None, "ANSWER"),
]
HOLDOUT = [
    # The C2 review's 26 independent sentences (labels from that review).
    ("laptop-an hiện wifi nhưng không mở được trang nào", D, "WF-INTERNET", "RUN"),
    ("mang nha minh cham rua tu chieu", D, "WF-018", "RUN"),
    ("the whole house lost internet an hour ago", D, "WF-018", "RUN"),
    ("mất kết nối internet toàn bộ", D, "WF-018", "RUN"),
    ("truy cập bằng địa chỉ IP được nhưng tên miền thì không", D, "WF-023", "RUN"),
    ("dns has stopped resolving", D, "WF-023", "RUN"),
    ("laptop-an bi 169.254 khong co ip", D, "WF-024", "RUN"),
    ("new phone cannot get an ip", D, "WF-024", "ASK_USER"),
    ("modem nóng ran và hay khởi động lại", D, "WF-039", "RUN"),
    ("cpu cua router cao bat thuong", D, "WF-039", "RUN"),
    ("đèn PON nhấp nháy đỏ", D, "UNSUPPORTED", "UNSUPPORTED"),
    ("vpn tới công ty không kết nối được", D, "UNSUPPORTED", "UNSUPPORTED"),
    ("DNS router đang dùng là gì", L, "dns.config", "RUN"),
    ("WAN có IP chưa", L, "wan.status", "RUN"),
    ("how much memory is free on the router", L, "system.resources", "RUN"),
    ("NAT là gì", K, None, "ANSWER"),
    ("làm sao để đặt mật khẩu wifi mạnh", K, None, "ANSWER"),
    ("bạn hỗ trợ những gì nữa", C, None, "ANSWER"),
    ("có đo được tốc độ mạng không", C, None, "ANSWER"),
    ("đặt lại mật khẩu wifi thành 12345678", X, None, "REFUSE"),
    ("please restart the router", X, None, "REFUSE"),
    ("cảm ơn nhé", S, None, "ANSWER"),
    ("giá vàng hôm nay bao nhiêu", O, None, "ANSWER"),
    ("kể chuyện cười đi", O, None, "ANSWER"),
    ("công thức nấu phở bò", O, None, "ANSWER"),
    ("wifi yếu và router có quá tải không", D, "WF-INTERNET+WF-039", "RUN"),
    # New holdout sentences.
    ("nhà mình rớt mạng liên tục từ tối qua", D, "WF-018", "RUN"),
    ("khong vao duoc mang ca nha", D, "WF-018", "RUN"),
    ("our broadband keeps disconnecting", D, "WF-018", "RUN"),
    ("đường truyền internet có vấn đề gì không", D, "WF-018", "RUN"),
    ("ping 8.8.8.8 duoc nhung vao google.com khong duoc", D, "WF-023", "RUN"),
    ("pages fail with server not found but ip works", D, "WF-023", "RUN"),
    ("router có dịch được tên miền không", D, "WF-023", "RUN"),
    ("laptop-an không có địa chỉ IPv4", D, "WF-024", "RUN"),
    ("my-phone never receives an ip lease", D, "WF-024", "RUN"),
    ("thiet bi moi khong nhan duoc dia chi", D, "WF-024", "ASK_USER"),
    ("ram router sắp hết chưa", D, "WF-039", "RUN"),
    ("the router reboots itself and feels sluggish", D, "WF-039", "RUN"),
    ("bộ nhớ router có đầy không", D, "WF-039", "RUN"),
    ("laptop-an vào wifi được mà youtube không chạy", D, "WF-INTERNET", "RUN"),
    ("my-phone has wifi but apps say no connection", D, "WF-INTERNET", "RUN"),
    ("may cua toi co wifi ma khong len mang", D, "WF-INTERNET", "ASK_USER"),
    ("laptop-an connected but every site times out", D, "WF-INTERNET", "RUN"),
    ("mạng lag và dns có lỗi không", D, "WF-018+WF-023", "RUN"),
    ("tín hiệu quang yếu, công suất thu thấp", D, "UNSUPPORTED", "UNSUPPORTED"),
    ("hẹn giờ tắt wifi buổi tối", D, "UNSUPPORTED", "UNSUPPORTED"),
    ("default route có tồn tại không", L, "wan.routes", "RUN"),
    ("dhcp pool con bao nhieu dia chi", L, "dhcp.pool", "RUN"),
    ("is the dhcp service running", L, "dhcp.service", "RUN"),
    ("cổng wan có liên kết không", L, "wan.status", "RUN"),
    ("ram trống của router bao nhiêu", L, "system.resources", "RUN"),
    ("router dang dung dns nao", L, "dns.config", "RUN"),
    ("what is dhcp", K, None, "ANSWER"),
    ("cách đổi kênh wifi", K, None, "ANSWER"),
    ("tuyến mặc định là gì", K, None, "ANSWER"),
    ("how to tell if dns is the problem", K, None, "ANSWER"),
    ("lease dhcp nghia la gi", K, None, "ANSWER"),
    ("vì sao wifi đầy vạch mà không vào mạng là gì", K, None, "ANSWER"),
    ("làm sao để kiểm tra cáp mạng", K, None, "ANSWER"),
    ("bạn giúp được gì", C, None, "ANSWER"),
    ("what checks do you support", C, None, "ANSWER"),
    ("ban lam duoc nhung gi", C, None, "ANSWER"),
    ("bạn có kiểm tra wifi không", C, None, "ANSWER"),
    ("help me with what you can do", C, None, "ANSWER"),
    ("đổi tên wifi thành NhaMinh", X, None, "REFUSE"),
    ("set dns to 8.8.4.4", X, None, "REFUSE"),
    ("cai dat lai router ve mac dinh", X, None, "REFUSE"),
    ("update the router firmware", X, None, "REFUSE"),
    ("thay mật khẩu quản trị", X, None, "REFUSE"),
    ("apply parental control", X, None, "REFUSE"),
    ("xin chào", S, None, "ANSWER"),
    ("thank you", S, None, "ANSWER"),
    ("chao buoi sang", S, None, "ANSWER"),
    ("bye", S, None, "ANSWER"),
    ("cảm ơn bạn nhé", S, None, "ANSWER"),
    ("hello", S, None, "ANSWER"),
    ("thời tiết ngày mai thế nào", O, None, "ANSWER"),
    ("viết email xin nghỉ phép", O, None, "ANSWER"),
    ("what is the capital of france", O, None, "ANSWER"),
    ("kể một câu chuyện cổ tích", O, None, "ANSWER"),
    ("tỷ giá đô la hôm nay", O, None, "ANSWER"),
    ("goi y mon an toi nay", O, None, "ANSWER"),
]
# Multi-turn conversations: (split, [(message, turn_type, workflow, action), ...])
CONVERSATIONS = [
    ("dev", [("máy tôi có wifi mà không vào mạng", D, "WF-INTERNET", "ASK_USER"),
             ("laptop-an", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
    ("dev", [("laptop-an có wifi mà không vào được mạng", D, "WF-INTERNET", "RUN"),
             ("còn my-phone thì sao", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
    ("dev", [("thiết bị không nhận IP", D, "WF-024", "ASK_USER"),
             ("my-phone", "FOLLOW_UP", "WF-024", "RUN")]),
    ("dev", [("my device has wifi but no internet", D, "WF-INTERNET", "ASK_USER"),
             ("my-phone", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
    ("dev", [("laptop-an không nhận được IP", D, "WF-024", "RUN"),
             ("what about my-phone", "FOLLOW_UP", "WF-024", "RUN")]),
    ("dev", [("chào bạn", S, None, "ANSWER"),
             ("laptop-an có wifi mà không vào được mạng", D, "WF-INTERNET", "RUN")]),
    ("holdout", [("may cua toi khong vao duoc mang du co wifi", D, "WF-INTERNET", "ASK_USER"),
                 ("laptop-an", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
    ("holdout", [("my-phone có wifi nhưng không vào mạng", D, "WF-INTERNET", "RUN"),
                 ("còn laptop-an thì sao", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
    ("holdout", [("a device cannot get an ip", D, "WF-024", "ASK_USER"),
                 ("laptop-an", "FOLLOW_UP", "WF-024", "RUN")]),
    ("holdout", [("laptop-an không có IP", D, "WF-024", "RUN"),
                 ("con my-phone thi sao", "FOLLOW_UP", "WF-024", "RUN")]),
    ("holdout", [("điện thoại không vào được mạng dù có wifi", D, "WF-INTERNET", "ASK_USER"),
                 ("my-phone", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
    ("holdout", [("cảm ơn", S, None, "ANSWER"),
                 ("router còn bao nhiêu RAM", L, "system.resources", "RUN")]),
    ("dev", [("thiết bị của tôi không vào được mạng", D, "WF-INTERNET", "ASK_USER"),
             ("laptop-an", "FOLLOW_UP", "WF-INTERNET", "RUN"),
             ("còn my-phone thì sao", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
    ("holdout", [("my device cannot get an ip", D, "WF-024", "ASK_USER"),
                 ("my-phone", "FOLLOW_UP", "WF-024", "RUN"),
                 ("what about laptop-an", "FOLLOW_UP", "WF-024", "RUN")]),
    ("holdout", [("laptop-an vào wifi được mà không lướt web", D, "WF-INTERNET", "RUN"),
                 ("còn my-phone thì sao", "FOLLOW_UP", "WF-INTERNET", "RUN")]),
]


def replay(registry):
    fixture = next(c for c in read_json(ROOT / "data/cases.json") if c["id"] == "GLM-21-1")
    rp = replay_from_fixture(fixture, registry)
    phone = copy.deepcopy(rp["devices"][0])
    phone.update(selector="my-phone", aliases=["điện thoại của tôi", "my phone"], client_id="client_phone")
    phone["world"]["clients.resolve"] = {"client_id": "client_phone"}
    rp["devices"][0]["aliases"] = ["laptop của tôi", "my laptop"]
    rp["devices"].append(phone)
    return rp


def oracle(registry, rp, message, goals, device_message=None):
    """Required Functions and expected status for a runnable turn (compiler + oracle run)."""
    device = match_device(normalize(device_message or message), rp["devices"])
    target, world = {"scope": "gateway", "id": "gateway_01"}, dict(rp["world"])
    if device is not None:
        target = {"scope": "client", "selector": device["selector"], "client_id": device["client_id"]}
        world.update(device["world"])
    case = {"target": target, "world": world, "capabilities": rp["capabilities"], "initial_evidence": []}
    state = CaseState(case, registry, lambda: 0.0)
    measurable = []
    for goal in goals:
        if registry.ports[goal].scope == "client" and not target.get("client_id"):
            continue
        try:
            Compiler(registry).compile([goal], state)
            measurable.append(goal)
        except PlanError:
            pass
    if not measurable:
        return [], state.case_status(goals, exhausted=True)
    plan = Compiler(registry).compile(measurable, state)
    GraphRunner(registry, case, state).run(plan)
    return sorted(n.function_id for n in plan.nodes.values()), state.case_status(goals, exhausted=True)


def labelled(registry, rp, message, kind, target, action, previous=None):
    turn = {"message": message, "turn_type": kind, "action": action}
    if kind in ("DIAGNOSE", "FOLLOW_UP") and target not in (None, "UNSUPPORTED"):
        turn["workflows"] = target.split("+")
    elif kind == "LOOKUP":
        turn["lookup_port"] = target
    elif target == "UNSUPPORTED":
        turn["workflows"] = []
    if action == "RUN":
        goals = ([target] if kind == "LOOKUP" else
                 list(dict.fromkeys(g for w in turn["workflows"] for g in registry.goal_ports[w])))
        request = previous if kind == "FOLLOW_UP" and previous else message
        turn["required_functions"], turn["expected_status"] = oracle(
            registry, rp, request, goals, device_message=message if kind == "FOLLOW_UP" else None)
    else:
        turn["required_functions"] = []
        turn["expected_status"] = {"ASK_USER": "NEEDS_INPUT", "REFUSE": "BLOCKED"}.get(action)
    return turn


def build():
    registry = GraphRegistry.from_v01()
    rp = replay(registry)
    items = []
    for split, rows in (("dev", DEV), ("holdout", HOLDOUT)):
        for i, (message, kind, target, action) in enumerate(rows):
            items.append({"id": f"CV-{split}-{i:03}", "split": split,
                          "turns": [labelled(registry, rp, message, kind, target, action)]})
    for i, (split, turns) in enumerate(CONVERSATIONS):
        labelled_turns, previous = [], None
        for message, kind, target, action in turns:
            labelled_turns.append(labelled(registry, rp, message, kind, target, action, previous))
            previous = message if kind == "DIAGNOSE" else previous
        items.append({"id": f"CV-{split}-conv-{i:02}", "split": split, "turns": labelled_turns})
    data = {"version": "1.0.0", "environment": "GLM-21-1 adapter world + devices laptop-an, my-phone",
            "note": "Thresholds may be calibrated on dev only; holdout is run once.", "items": items}
    text = json.dumps(data, ensure_ascii=False, indent=1) + "\n"
    OUT.write_text(text, encoding="utf-8", newline="")
    turns = [t for item in items for t in item["turns"]]
    MANIFEST.write_text(json.dumps({
        "file": OUT.name, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(), "items": len(items),
        "turns": len(turns), "conversations": sum(len(i["turns"]) > 1 for i in items),
        "turn_types": {k: sum(t["turn_type"] == k for t in turns) for k in sorted({t["turn_type"] for t in turns})},
        "splits": {s: sum(i["split"] == s for i in items) for s in ("dev", "holdout")}}, indent=1) + "\n",
        encoding="utf-8", newline="")
    return data


if __name__ == "__main__":
    build()
    print(MANIFEST.read_text(encoding="utf-8"))
