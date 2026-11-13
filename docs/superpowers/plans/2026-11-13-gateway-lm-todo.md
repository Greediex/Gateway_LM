# Gateway LM — Todo và lộ trình phát triển

> Khi triển khai: dùng skill `executing-plans` để làm từng task với kiểm tra sau mỗi bước. Tài liệu này là backlog đề xuất theo yêu cầu lập todo, chưa phải quyết định triển khai toàn bộ kiến trúc hay cho phép vận hành router.

**Mục tiêu cập nhật:** Trước mắt tạo luồng READ Wi-Fi/Internet thật từ laptop Linux đang chạy Gateway LM, có evidence và UI; tích hợp router OpenWrt ở giai đoạn sau. Quyết định này theo điều chỉnh trực tiếp của người dùng ngày 13/11/2026.

**Kiến trúc đề xuất:** Giữ `graph_v3` làm execution core; bổ sung feature theo từng nhu cầu, observability dùng verified facts, application layer mỏng. Feature không gọi thiết bị trực tiếp; tránh di chuyển code hàng loạt.

**Công nghệ hiện có:** Python 3.12, unittest, JSON Schema, Graph v3/v4, CompositeAdapter, Ubus transport, Web HTTP/JS; LLM/retrieval là tùy chọn.

**Ngày khảo sát:** 13/11/2026. **Nhánh:** `refactor/gateway-lm-composite-adapter-pr01`. **Commit gốc:** `3fd196fd47b492cb3036b4db100d654d9461c002`.

[Kiến trúc v2 đã điều chỉnh và bảng chuyển 10 PR gốc](../../architecture/GATEWAY_LM_V2_LAPTOP_FIRST.md).

## 0. Điều chỉnh mới: Foundation trước feature expansion

Theo yêu cầu mới trong tài liệu ngày 13/11/2026, xây lớp quản lý lệnh có version trước khi mở rộng tính năng. [Thiết kế và bảy gate Foundation](../specs/2026-11-13-command-catalog-v02-design.md) là tài liệu ưu tiên cho thứ tự triển khai; các task GLM bên dưới giữ mã để tra cứu.

`GLM-01 → FND-01 Contract → FND-02 catalog mẫu → FND-03 validator/builder → FND-04 binding/conformance → FND-05 Feature Registry → FND-06 migration/regression → FND-07 laptop demo`.

FND-01 phải chốt schema và compatibility vectors trước viết loader. FND-07 gom GLM-03/05/06/07 làm ca kiểm chứng; GLM-04 thuộc FND-05. Router vẫn ở GLM-06R sau mốc laptop. Không tạo hàng loạt Function trong giai đoạn Foundation; bugfix và tests thiết yếu không bị đóng băng.

## 1. Phạm vi và nguồn

Yêu cầu ban đầu: clone nhánh và lập todo; sau đó chuyển sang laptop-first và bổ sung Foundation theo tài liệu yêu cầu mới. Hướng dẫn cài đặt/thực thi trong ZIP vẫn là dữ liệu tham khảo; tài liệu mới được dùng làm yêu cầu điều chỉnh thiết kế/lộ trình. Chưa cài overlay, sửa runtime, truy cập router, commit hoặc push.

Nguồn đối chiếu:

- Repo: `README.md`, `AGENTS.md`, `docs/DEVELOPER_GUIDE.md`, `docs/TASK_STATUS.md`, `docs/RUNTIME_STAGES.md`, CI và mã adapter/test hiện tại.
- Đề xuất kiến trúc người dùng gửi: `/home/nangtuan/.codex/attachments/c6801550-ac2d-48f8-9459-ed2349a0a65e/Pasted text.txt`.
- Overlay: `/home/nangtuan/Downloads/gateway_lm_expansion_overlay.zip`; SHA-256 `af2fd260b0faf0bb1c602853763d37a8f77d90c7a37ee96945fdf752a8267b78`. Đã kiểm tra khớp cả 17 mục trong `SHA256SUMS.txt`; checksum không chứng minh chất lượng hay khả năng chạy trên firmware.

Ràng buộc dùng chung: READ mặc định; quyền WRITE do Core kiểm soát; không thực thi lệnh từ LLM; giữ ACL/scope/target/schema/TTL/budget, frozen fixtures và upstream hash. Manifest không cấp capability. `PROBE_OK` ở adapter và `PROBED_OK` ở contract là hai lớp cần kiểm tra đúng. Replay/host/mock không phải bằng chứng router/NPU.

## 2. Hiện trạng đã kiểm tra

| Hạng mục | Hiện trạng | Hệ quả cho todo |
|---|---|---|
| Router/Planner/Runner/Verifier, shared READY kernel | Có mã và regression tests | Giữ, kiểm thử trước khi tích hợp |
| CompositeAdapter, UbusReadAdapter, Ubus CLI | Có trong repo | Hardening và nghiệm thu, không viết lại từ đầu |
| GoalAgent, RCAAgent, TaskRuntime | Có pilot; policy legacy vẫn riêng | Tái sử dụng; measurement đạt không đồng nghĩa RCA/repair |
| Checkpoint, journal, WRITE transaction/outbox, HTTPS delegation | Có mã/test, giới hạn pilot | Việc còn lại chủ yếu integration/acceptance |
| Registry | Audit mới: 8 skills, 17 Functions, 10/270 requirements được ánh xạ, 0 requirement firmware-verified | Không gọi 270 requirements là 270 Functions chạy được |
| `features/`, `observability/`, `application/`, `network_ops/` | Chưa có các thư mục này trong checkout | ZIP là nguồn ứng viên, chưa tích hợp |
| UI | Có `web_gateway/server.py` và `static/` | Phát triển tiếp UI có sẵn |
| Firmware/NPU | Chưa có nghiệm thu trong công việc này | Cần acceptance riêng với thiết bị xác định |

### Baseline local của phiên khảo sát

- Python 3.12.3; môi trường hệ thống có numpy 1.26.4 và jsonschema 4.10.3, thiếu langgraph; chưa thiết lập môi trường theo lockfile.
- `python3 -m scripts.check_project`: **PASS**.
- `python3 -m unittest discover -s tests -v`: **416 tests, 316 errors, 7 skipped**. Trong log: 314 lỗi thiếu pinned SkillDAG và 2 lỗi thiếu pinned GoS. Chưa chạy `setup_upstream.py`; chưa thể kết luận suite pass hay coi các lỗi này là regression sản phẩm.
- `python3 -m scripts.analysis.audit_requirement_traceability --output runs/planning-20261113/traceability.json`: chạy thành công, số liệu ở bảng trên.
- Log local nằm ở `runs/planning-20261113/`; thư mục này bị Git ignore. Chưa chạy GitHub Actions, không có CI run URL mới.

### Cập nhật sau FND-01

Đã thiết lập venv theo lockfile và bootstrap pinned upstream đúng SHA. Full regression cuối: 519 tests, 514 pass, 5 Windows-only skip, 0 fail/error; catalog suite 17 tests pass. Lỗi thiếu dependency/upstream trong baseline khảo sát cũ đã được giải quyết trong venv. [Chuẩn FND-01](../../contracts/catalog-v02/README.md) và [báo cáo nghiệm thu](../../reports/FND01_CONTRACT_V02_20261113.md). GLM-01 còn các benchmark/CI steps riêng ngoài phạm vi FND-01.

## 3. Todo theo thứ tự thực hiện

P0 = nền tảng và luồng READ đầu tiên từ laptop; P1 = giá trị người dùng sau nền tảng; P2/P3 = mở rộng có điều kiện. Các mã GLM dưới đây là đề xuất phân chia công việc, không phải số PR đã tạo.

### GLM-01 — P0: Thiết lập baseline tái lập được

**Phụ thuộc:** Không. **File liên quan:** `requirements-react.txt`, `requirements-graph-v3.lock`, `setup_upstream.py`, `.github/workflows/composite-adapter-regression.yml`.

- [ ] Tạo `.venv-graph` bằng Python 3.12; cài đúng requirements, không thay phiên bản thư viện hệ thống.
- [ ] Chạy bootstrap GoS/SkillDAG, xác minh đúng commit/SHA; nếu lỗi dừng và ghi nguyên nhân, không sửa hash cho qua.
- [ ] Chạy project check, full regression, hai CLI replay WAN/client và benchmark smoke theo CI.
- [ ] Lưu commit, Python/dependency versions, số pass/fail/skip và lý do skip; gắn CI URL khi thực sự chạy CI.

**Nghiệm thu:** Môi trường đúng dependency, upstream hash hợp lệ, full suite không fail/error; mọi skip được giải thích. Baseline chỉ chứng minh trên host/replay.

### GLM-02 — P1 (trước OpenWrt): Tích hợp hardening adapter có chọn lọc

**Phụ thuộc:** GLM-01. **Sửa:** `gateway_pilot/adapters/composite.py`, `gateway_pilot/adapters/ubus_cli.py`, `tests/graph_v3/test_composite_adapter.py`, `tests/graph_v3/test_real_integration_boundaries.py`. **Thêm dự kiến:** `tests/graph_v3/test_ubus_transport_limits.py`.

- [ ] Review diff hai adapter trong ZIP; port từng thay đổi, không chép đè toàn bộ overlay.
- [ ] Composite probe phải trả unavailable khi backend ném `KeyError`/`TypeError`; backend lỗi không làm Function chưa được gán trở nên khả dụng; lỗi call được chuẩn hóa.
- [ ] Giới hạn stdout/stderr ngay khi đọc, deadline monotonic, dọn process/pipe; kiểm UTF-8, JSON và exit code.
- [ ] Cập nhật test đang mock `subprocess.run` nếu chuyển sang `Popen`; thêm process giả tạo stdout lớn, stderr lớn, treo, UTF-8 lỗi và JSON lỗi.
- [ ] Đo giới hạn thời gian/bộ nhớ với output lớn trên host; chạy lại regression.

**Nghiệm thu:** Không buffer vô hạn; vượt giới hạn/timeout phải bị chặn; lỗi backend không cấp quyền; suite cũ vẫn kiểm đúng hành vi. Code hiện tại kiểm `max_output` sau `capture_output=True`, nên đây là khoảng trống cụ thể.

### GLM-03 — P0: Verified snapshot và ranh giới thời gian

**Phụ thuộc:** GLM-01. **Thêm dự kiến:** `gateway_pilot/observability/{__init__,snapshot}.py`, `tests/observability/{__init__,test_snapshot}.py`. **Đối chiếu:** `graph_v3/state.py`, `verification.py`, `checkpoint.py`; nguồn ứng viên `network_ops/snapshot.py` trong ZIP.

- [x] Chỉ lấy fact từ `CaseState.fact()`; lưu evidence ID, source, scope, target, thời gian, thông tin freshness cần thiết.
- [x] Loại fact stale/sai target/sai provenance; replay chỉ bật bằng cấu hình test rõ ràng.
- [x] Quy định snapshot còn dùng được đến khi nào; kiểm tra lại freshness khi tiêu thụ snapshot giữ lâu, thay vì chỉ khi tạo.
- [x] Tránh mutation của giá trị lồng bên trong làm thay đổi snapshot đã phát hành; kiểm thử dữ liệu thiếu và dữ liệu bị sửa sau tạo.

**Nghiệm thu:** Raw JSON/file offline không trở thành verified fact; snapshot quá hạn không tạo kết luận healthy; test gateway/client tách biệt.

### GLM-04 — P0: Feature manifest và availability

**Phụ thuộc:** GLM-01; dùng GLM-03 cho các kết quả chẩn đoán sau đó. **Thêm dự kiến:** `gateway_pilot/features/{__init__,registry}.py`, `gateway_pilot/application/{__init__,feature_availability}.py`, `config/feature_flags.example.json`, `tests/features/{__init__,test_registry}.py`.

- [x] Khai báo feature ID/version, required/optional ports, READ permission, cấu hình bật/tắt bằng metadata tin cậy.
- [x] Tính `READY`, `DEGRADED`, `UNAVAILABLE`, `DISABLED` từ registry, adapter, capability, quyền và phạm vi; trả lý do cụ thể cho port thiếu/bị chặn.
- [x] Chốt rõ semantics: thiếu required port thì unavailable; thiếu optional port thì degraded; READY là khả năng thực hiện, không phải mạng đang khỏe.
- [x] Test ID trùng, port lạ, schema lỗi, thiếu quyền, probe fail, feature tắt; không dynamic import hay tự phê duyệt probe.

**Nghiệm thu:** Manifest không thay đổi ACL/capability; trạng thái UI phản ánh đúng backend thực sự dùng được.

### GLM-05 — P0: Connectivity phía laptop qua Core; Gateway Health chờ router

**Phụ thuộc:** GLM-03, GLM-04. **Thêm dự kiến:** `gateway_pilot/features/connectivity/{__init__,manifest.json,service.py,diagnostics.py,explanations.py}`, `features/gateway_health/` với cấu trúc tương ứng, `gateway_pilot/application/diagnose_network.py`, tests trong `tests/features/` và `tests/application/`.

- [x] Tái sử dụng rule phù hợp từ ZIP nhưng định nghĩa port client/laptop riêng cho route, probe và DNS; không gắn phép đo laptop vào port `wan.status` hay `system.resources` của gateway. Giữ diagnosis model dùng chung ở `features/contracts.py`.
- [x] Để Gateway Health CPU/RAM router ở trạng thái unavailable đến khi có backend router; CPU/RAM laptop nếu hiển thị phải ghi đúng thiết bị.
- [x] Service yêu cầu typed READ goals qua runtime hiện có; mọi execution đi qua `execute_ready_once` và `GraphRunner.step`.
- [x] Kết quả có status, code, evidence IDs, missing ports, lời giải thích và bước kiểm tra tiếp; không tự tạo causal claim.
- [x] Test laptop mất Wi-Fi, thiếu route, packet loss, DNS ambiguous, evidence thiếu/stale và happy path; rule CPU/RAM router vẫn có test riêng khi tích hợp router.
- [x] Chỉ thêm compatibility shim `network_ops` nếu thực sự nhập API đó để sử dụng; checkout hiện tại chưa có API này để phải duy trì.

**Nghiệm thu:** Có luồng request → Core → verified snapshot → diagnosis trên replay gắn nhãn rõ; không import trực tiếp Ubus trong feature, không gọi adapter tắt qua Core.

### GLM-06 — P0: Đọc Wi-Fi thật từ laptop Linux

**Phụ thuộc:** GLM-01, GLM-03, GLM-04, GLM-05. **Thêm dự kiến:** `gateway_pilot/adapters/linux_wifi.py`, `tests/adapters/test_linux_wifi.py`; contract/registry version mới cho client READ. **Đối chiếu/tái sử dụng:** `windows_live.py`, `live_intent.py`, `adapters/__init__.py`, `web_gateway/server.py`.

- [x] Kiểm tra interface Wi-Fi, NetworkManager và quyền đọc trên laptop. Môi trường khảo sát có `/usr/bin/nmcli` và `/usr/sbin/ip`, chưa thấy `iw`; việc có binary chưa chứng minh đang có kết nối Wi-Fi.
- [x] Đọc kết nối hiện tại bằng API/lệnh READ cố định: trạng thái association, SSID/BSSID, signal %, frequency/channel và link rate khi backend cung cấp. Giữ đơn vị gốc; signal % không tự đổi thành RSSI dBm. Không yêu cầu rescan hay thay đổi kết nối.
- [x] Đọc IP/default route và xác định interface thực dùng cho probe; khi Wi-Fi/Ethernet/VPN cùng tồn tại phải ghi rõ đường đo. Probe Internet đi qua Ethernet/VPN không chứng minh đường Wi-Fi hoạt động.
- [x] Thu latency/loss và DNS có timeout/budget; giữ target theo cấu hình tin cậy. Link rate không phải throughput Internet.
- [x] Đưa observation qua registered Function, shared execution kernel và Verifier; snapshot chấp nhận provenance Linux client đã cấu hình, scope/target là laptop. Không dựng fact trực tiếp từ output `nmcli`.
- [x] Cập nhật giới hạn `live` đang chỉ cho Windows ở Web/API và intent radio; giữ Windows route/ping/DNS hoạt động như cũ, chỉ quảng bá capability thực đã probe.
- [x] Test output có ký tự escape, thiếu metric, radio tắt, chưa associated, nhiều interface, route đổi giữa phép đo, timeout, JSON/schema lỗi và evidence stale.
- [x] Chạy live acceptance trên laptop, lưu OS/interface/backend version, thời gian và trace evidence; che định danh SSID/BSSID/IP khi tạo artifact chia sẻ.

**Nghiệm thu:** UI trả trạng thái Wi-Fi và kết quả kiểm tra Internet từ chính laptop với nguồn/đơn vị/thời gian chính xác; thiếu dữ liệu phải báo rõ. Không cần router credentials. Chưa có bảng client của AP, DHCP pool hay CPU/RAM router từ nguồn này.

### GLM-06R — P1 (giai đoạn router): Firmware profile, conformance và một gateway thật

**Phụ thuộc:** GLM-02, GLM-03, GLM-04, GLM-05; triển khai sau mốc laptop GLM-06. **Thêm dự kiến:** `gateway_pilot/adapters/firmware/{__init__,profiles,conformance}.py`, `tests/adapters/`; **sửa khi cần:** `adapters/ubus_read.py`, registry version mới và tài liệu `docs/OPENWRT_ADAPTER.md`.

- [ ] Review và chuyển firmware/conformance từ ZIP; profile phải do cấu hình tin cậy phê duyệt, ràng buộc đúng model/firmware/hash.
- [ ] Giải quyết rõ đường chuyển contract từ unverified sang firmware-approved; boolean trong JSON và schema pass không đủ chứng minh hỗ trợ thiết bị.
- [ ] Xác định normalization từ payload Ubus thực sang port schema; không giả định JSON native trùng schema chuẩn hóa.
- [ ] Trước vận hành: xác định board, firmware, đường quản trị, quyền READ, dung lượng/tài nguyên và recovery path; không tự chọn IP từ dự án khác.
- [ ] Bắt đầu với `wan.status`; sau đó route/system và phép thử WAN/DNS nếu backend đã được xác minh. Không ép mọi phép đo vào Ubus nếu firmware không có method phù hợp.
- [ ] Test profile sai firmware, mapping lạ, WRITE, schema sai, timeout, probe mất hỗ trợ; thu acceptance trace qua toàn bộ Core trên board.

**Nghiệm thu:** Mỗi Function được công nhận phải có firmware hash, mapping/normalization đã review, raw capture được bảo vệ, verified evidence và trace thực. Thiếu probe phải báo thiếu dữ liệu, không hiện xanh. Công việc hardware chỉ bắt đầu khi đã có thiết bị và phạm vi thao tác rõ.

### GLM-07 — P1: Dashboard Tổng quan và Chẩn đoán

**Phụ thuộc:** GLM-04, GLM-05; live mode chỉ sau GLM-06. **Sửa:** `web_gateway/server.py`, `web_gateway/static/{index.html,app.js,app.css}`, `tests/web/test_adapter.py`; **thêm dự kiến:** `tests/web/test_features.py`.

- [x] Hiển thị Wi-Fi laptop, Internet từ laptop, thời gian đo và feature availability; tách replay/Linux live/Windows live. Router health unavailable khi chưa có backend router.
- [x] Mỗi kết luận có evidence và hướng xử lý; phân biệt có lỗi, chưa đủ dữ liệu, chưa hỗ trợ và chưa chạy phép đo.
- [x] API dùng application service; không nhận adapter/profile/model path/quyền WRITE từ HTTP.
- [x] Test response/API isolation và kiểm trực quan các trạng thái loading, lỗi, thiếu dữ liệu, stale và thành công.

**Nghiệm thu:** Không hiện healthy khi required measurement chưa có; người dùng đọc được vấn đề và bước tiếp theo mà không cần hiểu GraphRunner.

### GLM-08 — P1: Wi-Fi, Devices và DHCP

**Phụ thuộc:** GLM-03 đến GLM-06 cho laptop; GLM-06R cho thiết bị khác và DHCP phía router. **Thêm dự kiến:** `gateway_pilot/features/wifi/`, `features/devices/`, `features/connectivity/dhcp.py`, tests tương ứng; mở rộng adapter/registry theo contract mới khi cần.

- [ ] Tái sử dụng rule association/DHCP từ ZIP; xác định client identity và scope trước mọi phép đo.
- [ ] Mở rộng contract/adapter để có client-scoped READ; UbusReadAdapter hiện chỉ nhận gateway-scoped, zero-input, single-output Functions.
- [ ] Wi-Fi của laptop đã thuộc P0/GLM-06; task này mở rộng thiết bị khác. Bổ sung RSSI/link rate/channel utilization chỉ khi backend cung cấp và đã xác minh; không dùng association để suy ra Wi-Fi tốt.
- [ ] Test nhầm client, client rời mạng, thiếu metric, địa chỉ thay đổi; thông tin thiết bị chỉ hiển thị theo quyền.

**Nghiệm thu:** Tách được sự cố gateway/client; dữ liệu Wi-Fi chưa hỗ trợ được trình bày rõ; không suy RSSI thành khoảng cách/XY.

### GLM-09 — P1: History và Alerts có giới hạn tài nguyên

**Phụ thuộc:** GLM-03, GLM-05; live acceptance cần GLM-06. **Thêm dự kiến:** `gateway_pilot/observability/{telemetry,history,alerts}.py`, `gateway_pilot/application/monitor_gateway.py`, `tests/observability/test_telemetry.py`.

- [ ] Review `FleetTelemetry` trong ZIP; dùng thời gian quan sát/freshness thực, không chỉ thời gian ingest.
- [ ] Bổ sung giới hạn tổng số gateway/series và eviction; `deque(maxlen)` hiện chỉ giới hạn từng series, chưa giới hạn số series.
- [ ] Chốt retention, storage quota, dedup, alert cooldown/recovery và hành vi restart.
- [ ] Test gửi lại evidence, snapshot cũ, ngắt dữ liệu, đảo thứ tự mẫu, gateway tách biệt và đạt quota.

**Nghiệm thu:** Mẫu trùng/cũ không tạo cảnh báo mới; giới hạn tổng RAM/storage đo được; alert là tín hiệu quan sát, không tự kích WRITE hoặc trở thành RCA.

### GLM-10 — P1: Đánh giá chẩn đoán và model độc lập

**Phụ thuộc:** GLM-05; đánh giá thực địa cần GLM-06/08. **Tái sử dụng:** `scripts/analysis/evaluate_goal_proposals.py`, `evaluate_retrieval.py`, `audit_requirement_traceability.py`, `scripts/hardware/measure_gateway.py`, `summarize_inference.py`.

- [ ] Tạo dataset mới versioned, tách dev/test theo incident/session/device phù hợp; không sửa frozen benchmark cũ.
- [ ] Đo chẩn đoán đúng/sai, unsupported claims, abstention/coverage, latency p50/p95, CPU/RAM; ghi denominator và execution mode.
- [ ] Chạy local LLM/embedding thật nếu chọn sử dụng; calibration chỉ trên dev, không gọi illustrative fixture là holdout.
- [ ] Chốt ngưỡng đạt trước khi mở test cuối; chỉ ghi NPU khi có runtime và phép đo board-backed.

**Nghiệm thu:** Báo cáo tái lập được theo commit/dataset/model/firmware; phân biệt chất lượng model, hiệu quả retrieval và kết quả hệ thống.

### GLM-11 — P2: Guided troubleshooting và WRITE được kiểm chứng

**Phụ thuộc:** GLM-06R, GLM-07, baseline router READ ổn định. **Tái sử dụng:** `graph_v3/change_transaction.py`, `write_outbox.py`, `tests/graph_v3/test_change_transaction.py`, `test_write_outbox.py`.

- [ ] Làm hướng dẫn READ trước; lập driver WRITE riêng cho một thao tác đã xác định và được phê duyệt.
- [ ] Kiểm preview, operator approval, nonce, firmware binding, snapshot, readback/rollback và mất kết nối giữa chừng.
- [ ] Khi outbox `IN_FLIGHT`, chỉ reconciliation bằng readback độc lập; không auto-repeat.
- [ ] Giữ controller tắt mặc định, không gọi từ Agent/Web/LLM. Nếu muốn mở UI WRITE phải có thiết kế và thay đổi policy được chấp thuận riêng, vì AGENTS hiện cấm đường này.

**Nghiệm thu:** Acceptance trên firmware và recovery path cụ thể; không dùng mock success để bật WRITE thật.

### GLM-12 — P3: Multi-gateway và Edge–Cloud

**Phụ thuộc:** GLM-06R, GLM-09, GLM-10. **Tái sử dụng:** `graph_v3/delegation.py`, `https_hypothesis.py`; mở rộng application/observability theo nhu cầu đã đo.

- [ ] Cách ly gateway identity, evidence, quota, quyền và lịch polling; kiểm retry/backoff cho READ.
- [ ] Chỉ bật provider từ cấu hình operator với consent/budget và aggregated verified telemetry.
- [ ] Benchmark lợi ích Edge/Cloud, latency và chi phí trước khi bổ sung service riêng.
- [ ] Test cross-gateway leakage, endpoint lạ/redirect, vượt budget, mất mạng; phản hồi Cloud luôn là hypothesis.

**Nghiệm thu:** Không có lẫn evidence giữa gateway, không gửi raw client/log, không nâng quyền từ Cloud; NPU/production chỉ ghi khi đã đo.

## 4. Đường găng GLM sau các gate Foundation

```text
GLM-01 → GLM-03 + GLM-04 → GLM-05 → GLM-06 (laptop) → GLM-07
                                            ↓          ↓
                                         GLM-09     GLM-10
GLM-02 + nền tảng READ → GLM-06R (router) → GLM-08 / GLM-11 / GLM-12
```

Mốc sản phẩm đầu sau Foundation: **đọc Wi-Fi/Internet thật từ laptop Linux và hiển thị qua Core/UI**. GLM-02 (Ubus hardening) và GLM-06R (firmware) không chặn mốc này. Wi-Fi local được đưa lên P0; thiết bị khác, DHCP server và sức khỏe router triển khai sau khi có backend tương ứng.

Các lệnh baseline (từ repo root, sau khi tạo venv):

```bash
python3.12 -m venv .venv-graph
.venv-graph/bin/python -m pip install -r requirements-react.txt
.venv-graph/bin/python setup_upstream.py
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m unittest discover -s tests -v
.venv-graph/bin/python -m gateway_pilot.assistant --fixture GLM-04-0 --request 'Check WAN' --trace
.venv-graph/bin/python -m gateway_pilot.assistant --fixture GLM-21-1 --request 'Laptop An có wifi nhưng không vào Internet' --trace
```

Mỗi task triển khai cần test contract và negative path cụ thể nêu ở trên, full regression và docs nhất quán. Thay Router/Planner/Runner/Answer cần replay smoke. Chỉ đánh dấu hoàn thành đúng phạm vi đã kiểm chứng; duy trì `docs/TASK_STATUS.md` cùng backlog, không ghi đè kết quả lịch sử.
