# CLI tools — benchmarks, reports, audits

Tất cả CLI dưới đây chạy bằng `python -m` **từ thư mục repository**. Việc chuyển file không sửa logic benchmark hoặc fixture đã khóa. Không quy kết kết quả nghiên cứu cũ cho refactor mới.

## Benchmark và replay

| Trước cleanup | Sau cleanup |
| --- | --- |
| `python run_conversation_benchmark.py` | `python -m scripts.benchmarks.run_conversation_benchmark` |
| `python run_dynamic_benchmark.py` | `python -m scripts.benchmarks.run_dynamic_benchmark` |
| `python run_function_selection.py` | `python -m scripts.benchmarks.run_function_selection` |
| `python run_html_benchmark.py` | `python -m scripts.benchmarks.run_html_benchmark` |
| `python run_operations_replay.py` | `python -m scripts.benchmarks.run_operations_replay` |
| `python run_rag_benchmark.py` | `python -m scripts.benchmarks.run_rag_benchmark` |

## Phân tích và xác minh

| Trước cleanup | Sau cleanup |
| --- | --- |
| `python analyze_catalog.py` | `python -m scripts.analysis.analyze_catalog` |
| `python audit_html.py` | `python -m scripts.analysis.audit_html` |
| `python compare_interfaces.py` | `python -m scripts.analysis.compare_interfaces` |
| `python inspect_case.py` | `python -m scripts.analysis.inspect_case` |
| `python verify_run.py` | `python -m scripts.analysis.verify_run` |
| `python write_analysis.py` | `python -m scripts.analysis.write_analysis` |

Dữ liệu benchmark vẫn ở `benchmarks/`, frozen manifests được giữ nguyên, output vẫn ở `runs/` (đã gitignore). Các tài liệu nghiên cứu lịch sử có thể ghi tên lệnh cũ; đối chiếu bảng trên.

## Entry points còn ở root

- `setup_upstream.py`: bootstrap / SHA verification.
- `prepare_data.py`: sinh dữ liệu frozen cho baseline; đường dẫn `prepare_data.py` xuất hiện trong metadata `gateway_pilot/run.py` và `compare_interfaces.py`. Giữ nguyên đường dẫn và nội dung để bảo toàn khả năng đối chiếu run lịch sử.

## Smoke test

```bash
python -m unittest tests.graph_v3.test_script_layout -v
python -m scripts.check_project
python -m scripts.benchmarks.run_function_selection --help
python -m scripts.analysis.audit_html --help
```

## Catalog metadata v0.2 (FND-03)

`python -m scripts.catalog validate/build/report` kiểm và build READ metadata; xem [hướng dẫn](../docs/CATALOG_V02.md) cho arguments. `python -m scripts.analysis.benchmark_catalog --output runs/catalog-v02/scale.json` chạy synthetic 10/100/1,000 trên host Linux/macOS, không đo router/NPU hoặc cấp quyền chạy Function.
