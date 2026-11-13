# FND-07 — Laptop network live, snapshot và UI

[README chạy thử](../README.md) · [Foundation](superpowers/specs/2026-11-13-command-catalog-v02-design.md) · [Plan](superpowers/plans/2026-11-13-fnd-07-laptop-demo.md).

## Luồng triển khai

`LinuxWifiBackend → catalog v0.2 → ReadRuntime → execute_ready_once → GraphRunner/Verifier → CaseState.fact → VerifiedSnapshot → laptop rules → Web`.

Profile riêng [catalog_laptop_network](../examples/catalog_laptop_network/) có **7 selected READ Functions**: clients.resolve, client.ipv4, laptop.route, laptop.wifi, laptop.gateway_probe, laptop.internet_probe, laptop.dns. Exact versions, budgets, inputs và schemas được kiểm bởi builder. Đây là profile riêng; không thay seed replay, profile laptop identity/IPv4 FND-04 hay data/benchmarks v0.1. Metadata approval [pin](../config/laptop_network_approval.json) phải khớp artifact, không tự cập nhật khi startup.

Composition root chỉ tạo reviewed local Linux backend với source/revision/probe IDs cố định, pin target local-laptop và environment được khám phá tại server. Operator khởi động Linux live là chọn READ trên laptop này. Không nhận backend, interface, registry, approval, permission hoặc targets từ HTTP. Khi đổi contract phải rebuild artifact và review/update approval pin trong code review.

## Phép đo và giới hạn

- `nmcli device status`, `nmcli radio wifi`, Wi-Fi list với **`--rescan no`**; không đổi connection/radio. Parse escaped colon/backslash, chỉ đọc active AP, giữ SSID/BSSID như untrusted display text.
- Signal là **%**, missing = -1; không đổi sang RSSI dBm. Channel/frequency thiếu dùng 0; UI báo chưa có. `ap_rate_mbps` là tốc độ AP quảng bá từ NetworkManager RATE, **không** negotiated link rate hay throughput Internet.
- `ip -j route get 1.1.1.1` chọn route IPv4 thực. Source và gateway được validate là IPv4, interface có bound/cú pháp. Network-unreachable được phân biệt với lỗi đọc/permission.
- Ping 4 gói cố định, bind source IPv4 của route, timeout 6 giây; gateway từ kernel route, IP công cộng cố định **1.1.1.1**. Không nhận địa chỉ đích từ chat. 100% loss vẫn là valid ICMP measurement, không đủ kết luận Internet/router hỏng. Missing RTT = -1 và UI/chat không trình bày thành latency âm.
- DNS dùng `resolvectl --interface=<route> --cache=no query --type=A example.com`, timeout 6 giây. Đây là phép thử resolver từ interface đã chọn, không kiểm truy cập website hoặc tổng thể DNS mọi ứng dụng.
- Thiếu `ping`/`resolvectl`, radio off/disconnected, missing metrics hoặc timeout không sinh số đo giả. CPU/RAM/router health UNAVAILABLE; chưa router firmware/NPU/WRITE acceptance.

Backend pin boot/netns/interface incarnation, Wi-Fi association/AP, IPv4, route và resolver configuration. Mỗi sample và support check đối chiếu environment trước/sau; đổi route/resolver/association trong batch làm snapshot rỗng thay vì trộn hai môi trường. Không tự tắt Wi-Fi/rút mạng để thử.

Nếu Wi-Fi và Ethernet/VPN cùng tồn tại, Internet/DNS đo trên interface mà kernel chọn. UI ghi rõ interface; probe Ethernet không chứng minh đường Wi-Fi tốt. Fingerprint là gate cho sample batch, không monitoring liên tục.

## Snapshot và rules

`VerifiedSnapshot.from_state` chỉ nhận CaseState, lấy `state.fact`, copy vào immutable bytes. Raw JSON không đi qua factory; replay bị loại trừ mặc định và chỉ cho phép rõ ràng trong tests. Mỗi fact giữ evidence ID, Function/runtime digest, scope, target, source, observation time, value và expiry. Snapshot export kiểm lại environment/freshness, trả copy mới; caller không thể mutate nested value đã phát hành.

TTL là **30 giây tính từ phép đo**, không 30 giây mới sau HTTP response. Server trả remaining TTL và absolute `expires_at`. UI giới hạn thời gian còn lại bằng absolute expiry rồi dùng performance clock để hết hạn; không trừ thời gian thu mẫu lần thứ hai. Hết hạn xóa facts/status và yêu cầu Làm mới. Không có polling thu mẫu nền; chat là kết quả tại thời điểm nêu trong câu trả lời.

Feature availability READY/DEGRADED/UNAVAILABLE/DISABLED đến từ trusted Core support snapshot, khác kết quả rules MEASURED/ISSUE/INCOMPLETE. Rules chỉ nói điều measurement chứng minh, kèm evidence IDs, missing ports, code và next steps; không tạo causal Claim. Signal dưới 40% được gắn nhãn heuristic signal thấp, không là ngưỡng throughput/chuẩn nghiệm thu RF.

## API và chạy thử

```bash
bash web_gateway/start_linux.sh --port 8766
```

Mở [localhost:8766](http://127.0.0.1:8766), bấm **Đo / Làm mới**. Linux live dùng shared Core READ cố định; UI khóa LLM/ReAct/ranking ở chế độ này. Windows route/ping/DNS và replay giữ flow cũ.

- `POST /api/network`, body **`{}`**: overview Linux live; chỉ server khởi động live, platform Linux. Body có field bị từ chối; Host/Origin localhost guard giữ nguyên.
- `POST /api/chat`: `source_mode=live` trên Linux chọn bounded measurement goals từ câu hỏi; không cho text/model chọn commands/targets. Các câu về thay cấu hình, client khác hoặc router resources chỉ trả capability boundary, không đo router. `method` là trường tương thích UI; Linux dùng shared deterministic Core, không tuyên bố chạy BM25/GoS/ReAct theo lựa chọn cũ.
- `/api/goals` và `/api/rca` tiếp tục replay-only. Không expose Core snapshot injection hay WRITE API.

Gợi ý: Wi-Fi laptop có vấn đề gì? / Gateway hiện tại là gì? / Kiểm tra Internet của máy này / Kiểm tra DNS. Chuyển sang replay để kiểm nghiệm kịch bản tổng hợp; không gắn số liệu replay với laptop.

## Kiểm chứng

```bash
.venv-graph/bin/python -m unittest tests.adapters.test_linux_wifi tests.observability.test_snapshot tests.features.test_laptop_network tests.web.test_features -v
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m unittest discover -s tests -v
```

Tests dùng synthetic/mocked commands, không phát ping thật. Live acceptance riêng và những tình huống chưa thử trên phần cứng được ghi tại [báo cáo FND-07](reports/FND07_LAPTOP_NETWORK_20261113.md). Router và monitoring/history tiếp tục backlog riêng.
