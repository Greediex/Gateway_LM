# FND-07 — Laptop Connectivity/Wi-Fi → verified snapshot → UI

**Goal:** Cho người dùng test Linux live trên v2, giữ Windows/replay và sửa README đúng trạng thái.
**Architecture:** Catalog laptop-network riêng pin typed READ contracts; backend Linux đọc NetworkManager không rescan, kernel route, bounded ping/DNS. Application gọi FND-06 Core, Snapshot chỉ lấy CaseState.fact còn hạn và recheck environment. Rules và UI dùng snapshot, không raw OS output.
**Spec:** ../specs/2026-11-13-command-catalog-v02-design.md FND-07; 2026-11-13-gateway-lm-todo.md GLM-03/05/06/07.

## Constraints / rulings
- Không thay data/benchmarks hoặc v0.1 digests; không WRITE/router acceptance.
- Máy hiện có Wi-Fi + Ethernet; Internet route thực đang đi Ethernet. Luôn ghi interface/source và không suy luận Internet Wi-Fi từ đường khác.
- Signal % khác RSSI dBm; link rate khác throughput. Missing/stale không healthy.
- API không nhận backend/permissions/commands/targets; local-only existing HTTP guard. Không thêm dependency.
- Ruling: reuse current UI and explicit `source_mode=live` Linux dispatch; Windows path unchanged. Dedicated laptop dashboard/API uses trusted application and refresh-on-click, no polling collector.

## Tasks
- [x] Linux provider + dedicated catalog/profile/contracts; parser/failure/route/resolver change tests.
- [x] Immutable verified snapshot, consumption freshness/environment gates; Connectivity/Wi-Fi results and Core trace; no direct adapter calls from rules.
- [x] Existing UI Linux live support and dashboard states/evidence/time/units; preserve Windows/replay.
- [x] HTTP integration/isolation tests, full suite/frozen checks, replay and real laptop acceptance, visual QA.
- [x] README v2 quickstart/test steps, docs/TODO/report; independent review, push v2, exact CI, start local server for user test.
