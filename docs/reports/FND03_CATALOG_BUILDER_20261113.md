# FND-03 — Catalog Validator/Builder: nghiệm thu local

Ngày 13/11/2026; nhánh `v2`; base commit `dd57f502ffb99ef89e2798476983fad880666273`.

## Thay đổi

- [Hướng dẫn và giới hạn](../CATALOG_V02.md): strict bounded JSON loader, reference/schema/scope/Skill validator, exact version selection, domain/port indexes và deterministic dependency witness.
- `builder.py`: artifact metadata tự chứa selected records, source/record/schema/policy/selection/content hashes; validate trước atomic replace, verified read/report.
- `python -m scripts.catalog validate/build/report`: API dành cho developer/operator, policy là vocabulary probe names, không tự cấp approval hoặc capability.
- `scripts.analysis.benchmark_catalog`: synthetic 10/100/1.000 Function, subprocess riêng và resource budgets.
- Output `execution_enabled:false`; không tạo `GraphRegistry` v0.2, không bind adapter hoặc sửa policy/Runner hiện hành. Runtime bridge vẫn là FND-06.

## Kiểm tra

| Check | Kết quả |
|---|---|
| Tests ban đầu trước implementation | Fail vì chưa có module loader/validator/builder; red log đã ghi |
| Tests mới FND-03 | 19 pass |
| Toàn bộ catalog tests | 43 pass |
| Full regression cuối | 545 tests: 540 pass, 5 skip, 0 fail/error |
| Lý do 5 skip | Windows live tests yêu cầu Windows; host hiện tại là Linux |
| Baseline | Toàn bộ 19 tracked data/benchmark hashes khớp; golden registry hash và 17 Function digests v0.1 vẫn pass |
| Reproducibility | Đảo thứ tự document vẫn cho artifact byte-identical; không mutate input |
| Publication failure | Validation/replace lỗi giữ artifact cũ và không để lại temp file |
| Integrity | Từ chối sửa nội dung, policy/schema digest, indexes và source counts kể cả khi rehash envelope |
| Review riêng | Sửa thiếu input-scope check theo profile scope-local; review lại 19 tests pass, không còn finding quan trọng |

Negative tests gồm duplicate JSON keys (kể cả nested), nonfinite/overflow, file size/Unicode, symlink/layout/domain sai, ID/version trùng, exact reference thiếu/sai, argument type/format/field/required mismatch, input/output scope mismatch, unknown probe IDs, WRITE, wrong Skill membership, impossible dependency/ORDER cycle, selected dependency thiếu và RETIRED. Tests cũng kiểm alternative producer có root không bị nhận nhầm là cycle, nhiều versions nhưng mỗi ID chỉ chọn một, cross-domain closure và output baseline được bảo vệ.

Các lệnh CLI validate/build/report đã chạy end-to-end trên seed. Không sửa Router/Resolver/Runner/Answer, nên không cần chạy lại replay assistant để chứng minh thay đổi metadata này.

## Scale trên host — synthetic metadata

[Bản JSON số đo](FND03_CATALOG_SCALE_20261113.json), protocol `catalog-scale/v1`, Linux x86_64/Python 3.12.3. Một fresh subprocess mỗi size, 25 warm discovery/closure samples; OS cache uncontrolled. Không dùng dữ liệu hardware hay model quality test.

| Functions | Validate (s) | Build (s) | Verified read (s) | Peak RSS (MiB) | Closure p95 (ms) |
|---:|---:|---:|---:|---:|---:|
| 10 | 0.039 | 0.135 | 0.037 | 24.14 | 0.005 |
| 100 | 0.358 | 1.070 | 0.365 | 26.99 | 0.028 |
| 1.000 | 3.478 | 10.996 | 3.687 | 57.34 | 0.187 |

Cả ba size đạt budget đã chốt trước chạy: validate/read ≤30s, build ≤60s, peak RSS ≤512 MiB, closure p95 ≤100ms. Dependency closure đúng chain qua domain. Runtime compile, model inference, NPU và device execution không được đo; target-verified executable count vẫn bằng 0.

## Dấu vết và giới hạn

Log/output local trong `runs/fnd-03/`: baseline hashes, red/catalog/regression logs, seed artifact và scale JSON; bị Git ignore. Chưa có kết quả GitHub CI tại thời điểm lập báo cáo local; URL/kết quả hosted sau push được báo riêng. Không có hardware acceptance.

Hashes bảo vệ integrity, không phải chữ ký hoặc operator approval. READ scope-local profile chưa có implicit cross-scope transforms, external input facts không có producer, workflow/binding JSON hay runtime plan recovery. FND-04/05/06 tiếp tục binding, Feature Registry và runtime compatibility. Không đánh dấu các gate đó hoàn thành bằng benchmark metadata.
