# Graph v3 — implementation và kết quả kiểm chứng

Đã thay phần graph của baseline bằng runtime riêng, giữ nguyên code/data/run v1–v2. Phạm vi là chẩn đoán replay một target/case; chưa hoàn thiện toàn sản phẩm trong HTML.

## Phần đã sửa

| Thành phần | Implementation thực tế |
|---|---|
| G_S | Quan hệ có kiểu; dependency closure, conflict, soft composition/alternative; propose/edit/version/rollback có kiểm quyền |
| G_SF | Membership hai chiều dùng trong graph retrieval và điều kiện Skill |
| H_F | Port/schema/scope/provenance, đa input/output, tìm producer tương thích |
| G_run | Invocation target/args/binding/verifier/digest; cạnh DATA/STATE/ORDER, node state và plan revision |
| GoS | Gọi ba hàm kernel PPR upstream có pin SHA; chuyển hướng dependency và parity với oracle/direct call |
| Planner | Lọc trước top-k, query cập nhật theo state; loại output đã đủ; tìm phương án theo tổng declared cost và dependency dưới search budget |
| Runner/repair | READY scheduler dùng PPR thật, kiểm chứng từng node; retry/alternative/revision; giữ nghĩa vụ còn lại và proof không bị ảnh hưởng |

## Kiểm chứng

- 50 test graph v3 pass; 34 test legacy pass; 0 fail/error/skip, exit code 0. Log: `docs/graph_v3_validation.log`.
- 48 ca cấu trúc chạy xong; kernel GoS được gọi 146 lần. Không chấm model ở lượt này (null).
- Microbenchmark k=2, bốn thư viện synthetic cỡ 4/16/64/128: BM25 đủ bundle 0/4, GoS PPR đủ bundle 4/4. Đây là oracle được dựng để kiểm prerequisite recovery, không phải accuracy tổng quát hoặc benchmark paper.
- `repair_demo.json` ghi trace timeout mô phỏng → producer backup → revision 2; DNS đã xác minh được giữ lại và không chạy lại.
- Integrity checks PASS: hash source snapshot/data cũ, DAG acyclic/bindings, verifier/proof và chỉ số được đối chiếu lại từ JSONL.

## End-to-end model (số liệu phụ)

| Operating point | Tự hoàn tất đúng | Tool/ca |
|---|---:|---:|
| v2 native analyst, Core lấy evidence theo list | 27/48 | 3.21 |
| v3 native analyst, Core dùng graph mới | 27/48 | 3.04 |

Cùng Qwen3 tag 1.7b, metadata khoảng 2.032B, Q4_K_M, CPU; không fine-tune. Model vẫn chỉ làm analyst. Tiêu chí action/diagnosis/citation và việc loại forced-stop được giữ nguyên.
Graph mới không làm tăng số ca model thành công trong lượt này. Lỗi citation/đọc evidence vẫn còn; không gán điểm kiểm chứng graph thành chất lượng reasoning của model. Nguồn evidence/IDs và guard mới khác v2, nên đây là operating-point follow-up, không cô lập nhân quả của riêng PPR và không phải holdout mới.

## Ranh giới còn lại

- Reuse kernel GoS thật, không tái lập toàn pipeline GoS embedding/LLM seed/rerank/hydration hoặc benchmark paper; không có SE-GoS trace-driven evolution.
- Schema compatibility là tập con bảo thủ, cấu trúc chưa hỗ trợ bị từ chối; không phải solver subsumption JSON Schema tổng quát.
- Cost/latency trong contract là khai báo policy; search hoàn tất chỉ tối ưu trong không gian READ/schema/budget được mô hình hóa. Không chứng minh tối ưu trên board.
- Function dùng Skill context chính của contract trong runner chẩn đoán này; nhiều invocation khác target/args trong cùng case chưa triển khai.
- Deadline là kiểm hợp tác trước/sau replay call, không phải adapter thật có preemption. Chưa transaction, persistent recovery, firmware/NPU hoặc forwarding benchmark.

## Chạy lại

```powershell
# Chạy từ thư mục Gateway_LM
python -m venv .venv-graph
.\.venv-graph\Scripts\python.exe -m pip install -r requirements-graph-v3.lock
.\.venv-graph\Scripts\python.exe -m unittest discover -s tests_graph_v3 -v
.\.venv-graph\Scripts\python.exe -m gateway_pilot.graph_v3.evaluate --output runs/my_graph_run
.\.venv-graph\Scripts\python.exe -m gateway_pilot.graph_v3.evaluate --model qwen3:1.7b --output runs/my_model_run
```

Mọi output phải là đường dẫn mới. Protocol: `docs/GRAPH_V3_PROTOCOL.md`; upstream contract: `docs/GRAPH_V3_UPSTREAM_CONTRACT.md`.
