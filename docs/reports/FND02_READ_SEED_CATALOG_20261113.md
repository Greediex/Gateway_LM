# FND-02 — Domain READ seed catalog: nghiệm thu local

Ngày 13/11/2026; nhánh `v2`; base commit `d0983fa41ab81a478871a806bdd43d2490215775`.

## Kết quả

[Catalog](../../catalog/README.md) gồm 3 Function READ_ONLY/PROPOSED trên các domain `clients`, `wifi`, `lan`, 3 Port và 2 Skill. Wi-Fi/IPv4 dùng chung identity port và connectivity Skill. [Selection mẫu](../../config/catalog_selection.example.json) pin exact versions; không được tự nạp vào runtime.

Nguồn thiết kế là ba Function có sẵn trong v0.1. Vì payload đóng và arguments bị thu hẹp, Function dùng version mới **4.0.0**, Port **2.0.0**; hai Skill mới namespaced **1.0.0**. Dữ liệu và contract runtime v0.1 giữ nguyên. Provenance seed vẫn `synthetic_replay/`; chưa có laptop/router binding hoặc executable capability mới. RSSI dBm không được thay bằng signal %.

Schema 0.2.0 bổ sung metadata `kind=skill` với exact port/function refs; completion_ports phải khớp produces cả ID/version. Không thêm quyền, WRITE set hay capability result. API chỉ kiểm document metadata cục bộ; không thêm generic catalog loader/validator/builder của FND-03.

## Kiểm tra thực tế

Môi trường `.venv-graph` Python 3.12.3 đã cài lockfile và pinned upstream từ FND-01.

| Check | Kết quả |
|---|---|
| Catalog suite trước thay đổi | 17 tests pass |
| Seed tests trước implementation | Fail do chưa có catalog/selection, được ghi trong red log |
| Seed tests sau implementation | 7 tests pass |
| Toàn bộ catalog tests | 24 tests pass |
| Full regression | 526 tests: 521 pass, 5 skip, 0 fail/error |
| Lý do 5 skip | Windows live tests yêu cầu Windows; host hiện tại là Linux |
| Compatibility | Hash toàn bộ 19 tracked data/benchmark files trước/sau khớp; golden registry hash và 17 runtime Function digests vẫn đạt |
| Review riêng | Không có finding cần sửa; reviewer chạy độc lập 24 catalog tests thành công |

Commands dùng từ repo root:

```bash
.venv-graph/bin/python -m unittest tests.catalog.test_seed_catalog -v
.venv-graph/bin/python -m unittest discover -s tests/catalog -v
.venv-graph/bin/python -m unittest discover -s tests -v
.venv-graph/bin/python -m scripts.check_project
```

Log local: `runs/fnd-02/{before.json,baseline-catalog.log,red.log,catalog.log,regression.log}`; thư mục bị Git ignore. Không sửa Router/Resolver/Runner/Answer, không cần chạy lại replay E2E cho thay đổi metadata này. Chưa có kết quả GitHub Actions tại thời điểm lập báo cáo local; kết quả hosted sau push được báo riêng, không suy từ test local. Không có hardware acceptance trong FND-02.

FND-02 hoàn tất ở phạm vi catalog metadata mẫu và tests; FND-03 tiếp tục parser chống duplicate keys, cross-catalog graph validation, deterministic builder/index và CLI.
