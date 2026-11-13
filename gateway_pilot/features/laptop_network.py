"""Laptop feature rules over verified snapshot exports; no OS/adapter imports."""
from __future__ import annotations


def diagnose_snapshot(snapshot: dict, availability: dict) -> list[dict]:
    facts = snapshot["facts"]
    def value(pid):
        return facts[pid]["value"] if pid in facts else None
    def result(fid, title, required, status, code, summary, steps):
        used = [pid for pid in required if pid in facts]
        missing = sorted(set(required)-facts.keys())
        return dict(feature_id=fid, title=title, availability=availability[fid]["status"], status=status,
                    code=code, summary=summary, evidence_ids=[facts[pid]["evidence_id"] for pid in used],
                    missing_ports=missing, next_steps=steps)
    required = ["laptop.route", "laptop.gateway_probe", "laptop.internet_probe", "laptop.dns"]
    route, gateway, internet, dns = (value(p) for p in required)
    status, code, text = "INCOMPLETE", "MISSING_EVIDENCE", "Chưa đủ phép đo route, IP công cộng và DNS."
    steps = ["Đo lại; kiểm tra nguồn kết nối và các phép đo còn thiếu."]
    if route and not route["has_route"]:
        status, code, text = "ISSUE", "NO_ROUTE", "Laptop chưa có đường IPv4 tới IP kiểm tra."
    elif internet and internet["loss_pct"] > 0:
        status, code, text = "ISSUE", "IP_PROBE_LOSS", f"IP kiểm tra mất {internet['loss_pct']:g}% gói ICMP; chưa đủ để xác định nguyên nhân."
    elif dns and not dns["resolved"]:
        status, code, text = "ISSUE", "DNS_NOT_RESOLVED", "Phép thử DNS example.com chưa phân giải được trên interface đã chọn."
    elif route and internet and dns and gateway:
        status, code = "MEASURED", "IP_DNS_RESPONDED"
        text = f"IP công cộng phản hồi: {internet['latency_ms']:g} ms, mất {internet['loss_pct']:g}% gói; DNS example.com phân giải được. Chưa kiểm tra truy cập web."
        steps = ["Nếu ứng dụng vẫn lỗi, kiểm tra riêng URL/dịch vụ hoặc proxy/VPN đang dùng."]
    if route and route["has_route"]:
        text += f" Đường đo: {route['interface']}."
    if gateway and gateway["received"] == 0:
        text += " Gateway không phản hồi ICMP; điều này chưa chứng minh router hỏng."
    conn = result("network.laptop.connectivity", "Kết nối từ laptop", required, status, code, text, steps)
    wifi = value("laptop.wifi")
    status, code, text = "INCOMPLETE", "WIFI_MISSING", "Chưa có evidence Wi-Fi còn hiệu lực."
    steps = ["Đo lại hoặc kiểm tra NetworkManager và interface Wi-Fi."]
    if wifi:
        if not wifi["radio_enabled"]:
            status, code, text = "ISSUE", "WIFI_RADIO_OFF", "Wi-Fi radio đang tắt."
            steps = ["Bật Wi-Fi trong cài đặt hệ điều hành rồi đo lại."]
        elif not wifi["associated"]:
            status, code, text = "ISSUE", "WIFI_DISCONNECTED", "Wi-Fi chưa associated với điểm phát."
            steps = ["Kết nối Wi-Fi trong hệ điều hành rồi đo lại."]
        elif wifi["signal_pct"] < 0:
            status, code, text = "INCOMPLETE", "WIFI_SIGNAL_MISSING", "Wi-Fi đã associated nhưng chưa đọc được signal %."
        else:
            status, code = ("ISSUE", "WIFI_SIGNAL_LOW") if wifi["signal_pct"] < 40 else ("MEASURED", "WIFI_ASSOCIATED")
            text = f"Wi-Fi {wifi['interface']} đã associated; signal {wifi['signal_pct']:g}% (không phải RSSI dBm)."
            steps = ["So sánh lại gần điểm phát; signal không đo tốc độ tải Internet."]
        if route and route["has_route"] and route["interface"] != wifi["interface"]:
            text += f" Probe mạng đi qua {route['interface']}; chưa kiểm chứng Internet qua Wi-Fi."
    return [conn, result("network.laptop.wifi", "Wi-Fi laptop", ["laptop.wifi"], status, code, text, steps)]
