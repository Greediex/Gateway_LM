# FND-02 — Domain READ Seed Catalog Implementation Plan

**Goal:** Tách một tập READ nhỏ thành catalog theo domain, giữ nguyên v0.1 và chưa nạp runtime.

**Architecture:** Ba Function có sẵn làm nguồn thiết kế, version mới vì payload/arguments thu hẹp; hai Skill namespaced và ba Port dùng reference chính xác. Tests kiểm tĩnh seed, validator cục bộ FND-01 mở rộng thêm Skill metadata.

**Tech Stack:** JSON, Python 3.12, jsonschema/unittest hiện có.

**Spec:** [Foundation](../specs/2026-11-13-command-catalog-v02-design.md), [Catalog](../../../catalog/README.md).

## Các bước

- [x] Kiểm baseline local/upstream `v2`, ghi hash data/benchmark trước thay đổi.
- [x] Viết tests seed trước; ghi red vì chưa có catalog/selection.
- [x] Thêm `catalog/functions/{clients,wifi,lan}/`, ba Port và hai Skill, exact selection trong `config/`.
- [x] Bổ sung Skill metadata shape/completion-reference check, không quyền hay binding.
- [x] Viết tài liệu migration: Function 3.0.0 → 4.0.0, Port schema v1 → SemVer 2.0.0, nguồn replay, shared references.
- [x] Review, chạy full regression/project check, xác nhận hash v0.1 và digest giữ nguyên.
- [x] Cập nhật TODO/status, commit và push nhánh `v2` theo yêu cầu người dùng.

Nghiệm thu: đúng 3 Function READ_ONLY/PROPOSED trên 3 domain; 3 Port/2 Skill, shared identity và connectivity Skill; tất cả references/selection đúng version; không auto-approval/executable binding; full regression không fail/error, skip có lý do. FND-03 vẫn phụ trách loader/builder/graph validation tổng quát.
