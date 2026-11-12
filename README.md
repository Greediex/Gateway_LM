# Gateway LM — Network Operations & Intelligence

**Trạng thái:** pilot Gateway LM v0.1 (Graph v4), ưu tiên chẩn đoán dựa trên bằng chứng. Hiện có replay tổng hợp, chế độ đo một số chỉ số mạng từ Windows và thử nghiệm trợ lý Ollama cục bộ. **Chưa có OpenWrt Function được xác minh trên router thật; không phải agent triển khai sản phẩm hoặc hệ thống hỏi gì cũng làm được.**

> Nhánh `refactor/gateway-lm-composite-adapter-pr01` được dùng để dọn dẹp và cải tiến từng bước. Không merge trực tiếp vào `main`. Composite Adapter giúp gán Function cho nhiều backend, nhưng chưa triển khai Function OpenWrt.

## Bắt đầu nhanh

**Windows PowerShell (Python 3.12):**

```powershell
py -3.12 -m venv .venv-graph
.\.venv-graph\Scripts\python.exe -m pip install -r requirements-react.txt
.\.venv-graph\Scripts\python.exe setup_upstream.py
.\.venv-graph\Scripts\python.exe -m gateway_pilot.assistant --fixture GLM-04-0 --request "Check WAN" --trace
.\web_gateway\start_windows.ps1
```

**Ubuntu/Linux (Python 3.12):**

```bash
python3.12 -m venv .venv-graph
source .venv-graph/bin/activate
python -m pip install -r requirements-react.txt
python setup_upstream.py
python -m gateway_pilot.assistant --fixture GLM-04-0 --request "Check WAN" --trace
bash web_gateway/start_linux.sh
```

Web UI: `http://127.0.0.1:8765`. Lệnh `setup_upstream.py` lấy GoS/SkillDAG tại commit cố định và xác minh SHA-256; chạy lại sẽ xác minh checkout hiện có thay vì xóa thư mục upstream.

**Ví dụ client (replay):**

```bash
python -m gateway_pilot.assistant --fixture GLM-21-1 --request "Laptop An có wifi nhưng không vào Internet" --trace
```

Dữ liệu trong ví dụ là **fixture mô phỏng**. Trạng thái `PARTIAL`/`INCONCLUSIVE` có nghĩa là chưa đủ bằng chứng, không phải chẩn đoán đã hoàn tất.

## Kiểm thử

```bash
python -m scripts.check_project
python -m unittest discover -s tests -v
```

GitHub Actions chạy các bước trên và smoke test CLI ngay trên nhánh refactor: [CI workflow](.github/workflows/composite-adapter-regression.yml). Các test web chỉ dành cho Windows được skip trên Linux. Các báo cáo nghiên cứu cũ **không được cập nhật số liệu một cách hồi tố**.

## Bản đồ repository

| Đường dẫn | Vai trò |
| --- | --- |
| `gateway_pilot/assistant.py` | Entry point hội thoại và Answer Composer |
| `gateway_pilot/graph_v3/` | Routing/Planning/Execution/Verification stages; Contract, Registry, Retrieval, Compiler, Runner, Repair, State/Claims |
| `gateway_pilot/adapters/` | Backend boundary, Replay/Windows/OpenWrt skeleton, Composite Adapter |
| `web_gateway/` | HTTP server và giao diện thử nghiệm |
| `data/`, `benchmarks/` | Registry, fixture, bộ đánh giá và manifest đã khóa |
| `tests/` | Regression tests: `graph_v3/`, `web/` và baseline |
| `docs/` | Kiến trúc, protocol, Web UI, báo cáo lịch sử trong `reports/` |
| `scripts/` | Benchmark, phân tích và kiểm tra vệ sinh repository |

## Tài liệu quan trọng

- [Docs index — bắt đầu từ đây](docs/INDEX.md)
- [Các lệnh benchmark/analysis mới](scripts/README.md)
- [Developer guide: setup, test, bổ sung Function/Skill](docs/DEVELOPER_GUIDE.md)
- [Runtime stages (Routing → Planning → Execution → Verification)](docs/RUNTIME_STAGES.md)
- [Đối chiếu upstream và goal execution (opt-in)](docs/REFERENCE_IMPLEMENTATION.md)
- [Hybrid Semantic Retrieval (opt-in, local-only)](docs/SEMANTIC_RETRIEVAL.md)
- [Bảng trạng thái task còn thiếu / hoàn thành](docs/TASK_STATUS.md)
- [Quy tắc coding agent](AGENTS.md)
- [Web UI và chế độ đo](docs/WEB_UI.md)
- [Kết quả Graph v4 (ảnh chụp ngày 11/11/2026)](docs/GRAPH_V4_RESULT_VI.md)
- [Kiến trúc tổng thể v0.1 (HTML)](docs/architecture/gateway-lm-v0.1-kien-truc.html)
- [Nguồn paper, mức độ tích hợp và giấy phép](docs/PAPER_SOURCES.md)
- [Composite Adapter refactor](docs/ADAPTER_COMPOSITION.md)
- [README v0.1 đầy đủ trước cleanup — lưu trữ](docs/README_V01_DETAILS.md)

## Goal execution (mới, trên replay)

```bash
python -m gateway_pilot.graph_v3.goal_agent --fixture GLM-04-0 --request "Check WAN and memory" --goals wan.status system.resources --method bm25
```

Lệnh trên kiểm chứng **measurement goals đã đăng ký**, không suy ra root-cause diagnosis. Có thể gọi tương đương qua `POST /api/goals` (replay-only; xem [Web UI](docs/WEB_UI.md)). Mọi Function vẫn phải qua Registry/permission/capability/Verifier. Xem [reference alignment](docs/REFERENCE_IMPLEMENTATION.md).

## Những gì chưa hỗ trợ

- Chưa có OpenWrt firmware probe/adapter production được xác minh.
- Chưa có Task DAG tổng quát cho mọi yêu cầu mới, chưa có RCA trên dữ liệu mạng thật.
- Những nghiệp vụ WRITE (QoS, firewall, internet block) trong replay **không** cho phép suy ra khả năng thay đổi router thật.
- LLM là advisor tùy chọn; Function execution, policy, evidence và claim vẫn được kiểm soát bởi Core.

Đóng góp mới nên duy trì tương thích với API, schema và test hiện tại; tham khảo [AGENTS.md](AGENTS.md) và [Developer Guide](docs/DEVELOPER_GUIDE.md).

## Phân rã câu hỏi có nhiều mục tiêu (experimental)

Với Registry v0.1, ví dụ `python -m gateway_pilot.graph_v3.goal_agent --registry v01 --fixture GLM-04-0 --request "Kiểm tra trạng thái WAN và RAM" --method bm25`. Mỗi mệnh đề phải khớp một port đã đăng ký bằng `data/goal_aliases_v01.json`; mệnh đề thiếu rõ ràng hoặc có yêu cầu WRITE sẽ **không gọi Function nào**. [Các giới hạn](docs/TASK_STATUS.md).

## Evidence checkpoint (opt-in)

Có `EvidenceCheckpoint` HMAC-SHA256 để phục hồi **fact đọc còn hiệu lực** sau restart, không phục hồi lệnh đang chạy hay WRITE. Bật từ cấu hình Python tin cậy, không nhận khóa hoặc file path qua HTTP. Xem [Checkpoint guide](docs/CHECKPOINT.md).

## Ubus read-only integration (mock-only)

Có `UbusReadAdapter` hỗ trợ transport injection và Function mapping đã được xác minh từ firmware. Test hiện tại dùng transport giả; **chưa có mapping OpenWrt nào được probe trên board thật**. Xem [OpenWrt Adapter](docs/OPENWRT_ADAPTER.md).

## Hybrid Retrieval (opt-in, chưa đo chất lượng model)

Thêm phương thức `--method hybrid --semantic-model-dir /path/to/local-model` cho `gateway_pilot.graph_v3.goal_agent`. Phải cung cấp một model embedding tải sẵn tại máy; không tự download, không nhận đường dẫn từ HTTP, và không chạy NPU tự động. BM25/GoS vẫn là baseline. [Hướng dẫn và giới hạn](docs/SEMANTIC_RETRIEVAL.md).
