# FND-03 — Catalog Validator and Builder Implementation Plan

**Goal:** Kiểm tra catalog theo version/reference, build artifact metadata deterministic có integrity digest, CLI validate/build/report và benchmark 10/100/1.000 synthetic.

**Architecture:** Loader đọc JSON bounded từ path operator; validator dùng Contract v0.2 và resolve refs; indexes tạo lịch dependency khả thi bằng producer witness, builder chọn exact versions và publish một artifact bằng atomic replace. Artifact không nạp vào GraphRunner, không cấp capability. Runtime bridge ở FND-06.

**Tech Stack:** Python 3.12 stdlib, jsonschema hiện có; không thêm dependency.

**Spec:** [Foundation design](../specs/2026-11-13-command-catalog-v02-design.md).

## Ranh giới chốt cho FND-03

- Source chỉ gồm functions/ports/skills READ metadata; workflow/binding format chưa có bị từ chối thay vì bỏ qua JSON không hiểu.
- Flat `<id>.json` của seed được giữ; version bổ sung dùng `<id>@<version>.json` cùng thư mục/domain, không trùng cặp ID/version.
- `config/catalog_policy.example.json` là vocabulary probe ID do operator chọn, chỉ kiểm tên tham chiếu, không chứng minh implementation/attestation hay tự chạy probe.
- `validate` kiểm mọi source contract/reference và dependency realizability; `build` còn kiểm một selected version/ID, đủ port/Skill/member Function, lifecycle và dependency cho chính selection đó.
- Alternative producers có thể tạo graph union có vòng nhưng vẫn có lịch khả thi; witness schedule dùng một producer đã sẵn sàng cho mỗi input. Vòng không có producer gốc hoặc ORDER cycle bị từ chối. Đây là lịch metadata, không phải runtime plan hay proof đã đo thành công.
- Artifact gồm selected records, indexes, policy/schema/source digests và content digest, `execution_enabled=false`; report kiểm lại integrity/refs/indexes từ policy tin cậy và luôn báo 0 target-verified executable Functions.
- Benchmark đo load/validate/build/read, discovery/metadata dependency closure và peak RSS theo process riêng; runtime compile/ACL execution chưa được benchmark khi chưa có bridge.

## Thực hiện

- [x] Ghi hash baseline và kiểm upstream `v2` không lệch.
- [x] Viết negative tests: duplicate JSON keys, nonfinite/size/path, duplicate IDs, unknown refs, scope/field mismatch, impossible dependency, invalid selection, tampered artifact, atomic failure.
- [x] `loader.py`: strict JSON, bounded source traversal, canonical bytes/digests.
- [x] `validator.py`: policy vocabulary, cross-reference/version/scope/schema, Skill membership và selected closure.
- [x] `indexes.py`: domain/skill/producers/consumers, deterministic witness schedule và bounded discovery/closure.
- [x] `builder.py`: metadata selection, manifest/content hash, atomic artifact publication và verified read/report.
- [x] `scripts/catalog.py`: CLI validate/build/report; `scripts/analysis/benchmark_catalog.py`: synthetic scale report.
- [x] Review, full regression, benchmark, frozen hashes, docs/TODO; commit/push v2 và GitHub CI.

Chuẩn chi tiết và ranh giới scope-local: [Catalog v0.2](../../CATALOG_V02.md). Kết quả local: [nghiệm thu](../../reports/FND03_CATALOG_BUILDER_20261113.md).
