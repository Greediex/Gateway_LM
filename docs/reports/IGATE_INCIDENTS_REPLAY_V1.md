# Gateway LM v2 · Replay 14 sự cố router

Bản replay nạp 14 mẫu sự cố với 36 câu hỏi tiếng Việt. Web giữ ba lựa chọn `normal`, `fault`, `missing` và thêm 14 lựa chọn theo tên tiếng Việt. Dữ liệu là mô phỏng có ngưỡng chưa hiệu chỉnh. Bộ mô phỏng giữ các tín hiệu tham khảo, khuyến nghị và URL gốc. [Nguồn đã nhập](../../data/skill_expansion_v1/incidents_v1/router_incidents_v1.json)

## Kết quả qua Core

Mỗi câu hỏi nguồn chọn một Skill READ bằng cụm triệu chứng đã đăng ký. Router chọn Skill theo câu hỏi. Kịch bản đã gắn với phiên quyết định dữ liệu mà Skill đọc. Runner và Verifier xử lý qua Core, sau đó Claim Engine đánh giá dữ liệu đã xác minh. Bộ đáp án theo sự cố và mô tả nguyên nhân gốc nằm trong gold dành cho kiểm thử. [Gold](../../data/skill_expansion_v1/incidents_v1/gold.json)

| Sự cố | Số câu | Skill | Claim TRUE và kết luận mô phỏng |
|---|---:|---|---|
| `INC-DHCP-EXHAUST` | 3 | D02 | `pool_exhausted_v1` · Đã cấp 150/150 địa chỉ DHCP. Thiết bị mới hết địa chỉ để nhận. |
| `INC-DNS-FAIL` | 3 | GP01 | `gp01_dns_all_resolvers_down_v1` · Đường IP thông, mất gói 0%, nhưng 0/3 DNS resolver đạt kiểm tra. |
| `INC-WAN-DOWN` | 2 | O07 | `o07_default_route_absent_v1` + `o07_upstream_unreachable_v1` · Link vật lý còn lên, mất tuyến mặc định và upstream mất 100% gói. |
| `INC-24G-COCHANNEL` | 3 | B06 | `channel_crowded_v1` · Kênh 6 có 9 BSS lân cận. B05 cùng kịch bản đọc mức sử dụng kênh 88%. |
| `INC-WEAK-SIGNAL` | 3 | B04 | `rssi_weak_v1` + `snr_low_v1` · Client còn kết nối, RSSI −82 dBm và SNR 12 dB. |
| `INC-BUFFERBLOAT` | 3 | G06 | `bufferbloat_v1` · Độ trễ hàng đợi 180 ms. G01 và G07 cùng kịch bản đọc RTT 195 ms, mất gói 1% và SQM tắt. |
| `INC-PPPOE-MTU` | 3 | GP02 | `gp02_pppoe_mss_not_clamped_v1` · PPPoE có MTU 1492 byte, chưa bật kẹp MSS và upstream vẫn thông. |
| `INC-CGNAT` | 3 | GP05 | `gp05_carrier_grade_nat_v1` · Địa chỉ WAN thuộc dải CGNAT 100.64.0.0/10. |
| `INC-DOUBLE-NAT` | 2 | GP05 | `gp05_double_nat_v1` · WAN nhận địa chỉ riêng và thiết bị phía trước là router. |
| `INC-IPV6-BROKEN` | 2 | GP03 | `gp03_ipv6_address_without_route_v1` · Client có IPv6 global, thiếu tuyến mặc định IPv6. |
| `INC-DFS-RADAR` | 2 | GP06 | `gp06_dfs_radar_detected_v1` · Radio 5 GHz ghi nhận 2 lần phát hiện radar và 2 lần đổi kênh trong một giờ. |
| `INC-STICKY-CLIENT` | 2 | GP07 | `gp07_sticky_to_weak_ap_v1` · AP đang dùng ở −82 dBm, có AP mạnh hơn 19 dB và client không chuyển AP. |
| `INC-OVERHEAT-REBOOT` | 3 | H05 | `replay_hot_with_reboots_v1` · Gateway ở 92 °C, ghi nhận 3 lần khởi động và 2 sự kiện crash. Hai phép đọc có proof riêng. |
| `INC-CAPACITY` | 2 | GP04 | `gp04_router_overloaded_v1` · CPU 96%, RAM 88%, 38 thiết bị online. |

Các Claim mô tả đúng mức quan sát của mô phỏng. Ví dụ WAN xác nhận mất tuyến và upstream. Việc quy lỗi cho cáp, modem hay ISP cần đo thêm. PPPoE xác nhận cấu hình MTU/MSS và chưa đo gói lớn hay ICMP. H05 xác nhận nhiệt cao cùng các sự kiện khởi động lại, chưa xác lập thứ tự hay quan hệ nhân quả. B04 xác nhận suy hao ở client. Vị trí router, vật cản cụ thể và tuổi phần cứng cần dữ liệu bổ sung.

## Ví dụ qua HTTP localhost

- Chọn **DNS không phân giải được** rồi hỏi “Có Wi-Fi mà không vào được web?”. GP01 trả `FAULT`, hai proof Core và số đo mất gói 0%, 0/3 resolver đạt. Web hiển thị **Cách xử lý** với đề xuất đổi hoặc thêm DNS dự phòng và link hướng dẫn. Nhãn hiển thị là **khuyến nghị — chưa thực hiện, áp dụng trên router của bạn**. [Nguồn TP-Link](https://www.tp-link.com/us/blog/2527/wi-fi-not-working-how-to-diagnose-and-fix-it-fast/)
- Chọn **Router quá nhiệt, tự khởi động lại** rồi hỏi “Router hay tự khởi động lại?”. H05 trả `FAULT`, nhiệt độ 92 °C, 3 lần khởi động và 2 crash qua hai lần đọc. Khuyến nghị đặt router nơi thoáng nằm trong phần hướng dẫn đi kèm. [Nguồn Glo Fiber](https://www.glofiber.com/en/blog/how-to-tell-if-your-router-is-bad)
- Trong kịch bản DNS, hỏi “Kiểm tra VPN”. J01 trả `HEALTHY` với hồ sơ tunnel đang hoạt động.

Khuyến nghị lấy từ `fix_vi` sau khi có verdict `FAULT` dùng ít nhất một proof của kịch bản. Điều kiện này được kiểm tra ở phía server và ở phần hiển thị. Test chặn nguồn sai target, sai scope, sai schema, quá hạn, timeout hoặc thiếu quyền. `incident_guidance` chỉ mang nội dung hiển thị và link tham khảo. Các Function đã chạy đều có rủi ro `READ_ONLY`.

## Phạm vi Skill và trạng thái dùng chung

Không có sự cố hay lượt tham chiếu Skill nào bị bỏ. Cả 50 lượt tham chiếu trong tệp nguồn đã có trong replay. Tám kịch bản dùng GP01–GP07 làm phép chẩn đoán chính vì các Skill nguồn chỉ đọc từng tín hiệu hoặc không phân biệt được hai nguyên nhân. Ví dụ F02 đo tình trạng resolver, GP01 kiểm tra thêm IP tới upstream. E05 chỉ có cờ nghi CGNAT, GP05 đọc loại địa chỉ WAN và trạng thái router phía trước để phân biệt CGNAT với NAT hai lớp. Các Skill nguồn còn lại dùng dữ liệu hiện hành của kịch bản hoặc dữ liệu bình thường tương ứng.

Mỗi kịch bản dùng một bộ ghi đè theo Function, chia sẻ số đo hiện hành giữa các Skill. Các mẫu lịch sử giữ thứ tự và khoảng cách thời gian. Ma trận chạy **1.582 lượt** qua Core trên **101 Skill được tính coverage + 7 GP + 5 iGate**, đạt đúng 1.479 `HEALTHY`, 33 `FAULT` và 70 `UNKNOWN`. Trong 70 lượt `UNKNOWN` có 56 lượt của bốn Skill iGate vốn chỉ xuất Claim quan sát và 14 lượt của các phép kiểm tra phụ thuộc sau.

- WAN mất tuyến khiến GP01/GP02 thiếu điều kiện upstream thông, K06 thấy trạng thái đổi giữa hai mẫu và L07/M06/SK04 không thỏa hợp đồng đầu vào.
- O02 có kết quả hỗn hợp ở ba ca nghẽn 2.4 GHz, sóng yếu và sticky client. O06 có độ trễ/jitter cao trong khi mất gói thấp ở ca bufferbloat. SK08 thấy nhiệt cao và lưu trữ bình thường ở ca quá nhiệt.
- J08 thấy dịch vụ bật nhưng chưa có kết nối ở ca CGNAT. L03 đọc hai gateway còn tới được ở ca NAT hai lớp. H04 có cảnh báo và không có lỗi hệ thống ở ca DFS. Các tổ hợp đó nằm ngoài Claim `HEALTHY`/`FAULT` hiện có của từng Skill.

## Pin và kiểm tra

Kết quả `.venv-graph/bin/python -m scripts.prepare_replay_sim_approval` đề xuất các pin sau cho `replay_sim`.

| Pin | SHA-256 |
|---|---|
| `incident_scenarios_digest` (mới) | `52e01c6f94ac66fed6204e5de3ce34e5251ef5230c130dfed4ccd3a3a1702ed5` |
| `incident_checks_digest` (GP01–GP07) | `0090eb755d076673e563813e8a682e3d2e0a776b535a0907cee1abe1ce05b8ad` |
| `igate_digest` (IG01–IG05) | `9883919316a93befe57fad38aae54472594faf112abf6071cd48242bfbb5557b` |

| Lệnh | Kết quả local |
|---|---|
| `.venv-graph/bin/python -m scripts.check_project` | PASS, 0 lỗi. |
| `.venv-graph/bin/python -m unittest discover -s tests` | 1.134 tổng, 1.129 pass, 0 fail, 5 skip, 390,346 giây. |
| `node scripts/check_chat_presentation.cjs` | PASS, gồm 4 huy hiệu replay, 14 lựa chọn sự cố và 3 ca hiển thị khuyến nghị. |
| `node scripts/check_skill_graph.cjs` | PASS, 97 bước force, 25 khung hình, 48 bước sau khi cập nhật và kiểm tra tương tác live/replay. |

HTTP localhost xác nhận `/api/config` công bố đủ 14 kịch bản và `/api/chat` trả 403 với cấu hình approval hiện tại. Kiểm thử replay dùng approval giả lập trong bộ nhớ. Web đã được kiểm tra qua HTTP và DOM trong Node. Phần cứng và trình duyệt tương tác chưa được nghiệm thu. Commit local theo yêu cầu nên chưa có URL CI.
