# Gateway LM v2 — Kiến trúc module, laptop trước

Ngày cập nhật: 13/11/2026. Đây là bản chuyển đề xuất kiến trúc người dùng gửi sang lộ trình dùng Wi-Fi laptop trước, theo điều chỉnh trực tiếp trong chat. Các mục bên dưới là thiết kế và công việc dự kiến, chưa phải chức năng đã triển khai.

Nguồn: `/home/nangtuan/.codex/attachments/c31114a2-3654-4c2f-9d40-1956584450a6/Pasted text.txt`. Đối chiếu checkout `3fd196f` trên nhánh `refactor/gateway-lm-composite-adapter-pr01`.

## 0. Bổ sung Foundation trước mốc laptop

Yêu cầu mới: **Modular Monolith + Versioned Function Catalog + Stable Graph Core + Verified Adapters + User-facing Features**. [Thiết kế Foundation v0.2](../superpowers/specs/2026-11-13-command-catalog-v02-design.md) bổ sung `command_catalog/` và `catalog/` vào cấu trúc đích, đặt Contract/Validator/Builder/Compatibility trước mở rộng feature. Loader v0.2 độc lập với baseline v0.1; không chia JSON rồi mặc định có thể dùng ngay.

Bảng 10 PR bên dưới vẫn là ánh xạ đề xuất cũ; thứ tự thực hiện mới theo FND-01 đến FND-07 trong thiết kế Foundation. Mốc laptop giữ nguyên vai trò ca nghiệm thu đầu tiên sau nền tảng; OpenWrt tiếp tục ở giai đoạn sau.

## 1. Kiến trúc giữ lại

Chọn Modular Monolith, Feature Modules, các adapter được cấu hình tin cậy và Shared Execution Core. Giữ `graph_v3`, CompositeAdapter, evidence verification, registry và quyền tập trung. AI hỗ trợ chọn mục tiêu và giải thích; mỗi feature có rule nghiệp vụ riêng, không cần thêm agent cho từng miền.

Luồng đầu tiên:

```text
Người dùng / Web
    → Application: diagnose_network
    → Connectivity / Wi-Fi Feature
    → Registry + Planner + shared execution kernel + GraphRunner
    → CompositeAdapter → Linux laptop adapter
    → EvidenceVerifier → CaseState facts
    → Snapshot → Feature diagnosis → Câu trả lời / UI
```

Khi tích hợp OpenWrt, thêm adapter, contract và capability đã kiểm chứng; feature tái sử dụng những port có cùng ý nghĩa/scope/schema. Chỉ các phép đo tương đương mới dùng chung contract. WAN phía router và đường Internet từ laptop là hai loại phép đo riêng.

## 2. Phạm vi các module

| Module trong đề xuất | Giai đoạn laptop | Giai đoạn router |
|---|---|---|
| Internet / Connectivity | IP, route và interface đang dùng; probe gateway/Internet, DNS từ laptop | WAN link/routes, gateway-side probes được firmware hỗ trợ |
| Wi-Fi | Association, SSID/BSSID, signal %, channel/frequency, link rate khi backend có | Telemetry AP/client, RSSI và channel utilization nếu có phép đo hợp lệ |
| Devices | Máy laptop hiện tại và các interface của nó | Danh sách client từ AP/router đã xác minh |
| Network Health | Tình trạng đường kết nối của laptop; host CPU/RAM chỉ khi cần và gắn nhãn laptop | Sức khỏe gateway, CPU/RAM/router services |
| AI Diagnostics | Giải thích kết quả từ laptop, chỉ ra dữ liệu còn thiếu | Kết hợp bằng chứng laptop/router khi có đúng quyền và scope |
| Monitoring / Alerts | Theo dõi chuỗi mẫu trên laptop, có timestamp và quota | Nhiều gateway với isolation và retention |
| Automation | Hướng dẫn xử lý dựa trên phép đo READ | WRITE riêng, sau acceptance firmware và cơ chế phê duyệt |
| Fleet / Edge AI | Chưa nằm trong mốc đầu | Triển khai sau khi có nhu cầu và phép đo độc lập |

CPU/RAM laptop không thay thế CPU/RAM router. Association không chứng minh Internet hoạt động; signal % giữ nguyên đơn vị, không tự chuyển thành dBm; link rate không được hiển thị thành tốc độ tải Internet. Probe phải ghi đúng interface/route, nhất là khi có Ethernet/VPN.

## 3. Cấu trúc bổ sung theo từng nhu cầu

```text
gateway_pilot/
  graph_v3/                 # core hiện có
  adapters/
    composite.py            # hiện có
    linux_wifi.py           # dự kiến: READ từ laptop Linux
    ubus_read.py            # hiện có; nghiệm thu router sau
    ubus_cli.py              # hiện có
    firmware/               # bổ sung khi triển khai router
  features/
    registry.py             # metadata và đăng ký feature tin cậy
    contracts.py            # cấu trúc kết quả diagnosis
    connectivity/           # logic đường kết nối, phân biệt client/gateway
    wifi/                   # logic association và metrics Wi-Fi
    devices/                # mở rộng sau
    gateway_health/         # chờ nguồn router
  observability/
    snapshot.py             # chỉ lấy verified, scoped, fresh facts
    telemetry.py            # bổ sung khi có chuỗi mẫu
    history.py
    alerts.py
  application/
    diagnose_network.py
    feature_availability.py
web_gateway/                # tái sử dụng Web/API hiện có
```

Đây là cấu trúc đích, chỉ tạo file khi task cần. Giữ entry point hiện có và Windows live route/ping/DNS. Không chuyển toàn bộ code chỉ để khớp sơ đồ. `network_ops/` mới nằm trong ZIP, chưa tồn tại trong checkout: chọn port mã hữu ích trực tiếp sang module đích; chỉ cần shim nếu thực sự đưa API cũ vào sử dụng.

## 4. Manifest và nguồn dữ liệu

Manifest vẫn khai báo feature ID/version, required/optional ports và READ permission. Contract cụ thể của các port laptop phải được chốt cùng registry/tests khi triển khai; không tái dùng ví dụ `wan.status` trong bản gốc để biểu diễn Wi-Fi laptop.

Availability được tính theo backend và target đang chọn: `READY`, `DEGRADED`, `UNAVAILABLE`, `DISABLED`. `READY` cho biết có thể thực hiện feature; trạng thái mạng phải dựa vào kết quả đo mới, không lấy availability làm healthy.

Adapter Linux dự kiến dùng NetworkManager/`nmcli` cho dữ liệu kết nối hiện tại; kiểm tra hỗ trợ trước khi quảng bá capability. Có binary chưa đủ để khẳng định Wi-Fi đang kết nối hoặc metric đọc được. Nếu cần dùng thêm `iw` cho metric khác, coi đó là capability tùy chọn có probe riêng. Không rescan hoặc đổi kết nối để đọc trạng thái hiện tại.

Raw output đi qua observation → verifier → facts; mọi snapshot cần provenance, target và freshness. Feature không import trực tiếp lệnh hệ điều hành; Web không nhận quyền, adapter hoặc command từ request.

## 5. Chuyển lộ trình 10 PR của bản gốc

Các số dưới đây là thứ tự đề xuất, chưa tạo PR trên GitHub. Mã GLM dẫn đến [backlog chi tiết](../superpowers/plans/2026-11-13-gateway-lm-todo.md).

| PR trong đề xuất | Nội dung sau chuyển | Todo tương ứng |
|---|---|---|
| 01 — ổn định Core/Composite | Dựng môi trường theo lockfile, bootstrap upstream, baseline regression; Ubus hardening trước mốc router | GLM-01; GLM-02 ở giai đoạn router |
| 02 — features và registry | Feature registry/flags/availability, phân biệt laptop và router | GLM-04 |
| 03 — tách diagnostics | Port rule Connectivity và Wi-Fi phù hợp cho laptop; gateway rules chờ backend | GLM-05, GLM-06; GLM-08 mở rộng |
| 04 — observability | Verified snapshot trước integration diagnostics; telemetry/history bổ sung sau | GLM-03; GLM-09 |
| 05 — Connectivity OpenWrt | Đổi thành Linux laptop Wi-Fi + route/probe/DNS thật | GLM-06 |
| 06 — Network Health Dashboard | Tổng quan Wi-Fi/Internet từ laptop, evidence và missing-data; router health unavailable | GLM-07 |
| 07 — Wi-Fi và Devices | Wi-Fi local đã đưa lên PR-05; giai đoạn này mở rộng Devices, client khác, DHCP khi có router | GLM-08, GLM-06R |
| 08 — Monitoring/History/Alerts | Theo dõi laptop trước; lưu mẫu có quota/freshness/dedup | GLM-09 |
| 09 — Guided troubleshooting/WRITE | READ guidance trước; WRITE sau acceptance firmware và quyết định policy riêng | GLM-11 |
| 10 — Multi-Gateway/Edge AI | Giữ giai đoạn sau, có isolation/consent/budget và benchmark | GLM-12 |

Đây là bảng ánh xạ nội dung, không ép thứ tự số PR thành dependency: snapshot GLM-03 phải có trước diagnosis integration; adapter laptop có thể phát triển song song về mặt kỹ thuật nhưng acceptance end-to-end cần đủ Core, facts và feature boundary. Đánh giá độc lập GLM-10 chạy sau khi có luồng đo, trước các tuyên bố chất lượng sản phẩm.

## 6. Mốc demo đầu tiên

Người dùng hỏi: **“Wi-Fi laptop này có vấn đề gì?”**

Ứng dụng đọc trạng thái kết nối Wi-Fi hiện tại, metric được hỗ trợ, route thực dùng, thử gateway/Internet/DNS trong budget, rồi trả kết quả gồm bằng chứng, thời điểm đo và bước kiểm tra tiếp. Khi thiếu dữ liệu hoặc đường probe qua interface khác, hiển thị rõ phạm vi kết luận. Câu hỏi về điện thoại khác hoặc CPU/RAM router trả giới hạn capability thay vì dùng số liệu laptop để thay thế.

Điều kiện nghiệm thu:

- [ ] Baseline theo lockfile và upstream hash hợp lệ; full regression không fail/error, skip được giải thích.
- [ ] Registered READ Functions thực thi qua shared kernel/GraphRunner/Verifier.
- [ ] Linux live acceptance đọc được dữ liệu từ laptop thật, ghi OS/backend/interface và evidence trace.
- [ ] Test disconnected/radio-off, thiếu metric, nhiều interface/VPN, route đổi, timeout, stale và malformed payload.
- [ ] UI phân biệt live/replay, đơn vị signal/link rate, availability và trạng thái phép đo; thiếu kiểm tra không hiện healthy.

Sau mốc này mới mở rộng router bằng GLM-06R. Toàn bộ tiêu chí firmware/NPU tiếp tục được đánh giá bằng phép đo trên thiết bị tương ứng.
