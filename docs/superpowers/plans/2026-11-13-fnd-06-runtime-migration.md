# FND-06 — Runtime migration Implementation Plan

**Goal:** Nạp catalog v0.2 đã pin từ trusted startup vào Core READ hiện có, giữ nguyên v0.1 và dữ liệu frozen.
**Architecture:** Compatibility view chỉ mô tả selected metadata, giữ risk READ_ONLY. Runtime riêng sở hữu binding/support probe leases gắn context/ACL, adapter kiểm result trước Core Verifier; mọi diagnostic call qua shared execution kernel. Không nhận artifact, backend hoặc capability từ HTTP/LLM. Không thay UI (FND-07).
**Tech Stack:** Python, dataclasses, JSON Schema và Core hiện có; không thêm dependency.
**Spec:** ../specs/2026-11-13-command-catalog-v02-design.md, gate FND-06; ../../contracts/catalog-v02/README.md.

## Constraints
- Một exact version/ID, READ_ONLY, IMPLEMENTED/VERIFIED; PROBE/WRITE/unknown format fail closed.
- Giữ Function.digest v0.1 và toàn bộ data/benchmarks. Catalog hash khác runtime contract hash.
- Không fallback sang legacy replay khi thiếu adapter v0.2; target/environment/ACL/backend được kiểm lại trước/sau call.
- Probe lease ngắn hạn không phải health/evidence; conformance không cấp capability. Trusted backend tự bound I/O; elapsed gate từ chối kết quả muộn.

## Tasks
- [x] Compatibility: `command_catalog/compatibility.py` compile Port/FunctionV02, selected Skills, read-only legacy view; pin toàn registry trong Function digest; explicit loader dispatch.
- [x] Runtime: `command_catalog/runtime.py` trusted construction, selected bindings, bounded support leases, Core snapshot producer, explicit adapter and shared-kernel run API.
- [x] Shared policy: thêm format v0.2 vào `CaseState.allowed` và `GraphRegistry.contract_allowed`, generic typed argument gate; giữ nguyên nhánh v0.1/legacy và chặn format lạ.
- [x] Tests `tests/catalog/test_runtime_v02.py`: replay through Core, dependency args, version/retry/TTL mapping, permission/target/env/probe loss/timeout/malformed response gates, digest mutation, checkpoint pin mismatch, added Function/backend không sửa Runner, snapshot availability.
- [x] Verify: focused tests, check_project, full unittest, replay smoke; hashes frozen và 17 v0.1 golden digests.
- [x] Review, docs/TODO/status/report, commit/push `v2`, CI exact commit.
