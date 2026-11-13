# FND-04 — Trusted Adapter Binding and Conformance Implementation Plan

**Goal:** Chọn một backend/Function/context từ startup configuration tin cậy, pin registry/Function/backend/target/environment, kiểm conformance READ bằng replay và laptop trước khi có runtime bridge.

**Architecture:** Binding declarations tách khỏi immutable registry artifact để tránh circular digest. Operator cung cấp approved binding digests riêng và backend objects từ Python; không dynamic import. Selection không thực thi I/O; harness sample/probe chỉ phục vụ conformance, không admit Facts/Claims hoặc bật capability. GraphRunner bridge vẫn ở FND-06.

**Tech Stack:** Python 3.12, JSON Schema, ToolResult hiện có, Linux socket/ioctl READ; không thêm dependency, shell command hay network probe.

**Spec:** [Foundation](../specs/2026-11-13-command-catalog-v02-design.md).

## Phạm vi

- Pin binding ID, registry content digest, metadata Function digest/exact version, backend ID/revision/source, scope/target/environment.
- Duyệt tách khỏi declaration: thiếu approved digest, backend chưa được startup cung cấp, duplicate Function assignment hoặc pins sai đều fail trước I/O. Không fallback/retry backend khác.
- Conformance: đúng quyền/target/env/args, probe lại mỗi lượt, ToolResult exact outputs/schema/source/identity/freshness/deadline. Errors không cấp execution.
- Replay provider dùng fixture tách biệt; Linux provider đọc identity/IPv4 của interface operator chọn. Không lấy signal % làm RSSI dBm.
- Laptop example catalog riêng với provenance `linux_client/`, port major version mới; không sửa replay catalog/v0.1 để giả dữ liệu live.
- Kernel READ không phải generic backend timeout cancellation: harness kiểm elapsed và backend chịu trách nhiệm bounded I/O; provider laptop không gọi external process/network.

## Các bước

- [x] Ghi baseline hashes, kiểm upstream v2 và tests trước thay đổi.
- [x] Schema/TargetContext/BindingSelection + negative tests cho approval/pins/context.
- [x] Conformance harness + ToolResult negative tests; không có v0.2 execution integration.
- [x] Replay và Linux READ providers; laptop example catalog/policy với exact versions/provenance.
- [x] Smoke replay; live conformance trên interface Wi-Fi laptop khi hỗ trợ, báo cáo không chứa IP/MAC/SSID/raw boot ID.
- [x] Review, full tests, frozen hashes, docs/TODO; commit/push v2 và GitHub CI.

[Hướng dẫn](../../ADAPTER_BINDINGS_V02.md) và [báo cáo local](../../reports/FND04_BINDINGS_CONFORMANCE_20261113.md).
