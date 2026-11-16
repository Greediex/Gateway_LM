# Gateway LM — Todo

**Hiện tại: nhánh `v2`, Foundation FND-01…07 đã hoàn tất.** Backlog NEXT bên dưới lấy từ bảng người dùng gửi sau FND-07. Phần GLM và báo cáo khảo sát giữ lại để trace lịch sử từ commit `3fd196f`.

[Xem todo chi tiết, file liên quan, phụ thuộc và điều kiện nghiệm thu](docs/superpowers/plans/2026-11-13-gateway-lm-todo.md).

[Bản chuyển kế hoạch kiến trúc v2 sang laptop trước](docs/architecture/GATEWAY_LM_V2_LAPTOP_FIRST.md) — giữ kiến trúc module và ánh xạ 10 PR gốc sang backlog.

**Thứ tự mới theo yêu cầu Foundation:** chuẩn hóa Contract/Catalog trước khi mở rộng tính năng; Wi-Fi laptop là ca kiểm chứng đầu tiên sau nền tảng. [Thiết kế Foundation v0.2 để review](docs/superpowers/specs/2026-11-13-command-catalog-v02-design.md).

- [x] **FND-01:** Chuẩn hóa Function Contract v0.2, ID/version/ref, digest và test vectors — [chuẩn](docs/contracts/catalog-v02/README.md), [nghiệm thu](docs/reports/FND01_CONTRACT_V02_20261113.md).
- [x] **FND-02:** Catalog theo domain với tập READ nhỏ, giữ dữ liệu v0.1 — [catalog](catalog/README.md), [nghiệm thu](docs/reports/FND02_READ_SEED_CATALOG_20261113.md).
- [x] **FND-03:** Catalog Validator/Builder, deterministic artifact, CLI validate/build/report và benchmark synthetic — [hướng dẫn](docs/CATALOG_V02.md), [nghiệm thu](docs/reports/FND03_CATALOG_BUILDER_20261113.md).
- [x] **FND-04:** Trusted Adapter Binding và conformance; replay/laptop trước, OpenWrt sau — [hướng dẫn](docs/ADAPTER_BINDINGS_V02.md), [nghiệm thu](docs/reports/FND04_BINDINGS_CONFORMANCE_20261113.md).
- [x] **FND-05:** Feature Registry dùng Catalog và availability theo target (GLM-04) — [hướng dẫn](docs/FEATURE_REGISTRY_V02.md), [nghiệm thu](docs/reports/FND05_FEATURE_REGISTRY_20261113.md).
- [x] **FND-06:** Migration, compatibility view, policy v0.2 và regression v0.1.
- [x] **FND-07:** Connectivity/Wi-Fi laptop → verified snapshot → UI (GLM-03/05/06/07).

## Backlog tiếp theo — NEXT

[Roadmap chi tiết: dependency và điều kiện nghiệm thu](docs/NEXT_ROADMAP_V2.md).

- [ ] **P0 / NEXT-01:** Tích hợp RCA Agent hiện có với Core READ v0.2 và VerifiedSnapshot.
- [ ] **P0 / NEXT-02:** Mở rộng chẩn đoán thích ứng thay vì chỉ dùng quy tắc cố định.
- [ ] **P0 / NEXT-03:** Tích hợp LLM Goal Proposal vào luồng chẩn đoán với kiểm soát an toàn.
- [ ] **P0 / NEXT-04:** Hoàn thiện catalog Function Wi-Fi, Devices, DHCP.
- [ ] **P0 / NEXT-05:** Mở rộng OpenWrt Adapter hiện có để hỗ trợ catalog READ mới qua replay/mock.
- [ ] **P1 / NEXT-06:** Hỗ trợ chẩn đoán theo từng thiết bị và quan hệ Client–AP–Router.
- [ ] **P1 / NEXT-07:** Bổ sung History và lưu chuỗi Verified Evidence.
- [ ] **P1 / NEXT-08:** Phát triển Monitoring, Alerts và quản lý Incident.
- [ ] **P1 / NEXT-09:** Mở rộng Web UI cho RCA, Devices, History và Alerts.
- [ ] **P0 / NEXT-10:** Đánh giá độc lập LLM, Function Selection, RCA và latency bằng dữ liệu replay có nhãn.
- [ ] **P1 / NEXT-11:** Hoàn thiện giới hạn tài nguyên, timeout và xử lý lỗi Ubus.
- [ ] **Để sau / NEXT-12:** Nghiệm thu OpenWrt trên firmware thật.

**Bắt đầu:** NEXT-10 baseline/harness cùng NEXT-01; tiếp theo NEXT-02 → NEXT-03. Catalog/mock NEXT-04 → NEXT-05 có thể triển khai độc lập; phần transport NEXT-11 cần đi trước nghiệm thu adapter/firmware. Chưa có NEXT task nào được đánh dấu hoàn thành.

## GLM — đối chiếu lịch sử

Các task GLM bên dưới giữ mã cũ để tra cứu; không phải một luồng mở rộng chạy trước Foundation. GLM-01 là prerequisite baseline, sửa lỗi và kiểm thử thiết yếu vẫn được thực hiện.

- [ ] **P0 / GLM-01:** Thiết lập môi trường đúng lockfile, bootstrap upstream và xác lập regression baseline.
- [ ] **P1 / GLM-02:** Hardening CompositeAdapter và giới hạn I/O Ubus, tích hợp ZIP có chọn lọc.
- [x] **P0 / GLM-03:** Verified snapshot, provenance, scope và freshness.
- [x] **P0 / GLM-04:** Feature manifest, registry và availability (FND-05).
- [x] **P0 / GLM-05:** Connectivity phía laptop qua execution core; Gateway Health chờ backend router.
- [x] **P0 / GLM-06:** Đọc Wi-Fi thật từ laptop Linux, route/ping/DNS với client scope và evidence.
- [ ] **P1 / GLM-06R:** Firmware profile/conformance và nghiệm thu READ trên router ở giai đoạn sau.
- [x] **P1 / GLM-07:** Dashboard Tổng quan + Chẩn đoán, thể hiện evidence và dữ liệu thiếu.
- [ ] **P1 / GLM-08:** Wi-Fi, Devices, DHCP với client scope đúng.
- [ ] **P1 / GLM-09:** History/Alerts, dedup, freshness và giới hạn tổng tài nguyên.
- [ ] **P1 / GLM-10:** Benchmark độc lập cho diagnosis, LLM/retrieval và tài nguyên.
- [ ] **P2 / GLM-11:** Guided troubleshooting; WRITE chỉ sau acceptance firmware và phê duyệt riêng.
- [ ] **P3 / GLM-12:** Multi-gateway và Edge–Cloud có cách ly, consent, budget.

**Mốc sản phẩm Foundation đã đạt:** Linux laptop → Core → verified snapshot → UI ở FND-07. Windows giữ route/ping/DNS; router acceptance chưa thực hiện. Mở rộng sau Foundation theo NEXT bên trên.

**Ghi nhận khảo sát ban đầu (trước Foundation):** clone đúng nhánh, đọc và đối chiếu repo/ZIP/đề xuất, kiểm 17 checksum của overlay, chạy project check và traceability audit, lập backlog. Chưa áp dụng overlay hoặc sửa runtime.

**Kiểm chứng FND-01:** đã tạo `.venv-graph` đúng lockfile và bootstrap upstream có xác minh SHA. Full regression: **519 tests, 514 pass, 5 skip Windows, 0 fail/error**; 17 tests catalog mới pass. Project check PASS; 31 baseline file hashes và 17 digest v0.1 giữ nguyên. Hai replay smoke WAN/client có answer. Chưa có CI URL mới hoặc hardware acceptance. Lỗi thiếu upstream lúc khảo sát ban đầu đã được giải quyết trong môi trường venv.

Trạng thái các khả năng đã có: [TASK_STATUS](docs/TASK_STATUS.md). Không coi task trong backlog là đã được triển khai.

**Kiểm chứng FND-02:** 3 Function / 3 Port / 2 Skill, 24 catalog tests pass; toàn repo 526 tests: 521 pass, 5 Windows-only skip, 0 fail/error. Dữ liệu/benchmark v0.1 và 17 runtime digests giữ nguyên; chưa thêm executable binding.

**Kiểm chứng FND-03:** 43 catalog tests pass; full regression 545 tests: 540 pass, 5 Windows-only skip. Synthetic 10/100/1.000 đạt budget; 1.000 Function build 10,996s, peak RSS 57,34 MiB. Đây là metadata tooling; chưa có executable runtime v0.2.

**Kiểm chứng FND-04:** 17 adapter tests pass; full regression 562 tests: 557 pass, 5 Windows-only skip. Replay 3/3 và laptop live identity/IPv4 2/2 CONFORMANT; provider chưa đọc RSSI dBm. Không admit facts hoặc cấp runtime capability trước FND-06.

**Kiểm chứng FND-05:** 16 feature tests pass; full regression 578 tests: 573 pass, 5 Windows-only skip. Bốn trạng thái availability được kiểm bằng synthetic Core snapshots; preview thật UNAVAILABLE/RUNTIME_NOT_CONNECTED tới khi có FND-06, không lấy conformance làm capability.

**FND-06:** [Runtime migration](docs/RUNTIME_V02.md) và [local acceptance](docs/reports/FND06_RUNTIME_MIGRATION_20261113.md). Trusted v0.2 READ qua shared Core, scoped support leases, compatibility view và checkpoint pins; FND-07 laptop snapshot/UI đã hoàn tất ở gate tiếp theo.

**FND-07:** [Laptop live + verified snapshot + UI](docs/LAPTOP_NETWORK_V2.md), [local acceptance](docs/reports/FND07_LAPTOP_NETWORK_20261113.md). Linux profile 7 READ Functions; route thực và Wi-Fi tách biệt, snapshot TTL, router health unavailable. README cập nhật chạy/test v2.

**Skill expansion pack:** Đã import/review catalog thiết kế 120 Skill, 206 edges và 72 READ proposals riêng; [guide](docs/skill_expansion/README.md), [acceptance](docs/reports/SKILL_EXPANSION_INTEGRATION_20261113.md). Metadata/synthetic integration không hoàn thành NEXT-01…12 hoặc cấp hardware capability.
