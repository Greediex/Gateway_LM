# Gateway LM — Todo

Backlog khảo sát ngày **13/11/2026**, dựa trên nhánh `refactor/gateway-lm-composite-adapter-pr01`, commit `3fd196f`, đề xuất kiến trúc và ZIP người dùng cung cấp.

[Xem todo chi tiết, file liên quan, phụ thuộc và điều kiện nghiệm thu](docs/superpowers/plans/2026-11-13-gateway-lm-todo.md).

[Bản chuyển kế hoạch kiến trúc v2 sang laptop trước](docs/architecture/GATEWAY_LM_V2_LAPTOP_FIRST.md) — giữ kiến trúc module và ánh xạ 10 PR gốc sang backlog.

**Thứ tự mới theo yêu cầu Foundation:** chuẩn hóa Contract/Catalog trước khi mở rộng tính năng; Wi-Fi laptop là ca kiểm chứng đầu tiên sau nền tảng. [Thiết kế Foundation v0.2 để review](docs/superpowers/specs/2026-11-13-command-catalog-v02-design.md).

- [x] **FND-01:** Chuẩn hóa Function Contract v0.2, ID/version/ref, digest và test vectors — [chuẩn](docs/contracts/catalog-v02/README.md), [nghiệm thu](docs/reports/FND01_CONTRACT_V02_20261113.md).
- [x] **FND-02:** Catalog theo domain với tập READ nhỏ, giữ dữ liệu v0.1 — [catalog](catalog/README.md), [nghiệm thu](docs/reports/FND02_READ_SEED_CATALOG_20261113.md).
- [x] **FND-03:** Catalog Validator/Builder, deterministic artifact, CLI validate/build/report và benchmark synthetic — [hướng dẫn](docs/CATALOG_V02.md), [nghiệm thu](docs/reports/FND03_CATALOG_BUILDER_20261113.md).
- [ ] **FND-04:** Trusted Adapter Binding và conformance; replay/laptop trước, OpenWrt sau.
- [ ] **FND-05:** Feature Registry dùng Catalog và availability theo target (GLM-04).
- [ ] **FND-06:** Migration, compatibility view, policy v0.2 và regression v0.1.
- [ ] **FND-07:** Connectivity/Wi-Fi laptop → verified snapshot → UI (GLM-03/05/06/07).

Các task GLM bên dưới giữ mã cũ để tra cứu; không phải một luồng mở rộng chạy trước Foundation. GLM-01 là prerequisite baseline, sửa lỗi và kiểm thử thiết yếu vẫn được thực hiện.

- [ ] **P0 / GLM-01:** Thiết lập môi trường đúng lockfile, bootstrap upstream và xác lập regression baseline.
- [ ] **P1 / GLM-02:** Hardening CompositeAdapter và giới hạn I/O Ubus, tích hợp ZIP có chọn lọc.
- [ ] **P0 / GLM-03:** Verified snapshot, provenance, scope và freshness.
- [ ] **P0 / GLM-04:** Feature manifest, registry và availability.
- [ ] **P0 / GLM-05:** Connectivity phía laptop qua execution core; Gateway Health chờ backend router.
- [ ] **P0 / GLM-06:** Đọc Wi-Fi thật từ laptop Linux, route/ping/DNS với client scope và evidence.
- [ ] **P1 / GLM-06R:** Firmware profile/conformance và nghiệm thu READ trên router ở giai đoạn sau.
- [ ] **P1 / GLM-07:** Dashboard Tổng quan + Chẩn đoán, thể hiện evidence và dữ liệu thiếu.
- [ ] **P1 / GLM-08:** Wi-Fi, Devices, DHCP với client scope đúng.
- [ ] **P1 / GLM-09:** History/Alerts, dedup, freshness và giới hạn tổng tài nguyên.
- [ ] **P1 / GLM-10:** Benchmark độc lập cho diagnosis, LLM/retrieval và tài nguyên.
- [ ] **P2 / GLM-11:** Guided troubleshooting; WRITE chỉ sau acceptance firmware và phê duyệt riêng.
- [ ] **P3 / GLM-12:** Multi-gateway và Edge–Cloud có cách ly, consent, budget.

**Mốc sản phẩm sau Foundation:** Wi-Fi/Internet thật từ laptop → Core → UI; không cần chờ OpenWrt. Repo có Windows route/ping/DNS nhưng chưa đọc Wi-Fi radio; Linux backend là việc cần bổ sung.

**Đã làm trong phiên này:** clone đúng nhánh, đọc và đối chiếu repo/ZIP/đề xuất, kiểm 17 checksum của overlay, chạy project check và traceability audit, lập backlog. Chưa áp dụng overlay hoặc sửa runtime.

**Kiểm chứng FND-01:** đã tạo `.venv-graph` đúng lockfile và bootstrap upstream có xác minh SHA. Full regression: **519 tests, 514 pass, 5 skip Windows, 0 fail/error**; 17 tests catalog mới pass. Project check PASS; 31 baseline file hashes và 17 digest v0.1 giữ nguyên. Hai replay smoke WAN/client có answer. Chưa có CI URL mới hoặc hardware acceptance. Lỗi thiếu upstream lúc khảo sát ban đầu đã được giải quyết trong môi trường venv.

Trạng thái các khả năng đã có: [TASK_STATUS](docs/TASK_STATUS.md). Không coi task trong backlog là đã được triển khai.

**Kiểm chứng FND-02:** 3 Function / 3 Port / 2 Skill, 24 catalog tests pass; toàn repo 526 tests: 521 pass, 5 Windows-only skip, 0 fail/error. Dữ liệu/benchmark v0.1 và 17 runtime digests giữ nguyên; chưa thêm executable binding.

**Kiểm chứng FND-03:** 43 catalog tests pass; full regression 545 tests: 540 pass, 5 Windows-only skip. Synthetic 10/100/1.000 đạt budget; 1.000 Function build 10,996s, peak RSS 57,34 MiB. Đây là metadata tooling; chưa có executable runtime v0.2.
