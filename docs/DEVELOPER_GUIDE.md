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
    registry_v01.py, graphs.py, resolver.py  # catalog/retrieval
    planner.py, runner.py, repair.py         # planning/execution
    state.py, claims.py, contracts.py        # verified state/claims
    upstream.py, skilldag.py                 # pinned upstream integration
  adapters/                                 # typed Function adapters
web_gateway/                                # web UI and tests
data/ + benchmarks/                         # frozen test data
docs/contracts/                             # machine-readable contracts
```

Điểm bắt đầu hợp lý khi mở rộng Function: [Adapter composition](ADAPTER_COMPOSITION.md), `registry_v01.py`, `tests_graph_v3/test_registry_v01.py`.

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
python -m unittest discover -s tests_graph_v3 -v
python -m unittest discover -s tests -v
python -m unittest discover -s web_gateway/tests -v
python -m gateway_pilot.assistant --fixture GLM-04-0 --request "Check WAN" --trace
```

CI trên nhánh refactor thực hiện tương đương và lưu hai trace smoke vào artifact. Trên Linux, web test dành riêng cho Windows sẽ được skip.

## 6. Lưu ý khi đánh giá

- `runs/` là output tự sinh, không commit; tên output mới cho mỗi lần chạy.
- Mọi số liệu model/benchmark phải gắn đúng phiên bản registry, fixture, commit, model và loại execution (synthetic/live).
- Đừng dùng fixture test để tối ưu rồi gọi kết quả là holdout.
- Các tài liệu v1/v2 là baseline, không phải mô tả đầy đủ của code Graph v4.
- Không đổi hash upstream sang một giá trị tùy ý hoặc bỏ qua verifier để làm CI xanh.
