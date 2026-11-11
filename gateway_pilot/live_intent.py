"""Map live questions to measurement goals or an explicit capability boundary."""

import re
from dataclasses import dataclass

from .workflow import normalize, route


NETWORK_CHECKS = ("live.gateway", "live.internet", "live.dns")


@dataclass(frozen=True)
class LiveIntent:
    workflow: str
    title: str
    pattern: str
    checks: tuple[str, ...] = ()
    limitation: str = ""


# The same catalog drives fast routing, model candidates and the planner's goals.
CATALOG = {
    "clients": LiveIntent("WF-001", "Danh sách thiết bị đang kết nối",
                          r"\b(?:ai dang online|ai dang ket noi|thiet bi nao dang ket noi|thiet bi nao.*online|"
                          r"danh sach thiet bi|bao nhieu thiet bi|who is online)\b",
                          limitation="Để biết thiết bị nào đang kết nối, Gateway LM cần bảng thiết bị từ router hoặc điểm phát Wi-Fi. Máy Windows chỉ quan sát được kết nối của chính nó."),
    "router_resources": LiveIntent("WF-039", "CPU, RAM và bộ nhớ của router",
                                    r"\b(?:cpu|ram|bo nho|nhiet do|luu tru|(?:router|gateway|modem) (?:co )?(?:dang )?qua tai)\b",
                                    limitation="Cần quyền đọc số đo CPU, RAM, bộ nhớ hoặc nhiệt độ trực tiếp từ router. Ping từ Windows chỉ cho biết đường tới router có phản hồi hay không."),
    "dhcp": LiveIntent("WF-024", "Địa chỉ cấp phát, DHCP pool và lease",
                       r"\b(?:dhcp|pool|lease|cap phat ip|khong co ip|chua nhan duoc ip)\b",
                       limitation="Để kiểm tra cấp phát IP, cần bảng lease và dải cấp phát của router. Phép đo từ Windows chỉ đọc được tuyến IPv4 mà máy đang dùng."),
    "radio": LiveIntent("WF-006", "Cường độ sóng, kênh và băng tần Wi-Fi",
                        r"\b(?:rssi|cuong do song|tin hieu wi fi|tin hieu wifi|song yeu|bang tan|kenh wi fi|kenh wifi)\b",
                        limitation="Phép đo hiện tại chưa đọc được cường độ sóng, kênh hoặc băng tần. Bạn có thể hỏi độ trễ và mất gói từ máy này để kiểm tra phần kết nối đo được."),
    "throughput": LiveIntent("LIVE-THROUGHPUT", "Tốc độ tải lên hoặc tải xuống theo Mbps",
                             r"\b(?:mbps|gbps|bang thong|toc do mang|toc do internet|toc do tai|speedtest|download speed|upload speed)\b",
                             NETWORK_CHECKS, "Chưa đo được tốc độ tải lên hoặc tải xuống theo Mbps. Dưới đây là độ trễ, mất gói và DNS từ máy này."),
    "quality": LiveIntent("LIVE-QUALITY", "Chất lượng mạng, độ trễ, mất gói hoặc mạng chập chờn",
                          r"\b(?:do tre|latency|mat goi|packet loss|jitter|lag|giat|chap chon|mang cham|mang yeu|"
                          r"(?:mang|internet|wi fi|wifi|duong truyen) (?:co )?(?:on|the nao|chat luong|qua tai)|"
                          r"chat luong (?:ket noi|mang|wi fi|wifi|internet|duong truyen))\b", NETWORK_CHECKS),
    "dns": LiveIntent("LIVE-DNS", "Kiểm tra phân giải DNS từ máy Windows",
                      r"\b(?:dns|ten mien|phan giai)\b", ("live.dns",)),
    "connectivity": LiveIntent("LIVE-INTERNET", "Kiểm tra Internet hoặc kết nối IPv4",
                               r"\b(?:internet|mat mang|vao mang|ket noi mang|wan|uplink)\b", NETWORK_CHECKS),
    "gateway": LiveIntent("LIVE-GATEWAY", "Địa chỉ và phản hồi của gateway mặc định",
                          r"\b(?:gateway|router|cong mac dinh|default gateway)\b", ("live.gateway",)),
}

LEGACY_INTENTS = {"WF-018": "connectivity", "WF-INTERNET": "connectivity", "WF-023": "dns",
                  "WF-024": "dhcp", "WF-039": "router_resources"}
NETWORK_WORD = re.compile(r"\b(?:mang|internet|wifi|wi fi|router|gateway|ket noi|duong truyen|dns|wan|ping)\b")
NETWORK_SUBJECT = re.compile(r"\b(?:mang|internet|wifi|wi fi|ket noi|duong truyen)\b")
ASSESSMENT_WORDS = re.compile(r"\b(?:chat luong|on dinh|dang tin|tinh trang|ra sao|the nao|tot khong|cham khong)\b")


def understand_live(request, advisor=None):
    text = normalize(request)
    workflow = route(text)
    if workflow == "WF-WRITE":
        return ("write",), {"source": "rules"}
    matches = tuple(key for key, intent in CATALOG.items() if re.search(intent.pattern, text))
    # Generic mentions of a router or Internet provide a fallback, not a second task.
    specific = tuple(key for key in matches if key not in {"connectivity", "gateway"})
    if not specific and NETWORK_SUBJECT.search(text) and ASSESSMENT_WORDS.search(text):
        specific = ("quality",)
    legacy = LEGACY_INTENTS.get(workflow)
    keys = specific or matches[:1] or ((legacy,) if legacy else ())
    understand = getattr(advisor, "understand_live_request", None)
    if keys or not NETWORK_WORD.search(text) or not callable(understand):
        return keys, {"source": "rules"}

    intake = {"source": "llm", "model": advisor.model, "accepted": False}
    try:
        proposed = understand(request, {key: value.title for key, value in CATALOG.items()})
    except (OSError, KeyError, TypeError, ValueError) as exc:
        intake["reason"] = type(exc).__name__
    else:
        if isinstance(proposed, str) and proposed in CATALOG:
            intake["accepted"] = True
            return (proposed,), intake
    return (), intake


def combined_intent(keys):
    intents = [CATALOG[key] for key in keys]
    if len(intents) == 1:
        return intents[0]
    lead = next((intent for intent in intents if intent.checks), intents[0])
    checks = tuple(dict.fromkeys(check for intent in intents for check in intent.checks))
    limitations = " ".join(intent.limitation for intent in intents if intent.limitation)
    return LiveIntent(lead.workflow, lead.title, "", checks, limitations)
