# Laptop-first Skill launcher

Nghiệm thu 16/11/2026 theo yêu cầu chạy laptop trước. Đây là mốc CAT-02/CAT-03; chưa hoàn thành toàn bộ 120 nghiệp vụ.

| Mode | Có thể chạy | Giới hạn |
|---|---|---|
| Live Linux | SK01 định danh laptop, A08 association/AP BSSID của chính laptop | Không kiểm kê client trên router hoặc theo dõi roaming |
| Live Linux | `laptop.network.inspect`, `laptop.wifi.inspect`, `laptop.ipv4.inspect`, `laptop.route.inspect`, `laptop.gateway.inspect`, `laptop.dns.inspect` | 6 action namespace riêng; không tính vào 120 thiết kế |
| Replay | B02/B03/B05 | Fixture synthetic đã review, không phải số đo laptop/router |

Catalog live có 126 hàng: 120 thiết kế + 6 action laptop. Trong 120 thiết kế, chỉ SK01/A08 có mapping local; 118 hàng còn lại unavailable kèm lý do. Đặc biệt B04 thiếu RSSI/SNR, B07 thiếu history, SK13 WRITE bị chặn. Windows vẫn giữ luồng live cũ; launcher live này yêu cầu Linux/NetworkManager.

## Dùng Web và CLI

Chạy theo README, mở localhost, tìm mục **Chọn Skill trên laptop**. Bấm **Khởi tạo phiên**, lọc **Có thể chạy trong phiên**, chọn và chạy. Danh mục/khởi tạo chỉ probe khả năng đọc; lấy mẫu khi bấm Chạy. Nguồn phiên độc lập với cấu hình chat. Đổi nguồn sẽ đóng phiên cũ và xóa kết quả. Evidence có source/target/scope/time/TTL; UI xóa số đo hết hạn. History chỉ giữ tham chiếu trong bộ nhớ, không chứng minh fact còn mới.

```bash
python -m scripts.skills list --mode live
python -m scripts.skills run laptop.network.inspect --mode live
python -m scripts.skills run A08 --mode live
python -m scripts.skills run B02 --mode replay
```

CLI mỗi lệnh tạo một phiên rồi đóng. Web tái sử dụng evidence giữa nhiều lượt trong cùng phiên: TTL contract từng Port, tối đa 300s/24 calls/64 plans, 8 phiên/server. Expiry/context/permission/binding thay đổi làm mất hiệu lực evidence. Hết budget không tạo quyền chạy thêm. Không có fallback live → replay.

## API localhost

- `GET /api/skills?mode=live|replay`: metadata + availability chưa xác minh trước phiên.
- `POST /api/skills/session` JSON `{"mode":"live"}`: tạo phiên, probe capability, catalog READY/DEGRADED/UNAVAILABLE.
- `POST /api/skills/run` JSON `{"session_id":"…","skill_id":"A08"}`: chạy qua bridge/session/Core, snapshot đã verify.
- `POST /api/skills/close` JSON `{"session_id":"…"}`: đóng phiên.

Không nhận command, Function IDs, target, profile, permissions, backend hay path. Session không hợp lệ/hết hạn trả 410, hết capacity 429. API chỉ phục vụ localhost với Host/Origin guards. Không bật server ra mạng.

## Ranh giới triển khai

`examples/skill_deployments/` chứa metadata triển khai riêng; `config/skill_launcher/approvals.json` pin registry/action/backend revisions. Builder kiểm pins khi nạp; không tự phê duyệt source proposal khi khởi động. 72 source contracts vẫn PROPOSED; 203 proposed edges chưa được duyệt tự động. Execution đi qua RuntimeSkillBridge → ReadSession → shared execute_ready_once/GraphRunner → Verifier → VerifiedSnapshot. Không có đường gọi OS trực tiếp từ HTTP/model.

Live A08 dùng association/BSSID thực từ NetworkManager, contract v2 có dependency định danh client. Signal phần trăm không biến thành RSSI dBm/SNR. Route Internet có thể dùng Ethernet dù Wi-Fi đang associated. Phép đo hoàn thành không phải RCA/khôi phục đã xác minh. OpenWrt firmware, monitoring/history bền, LLM adaptive RCA và 118 thiết kế còn lại tiếp tục backlog NEXT.

## Kết quả nghiệm thu local

[Biên bản đã bỏ định danh mạng](reports/LAPTOP_SKILL_ACCEPTANCE_20261116.json): 8/8 lựa chọn live MEASURED, tổng 8 tool calls trong một phiên; 5 lượt tiếp theo tái sử dụng evidence nên thêm 0 calls. Replay B02/B03/B05: 3/3 MEASURED, synthetic_only=true. Trình duyệt localhost đã khởi tạo/lọc/chọn/chạy network action và hiển thị đúng đường đo Ethernet khác Wi-Fi. Đây là một lần kiểm tra local, không phải đo hiệu năng hay nghiệm thu firmware.

Validation: full unittest discovery **718 tests, 713 pass, 5 Windows-only skips**; `scripts.check_project`, JavaScript syntax/lifecycle harness và independent review đạt. Frozen `data/`/`benchmarks/` không đổi. CI cho commit được ghi tại lịch sử Actions trên nhánh v2.
