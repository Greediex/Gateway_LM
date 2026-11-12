# Developer Guide — Gateway LM

## 1. Nguyên tắc trước khi sửa

- Làm việc trên nhánh riêng, không tự merge vào `main`.
- Không xóa `data/`, `benchmarks/`, `contracts/golden/`, các báo cáo paper hoặc baseline chỉ vì không thuộc code chạy thường xuyên.
- `gateway_pilot/graph_v3` là runtime hiện hành; `gateway_pilot/core.py`, `run.py` còn được dùng làm baseline và compatibility.
- Không chuyển toàn bộ code sang package khác trong một commit.
- Tuân theo [AGENTS.md](../AGENTS.md) trước khi thay đổi Function, Adapter, Planner hoặc Claim.

## 2. Setup

Dùng Python 3.12 (cùng version GitHub Actions). Từ repo root:

```bash
python3.12 -m venv .venv-graph
source .venv-graph/bin/activate
python -m pip install -r requirements-react.txt
python setup_upstream.py
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv-graph
.\.venv-graph\Scripts\python.exe -m pip install -r requirements-react.txt
.\.venv-graph\Scripts\python.exe setup_upstream.py
```

`setup_upstream.py` clone GoS/SkillDAG đúng commit, rồi kiểm SHA-256. Có thể gọi lại để **xác minh** checkout hiện có; nếu checkout lệch commit, script dừng và không tự xóa/sửa upstream.

## 3. Tổ chức code

```text
gateway_pilot/
  assistant.py, turn_router.py, answer.py   # interaction + output
  graph_v3/
    routing.py, planning_stage.py          # Contract 0 selection → typed DAG
    execution.py, verification.py          # adapter observations → verified evidence
    registry_v01.py, graphs.py, resolver.py  # catalog/retrieval
    planner.py, runner.py, repair.py         # planning/execution
    state.py, claims.py, contracts.py        # verified state/claims
    upstream.py, skilldag.py                 # pinned upstream integration
  adapters/                                 # typed Function adapters
web_gateway/                                # web UI
  tests/graph_v3/, tests/web/               # regression suites
data/ + benchmarks/                         # frozen test data
docs/contracts/                             # machine-readable contracts
scripts/benchmarks/                         # benchmark entry points
scripts/analysis/                           # analysis / audit tools
```

Điểm bắt đầu hợp lý khi mở rộng Function: [Adapter composition](ADAPTER_COMPOSITION.md), `registry_v01.py`, `tests/graph_v3/test_registry_v01.py`.

## 4. Thêm Function/Adapter đúng cách

1. Khai báo Function Contract và typed input/output. Không dùng tên Function làm logic ngầm cho schema.
2. Xác định scope, precondition, permission, risk, capability probe, verifier và TTL.
3. Viết adapter đã được allowlist và chỉ quảng bá `PROBE_OK` sau khi xác minh thực.
4. Chạy conformance tests; kiểm tra permission, wrong target, missing input, timeout, stale evidence.
5. Đảm bảo Resolver/Compiler/Runner không phải thay đổi chỉ để thêm Function cùng loại.

**Chưa có OpenWrt runtime production.** Đăng ký mapping mô phỏng không được quảng cáo là đã hỗ trợ firmware thật.

## 5. Lệnh kiểm tra

```bash
python -m scripts.check_project
python -m unittest tests.graph_v3.test_runtime_stages -v
python -m unittest discover -s tests -v
python -m gateway_pilot.assistant --fixture GLM-04-0 --request "Check WAN" --trace
```

CI trên nhánh refactor thực hiện tương đương và lưu hai trace smoke vào artifact. Trên Linux, web test dành riêng cho Windows sẽ được skip.

## 6. Lưu ý khi đánh giá

- `runs/` là output tự sinh, không commit; tên output mới cho mỗi lần chạy.
- Mọi số liệu model/benchmark phải gắn đúng phiên bản registry, fixture, commit, model và loại execution (synthetic/live).
- Đừng dùng fixture test để tối ưu rồi gọi kết quả là holdout.
- Các tài liệu v1/v2 là baseline, không phải mô tả đầy đủ của code Graph v4.
- Không đổi hash upstream sang một giá trị tùy ý hoặc bỏ qua verifier để làm CI xanh.

## 7. Vị trí CLI sau khi dọn dẹp

Các script không thuộc runtime được chuyển khỏi repo root. Chạy từ repo root với `python -m` để bảo đảm import độc lập hệ điều hành:

```bash
python -m scripts.benchmarks.run_function_selection --help
python -m scripts.benchmarks.run_html_benchmark --help
python -m scripts.benchmarks.run_dynamic_benchmark --help
python -m scripts.analysis.audit_html --help
python -m scripts.analysis.verify_run --help
```

Danh mục đầy đủ và ánh xạ lệnh cũ/mới tại [scripts/README.md](../scripts/README.md).

**Giữ ở repo root:** `setup_upstream.py` là bootstrap; `prepare_data.py` là bộ sinh fixture có đường dẫn được lưu trong metadata/hashes v1/v2. Không chuyển hoặc sinh lại frozen fixture. Các command cũ `python run_*.py` phải đổi sang `python -m scripts.benchmarks.run_*`.

## 8. Runtime stage interfaces

Các bước FunctionRouter → FunctionPlanner → GraphRunner → InvocationExecutor → EvidenceVerifier đã tách thành module riêng. Dependency injection chỉ từ cấu hình đáng tin cậy, không từ yêu cầu hay LLM. Xem [Runtime stages](RUNTIME_STAGES.md) cho phạm vi và những phần chưa thực hiện.

## 9. Typed multi-output Adapter & goal execution

Return `ToolResult(observations=(obs_port_a, obs_port_b))` from a trusted Adapter when a Function declares more than one output. Each observation requires a unique ID and the registered Function/port/source/target/schema; rejected results never assert a goal claim. The historical single-observation dict remains valid for one-output Functions.

Run: `python -m gateway_pilot.graph_v3.goal_agent --fixture GLM-04-0 --request "Check WAN and memory" --goals wan.status system.resources --method bm25`.

See [reference alignment and limits](REFERENCE_IMPLEMENTATION.md); this is an opt-in path and `RESOLVED` means measurement ports were verified, not that a real network incident was fixed.

## 10. Optional hybrid retrieval (trusted local encoder)

Gọi `registry.configure_semantic(encoder, min_similarity=0.62)` và `registry.retrieve(..., method="hybrid")`. Không cấu hình encoder từ user request. Khả năng vector chỉ thay đổi seed/rank; quyền Function vẫn do Registry và CaseState kiểm soát. Mọi model thực cần benchmark độc lập, xem [Semantic Retrieval](SEMANTIC_RETRIEVAL.md).
