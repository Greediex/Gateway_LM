# FND-05 — Feature Registry and Target Availability Implementation Plan

**Goal:** Đăng ký Feature metadata dùng Catalog, bật/tắt từ trusted flags và tính READY/DEGRADED/UNAVAILABLE/DISABLED theo target/quyền/capability mà không cấp execution.

**Architecture:** Feature Registry pin selected registry/port versions và validate manifests; application availability nhận typed, short-lived Core capability snapshot bound registry/context/permissions/policy identity. Không đọc binding report thành runtime capability, không gọi backend/probe. Thiếu runtime bridge FND-06 thì mặc định unavailable. Tái sử dụng dependency witness để giữ dependencies và alternatives qua domain.

**Tech Stack:** Python 3.12, JSON Schema/unittest hiện có, không thêm dependency.

**Spec:** [Foundation design](../specs/2026-11-13-command-catalog-v02-design.md), GLM-04.

## Semantics

- Required/optional ports pin exact versions và scope, references phải có trong selected Catalog; manifest sai/ID trùng bị từ chối khi đăng ký.
- Flags ngoài manifest; thiếu flag mặc định DISABLED. Manifest chỉ READ permission, không cấp quyền/probe/binding/import.
- Thiếu required port khả dụng: UNAVAILABLE; đủ required nhưng thiếu optional: DEGRADED; đủ tất cả: READY. READY là khả năng đo, không phải health/fact/claim.
- Input/ORDER dependencies cũng cần capability/quyền; một alternative producer khả dụng có thể phục vụ port. Không lấy một witness bị chặn làm kết luận mọi alternative đều lỗi.
- Snapshot chỉ từ trusted Core service, không HTTP/JSON; kiểm registry digest, Function version/metadata digest, target/environment, exact permission set, policy_context_id và TTL tối đa 60s. Context policy bao gồm principal/ACL revision do Core quản lý.
- Chưa có Core bridge thì runtime snapshot mặc định None. FND-04 CONFORMANT report không được dùng thay snapshot.

## Steps

- [x] Baseline và hash v0.1.
- [x] Feature schema/Registry, strict manifest/flags file readers và examples replay/laptop.
- [x] Typed availability snapshot + per-target evaluator, dependency alternatives và fail-closed default.
- [x] Tests cho manifest/refs/flags, bốn trạng thái, quyền/target/env/version/digest/policy/TTL, indirect deps và conformance không cấp READY.
- [x] Review, full regression, docs/TODO; commit/push v2 và GitHub CI.

[Chuẩn chi tiết](../../FEATURE_REGISTRY_V02.md), [nghiệm thu local](../../reports/FND05_FEATURE_REGISTRY_20261113.md).
