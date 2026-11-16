# Danh mục đầy đủ 120 Skills

**Đây là catalog đề xuất.** 8 Skill có trong Registry v0.1; 112 Skill mới chỉ là mục tiêu thiết kế.
Không có Function binding, lệnh thực thi hay quyền WRITE được cấp bởi danh mục này.

| Chỉ số | Giá trị |
|---|---:|
| Tổng Skill | 120 |
| Domain | 15 |
| EXISTING_V01 | 8 |
| PROPOSED | 112 |
| P0 / P1 / P2 | 36 / 50 / 34 |

## A — Identity & Inventory

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK01` | Xác định client đích | P0 | EXISTING_V01 | client / gateway |
| `A02` | Kiểm kê thiết bị trong mạng | P0 | PROPOSED | client / gateway |
| `A03` | Chuẩn hóa và gộp định danh thiết bị | P1 | PROPOSED | client / gateway |
| `A04` | Nhận diện hãng từ MAC/OUI | P2 | PROPOSED | client / gateway |
| `A05` | Phân loại loại thiết bị | P2 | PROPOSED | client / gateway |
| `A06` | Đối chiếu IP–MAC–hostname | P1 | PROPOSED | client / gateway |
| `A07` | Theo dõi vòng đời thiết bị | P2 | PROPOSED | client / gateway |
| `A08` | Theo dõi thiết bị gắn với AP | P0 | PROPOSED | client / gateway |

## B — Wi-Fi & RF

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK02` | Chẩn đoán kết nối Wi-Fi | P0 | EXISTING_V01 | client / AP |
| `B02` | Trạng thái radio và SSID | P0 | PROPOSED | client / AP |
| `B03` | Kiểm tra cấu hình SSID | P1 | PROPOSED | client / AP |
| `B04` | Đánh giá RSSI/SNR/chất lượng liên kết | P0 | PROPOSED | client / AP |
| `B05` | Theo dõi airtime và sử dụng kênh | P1 | PROPOSED | client / AP |
| `B06` | Phân tích nhiễu và trùng kênh | P1 | PROPOSED | client / AP |
| `B07` | Chẩn đoán roaming | P2 | PROPOSED | client / AP |
| `B08` | Chẩn đoán mesh/backhaul | P2 | PROPOSED | client / AP |

## C — Ethernet & Layer 2

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `C01` | Trạng thái cổng Ethernet | P0 | PROPOSED | gateway / network |
| `C02` | Lỗi RX/TX và tốc độ liên kết | P1 | PROPOSED | gateway / network |
| `C03` | Bảng MAC/FDB của switch | P1 | PROPOSED | gateway / network |
| `C04` | Sức khỏe bridge | P1 | PROPOSED | gateway / network |
| `C05` | Phân tích membership VLAN | P1 | PROPOSED | gateway / network |
| `C06` | Phát hiện dấu hiệu vòng lặp L2 | P2 | PROPOSED | gateway / network |
| `C07` | Kiểm tra STP/RSTP | P2 | PROPOSED | gateway / network |
| `C08` | Phát hiện bất tương thích MTU | P2 | PROPOSED | gateway / network |

## D — IP, DHCP & IPv6

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK03` | Chẩn đoán DHCP và IPv4 | P0 | EXISTING_V01 | client / gateway |
| `D02` | Theo dõi vùng cấp phát DHCP | P0 | PROPOSED | client / gateway |
| `D03` | Theo dõi vòng đời DHCP lease | P1 | PROPOSED | client / gateway |
| `D04` | Phát hiện xung đột địa chỉ IP | P0 | PROPOSED | client / gateway |
| `D05` | Phân tích ARP/neighbor cache | P1 | PROPOSED | client / gateway |
| `D06` | Chẩn đoán IPv6 RA/SLAAC | P1 | PROPOSED | client / gateway |
| `D07` | Chẩn đoán DHCPv6 | P2 | PROPOSED | client / gateway |
| `D08` | Xác minh subnet/prefix/gateway | P1 | PROPOSED | client / gateway |

## E — WAN & Internet

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK04` | Chẩn đoán kết nối WAN | P0 | EXISTING_V01 | gateway / network |
| `E02` | Theo dõi vật lý/link WAN | P0 | PROPOSED | gateway / network |
| `E03` | Xác minh default route WAN | P0 | PROPOSED | gateway / network |
| `E04` | Chẩn đoán PPPoE/DHCP upstream | P1 | PROPOSED | gateway / network |
| `E05` | Phát hiện NAT/CGNAT | P2 | PROPOSED | gateway / network |
| `E06` | Chẩn đoán multi-WAN/failover | P2 | PROPOSED | gateway / network |
| `E07` | Phân tích WAN chập chờn | P0 | PROPOSED | gateway / network |
| `E08` | Kiểm chứng reachability thượng nguồn | P0 | PROPOSED | gateway / network |

## F — DNS & Core Services

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK05` | Chẩn đoán phân giải DNS | P0 | EXISTING_V01 | gateway / network |
| `F02` | So sánh chất lượng DNS resolver | P1 | PROPOSED | gateway / network |
| `F03` | Theo dõi trạng thái DNS cache | P2 | PROPOSED | gateway / network |
| `F04` | Chẩn đoán split-horizon DNS | P2 | PROPOSED | gateway / network |
| `F05` | Kiểm tra DNS option từ DHCP | P1 | PROPOSED | gateway / network |
| `F06` | Kiểm tra trạng thái DNSSEC | P2 | PROPOSED | gateway / network |
| `F07` | Quan sát cấu hình DoT/DoH | P2 | PROPOSED | gateway / network |
| `F08` | Chẩn đoán đồng bộ giờ NTP | P1 | PROPOSED | gateway / network |

## G — Performance & QoS

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `G01` | Độ trễ và mất gói | P0 | PROPOSED | gateway / network |
| `G02` | Phân tích jitter | P1 | PROPOSED | gateway / network |
| `G03` | Đánh giá throughput có kiểm soát | P2 | PROPOSED | gateway / network |
| `G04` | Thống kê lưu lượng từng interface | P0 | PROPOSED | gateway / network |
| `G05` | Xác định điểm tiêu thụ băng thông | P1 | PROPOSED | gateway / network |
| `G06` | Phân tích bufferbloat | P2 | PROPOSED | gateway / network |
| `G07` | Kiểm tra chính sách QoS/SQM | P1 | PROPOSED | gateway / network |
| `G08` | Khoanh vùng tắc nghẽn | P1 | PROPOSED | gateway / network |

## H — Router/System Health

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK08` | Sức khỏe tài nguyên gateway | P0 | EXISTING_V01 | gateway / network |
| `H02` | Tình trạng dịch vụ và tiến trình | P0 | PROPOSED | gateway / network |
| `H03` | Theo dõi dung lượng và wear lưu trữ | P2 | PROPOSED | gateway / network |
| `H04` | Phân tích log kernel và hệ thống | P1 | PROPOSED | gateway / network |
| `H05` | Giám sát nhiệt độ thiết bị | P2 | PROPOSED | gateway / network |
| `H06` | Kiểm tra driver/interface | P2 | PROPOSED | gateway / network |
| `H07` | Phân tích reboot/crash | P1 | PROPOSED | gateway / network |
| `H08` | Đánh giá sẵn sàng cập nhật firmware | P2 | PROPOSED | gateway / network |

## I — Security & Segmentation

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `I01` | Kiểm tra chính sách firewall (READ) | P0 | PROPOSED | gateway / network |
| `I02` | Kiểm tra dịch vụ/cổng phơi lộ | P1 | PROPOSED | gateway / network |
| `I03` | Đánh giá guest/client isolation | P1 | PROPOSED | gateway / network |
| `I04` | Kiểm tra chuẩn mã hóa Wi-Fi | P1 | PROPOSED | gateway / network |
| `I05` | Kiểm tra cấu hình xác thực quản trị | P1 | PROPOSED | gateway / network |
| `I06` | Xác minh phân đoạn mạng/VLAN | P1 | PROPOSED | gateway / network |
| `I07` | Phát hiện bất thường client có giải thích | P2 | PROPOSED | gateway / network |
| `I08` | Kiểm toán tuân thủ cấu hình | P2 | PROPOSED | gateway / network |

## J — VPN & Remote Connectivity

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `J01` | Kiểm tra sức khỏe VPN tunnel | P1 | PROPOSED | gateway / network |
| `J02` | Xác minh định tuyến qua VPN | P1 | PROPOSED | gateway / network |
| `J03` | Phân tích dấu hiệu DNS leak | P2 | PROPOSED | gateway / network |
| `J04` | Kiểm tra reachability của VPN peer | P1 | PROPOSED | gateway / network |
| `J05` | Chẩn đoán VPN site-to-site | P2 | PROPOSED | gateway / network |
| `J06` | Kiểm tra IPv6 qua VPN | P2 | PROPOSED | gateway / network |
| `J07` | Chẩn đoán policy-based routing | P2 | PROPOSED | gateway / network |
| `J08` | Chẩn đoán truy cập từ xa | P2 | PROPOSED | gateway / network |

## K — History, Monitoring & Incidents

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `K01` | Lịch sử Verified Evidence | P0 | PROPOSED | time-series / incident |
| `K02` | Phân tích xu hướng theo thời gian | P1 | PROPOSED | time-series / incident |
| `K03` | Quy tắc tạo cảnh báo | P0 | PROPOSED | time-series / incident |
| `K04` | Chống cảnh báo trùng | P1 | PROPOSED | time-series / incident |
| `K05` | Dựng timeline sự cố | P1 | PROPOSED | time-series / incident |
| `K06` | Phát hiện khoảng mất kết nối | P0 | PROPOSED | time-series / incident |
| `K07` | Xác minh trạng thái phục hồi | P1 | PROPOSED | time-series / incident |
| `K08` | Chính sách TTL và lưu trữ lịch sử | P0 | PROPOSED | time-series / incident |

## L — Topology & Multi-Gateway

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `L01` | Khám phá topology theo dữ liệu quan sát | P1 | PROPOSED | network / multi-gateway |
| `L02` | Ánh xạ client–AP–router | P0 | PROPOSED | network / multi-gateway |
| `L03` | Ánh xạ uplink/gateway | P1 | PROPOSED | network / multi-gateway |
| `L04` | Truy vết đường đi của client | P1 | PROPOSED | network / multi-gateway |
| `L05` | Bản đồ subnet/VLAN | P1 | PROPOSED | network / multi-gateway |
| `L06` | Tổng hợp sức khỏe theo site | P2 | PROPOSED | network / multi-gateway |
| `L07` | So sánh nhiều gateway | P2 | PROPOSED | network / multi-gateway |
| `L08` | Ước lượng phạm vi ảnh hưởng sự cố | P1 | PROPOSED | network / multi-gateway |

## M — Evidence & Adaptive Diagnosis

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK09` | Tương quan và kiểm chứng bằng chứng | P0 | EXISTING_V01 | case / diagnosis |
| `M02` | Xếp hạng giả thuyết RCA | P0 | PROPOSED | case / diagnosis |
| `M03` | Nhận diện bằng chứng còn thiếu | P0 | PROPOSED | case / diagnosis |
| `M04` | Chọn phép đo bổ sung thích ứng | P0 | PROPOSED | case / diagnosis |
| `M05` | Phân biệt quan sát và nguyên nhân | P0 | PROPOSED | case / diagnosis |
| `M06` | Chẩn đoán đối chiếu nhiều nguồn | P1 | PROPOSED | case / diagnosis |
| `M07` | Liên kết sự cố nhiều thiết bị | P1 | PROPOSED | case / diagnosis |
| `M08` | Giải thích kết luận kèm evidence ID | P0 | PROPOSED | case / diagnosis |

## N — Change & Guided Remediation

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `SK13` | Áp dụng và xác minh cấu hình có phê duyệt | P2 | EXISTING_V01 | gateway / network |
| `N02` | Phân tích tác động trước thay đổi | P1 | PROPOSED | gateway / network |
| `N03` | Snapshot cấu hình (READ) | P1 | PROPOSED | gateway / network |
| `N04` | Phát hiện configuration drift | P1 | PROPOSED | gateway / network |
| `N05` | Theo dõi phê duyệt thay đổi | P2 | PROPOSED | gateway / network |
| `N06` | Lập kế hoạch dry-run | P2 | PROPOSED | gateway / network |
| `N07` | Xác minh rollback/readback | P2 | PROPOSED | gateway / network |
| `N08` | Hướng dẫn khắc phục không tự WRITE | P1 | PROPOSED | gateway / network |

## O — Composite Troubleshooting Skills

| ID | Skill | Ưu tiên | Trạng thái | Phạm vi |
|---|---|---|---|---|
| `O01` | Điều tra client có Wi-Fi nhưng mất Internet | P0 | PROPOSED | case / diagnosis |
| `O02` | Điều tra Wi-Fi chậm | P0 | PROPOSED | case / diagnosis |
| `O03` | Điều tra mạng chập chờn | P0 | PROPOSED | case / diagnosis |
| `O04` | Điều tra lỗi DNS theo thiết bị | P0 | PROPOSED | case / diagnosis |
| `O05` | Điều tra IoT/camera mất kết nối | P1 | PROPOSED | case / diagnosis |
| `O06` | Điều tra gọi video/VoIP giật | P1 | PROPOSED | case / diagnosis |
| `O07` | Điều tra mất Internet diện rộng | P1 | PROPOSED | case / diagnosis |
| `O08` | Điều tra bất thường nhiều client | P1 | PROPOSED | case / diagnosis |
