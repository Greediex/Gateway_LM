# Gateway LM — Documentation Index

Bắt đầu ở [README](../README.md), sau đó chọn đúng nhóm tài liệu. **Tài liệu có số liệu ngày chạy là snapshot lịch sử**, không mặc nhiên là kết quả của nhánh mới nhất.

## I. Kiến trúc và cách phát triển (active)

| Tài liệu | Mục đích |
| --- | --- |
| [CLI script migration](../scripts/README.md) | Bảng chuyển lệnh root script sang package `scripts/benchmarks` và `scripts/analysis` |
| [Developer Guide](DEVELOPER_GUIDE.md) | Setup Windows/Linux/CI, cấu trúc module, thêm Function và chạy test |
| [OpenWrt Ubus adapter boundary](OPENWRT_ADAPTER.md) | Trusted Function mapping and requirements for real device probe |
| [WRITE transaction safety contract](WRITE_TRANSACTIONS.md) | Disabled-by-default approval, durable one-time nonce and mock rollback verification |
| [Signed read-only job journal](JOB_JOURNAL.md) | HMAC-chained step receipts and recovery boundaries |
| [Evidence checkpoint](CHECKPOINT.md) | HMAC-backed replay fact restore, ACL and freshness boundaries |
| [Nine workstream acceptance plan](ACCEPTANCE_9_TASKS.md) | Exact pilot vs hardware/model/live-provider sign-off criteria and commands |
| [Unified TaskRuntime](TASK_RUNTIME.md) | Common typed MEASURE / DIAGNOSE entrypoint and phase trace |
| [Task status / roadmap](TASK_STATUS.md) | Mốc MVP đã có, task còn thiếu và tiêu chí nghiệm thu |
| [Declarative Registry Extensions](REGISTRY_EXTENSIONS.md) | Trusted JSON overlays for safe new READ Functions/Skills |
| [Retrieval evaluation harness](SEMANTIC_RETRIEVAL.md#offline-function-retrieval-benchmark-v1) | Benchmark metrics and labeled JSONL test protocol |
| [Hybrid Semantic Retrieval](SEMANTIC_RETRIEVAL.md) | Local-only vector similarity, BM25/GoS fusion, hard gates, model evaluation pending |
| [Edge–Cloud delegation policy](EDGE_CLOUD_POLICY.md) | Explicit consent, privacy/FX budget and unverified hypothesis contract |
| [Evidence-driven RCA](EVIDENCE_RCA.md) | Adaptive Claim-based evidence acquisition and proof boundaries |
| [Bounded LLM goal / shared execution](LLM_EXECUTION_POLICY.md) | Validated LLM goal proposals and common READY dispatch |
| [Runtime stages](RUNTIME_STAGES.md) | Tách Routing, Planning, Execution và Evidence Verification; nêu phần đã có/chưa có |
| [Upstream comparison and goal execution](REFERENCE_IMPLEMENTATION.md) | GoS, SkillDAG, LangGraph, GraphFlow, ToolResult, dynamic goal DAG (opt-in) |
| [Web UI guide](WEB_UI.md) | Cách khởi động web và chọn replay/live adapter |
| [Architecture HTML v0.1](architecture/gateway-lm-v0.1-kien-truc.html) | Thiết kế giao diện và năng lực dự kiến; **không** phải danh mục implementation đã được chứng minh |
| [Graph v3 Protocol](GRAPH_V3_PROTOCOL.md) | Phạm vi, giới hạn, kế hoạch/contract và test |
| [Graph v3 Upstream Contract](GRAPH_V3_UPSTREAM_CONTRACT.md) | GoS/SkillDAG pin và phép ánh xạ |
| [Composite Adapter](ADAPTER_COMPOSITION.md) | Nhiều backend, capability gating, giới hạn và cách mở rộng |
| [Contract schemas](contracts/contract_0.schema.json) | Contract 0, A, B, C, evidence schema dưới `contracts/` |
| [AGENTS.md](../AGENTS.md) | Quy tắc thay đổi code/benchmark an toàn |

## II. Kết quả và trạng thái (giữ nguyên ngày gốc)

| Tài liệu | Phạm vi |
| --- | --- |
| [Graph v4 result — 11/11/2026](GRAPH_V4_RESULT_VI.md) | Snapshot G1–G23, kiểm thử trên replay; không thay thế kết quả CI của nhánh hiện tại |
| [Graph v4 changelog](GRAPH_V4_CHANGELOG.md) | Lịch sử thay đổi |
| [Graph v4 repair demo](GRAPH_V4_REPAIR_DEMO.md) | Ví dụ repair bằng dữ liệu replay |
| [Graph v3 result (historical)](reports/GRAPH_V3_RESULT_VI.md) | Báo cáo giai đoạn Graph v3 |
| [v1/v2 experiment overview](reports/EXPERIMENT_OVERVIEW_VI.md) | Benchmark và hạn chế của baseline |
| [Graph v3 repair demo](GRAPH_V3_REPAIR_DEMO.md) | Demo lịch sử |

## III. Báo cáo/paper và bằng chứng

| Tài liệu | Nội dung |
| --- | --- |
| [Paper Sources](PAPER_SOURCES.md) | Pinned repos, licenses, mô tả mức độ tham khảo |
| [Historical paper fidelity audit](PAPER_FIDELITY_AUDIT.md) | **Chỉ v1/v2**; không áp dụng nguyên trạng cho graph v4 |
| [Project Alignment](PROJECT_ALIGNMENT.md) | Pilot vs thiết kế và giới hạn |
| [HTML coverage audit](HTML_COVERAGE_AUDIT.md) | Mức độ phủ theo danh mục HTML |
| [Model interface notes](MODEL_INTERFACE_NOTES.md) | Giao diện model và điều kiện kiểm thử |
| [Native protocol](NATIVE_PROTOCOL.md) | Protocol giao diện native exploratory |
| [Test protocol](TEST_PROTOCOL.md) | Cách đọc thí nghiệm |

## IV. Dữ liệu được bảo vệ và lưu trữ

- `../data/` và `../benchmarks/`: nguồn fixture/benchmark. Không tự ý sửa khi refactor kiến trúc.
- `contracts/golden/`: golden traces. Chỉ cập nhật khi thay đổi contract được phê duyệt, có phân tích diff.
- `../runs/`: kết quả chạy cục bộ, được gitignore; không được dẫn chứng là có sẵn trên GitHub.
- [README trước cleanup](README_V01_DETAILS.md): bản lưu đầy đủ; các đường dẫn đến `runs/` cần dữ liệu cục bộ.
- [Upstream hash verification](UPSTREAM_HASH_VERIFICATION.md): lý do hash pinned file đã được đồng bộ theo upstream commit.

## V. Trạng thái code so với kế hoạch sản phẩm

**Đã có và được kiểm trên replay:** Registry/typed ports, GoS PPR kernel, SkillDAG adapter, Function Resolver, DAG Compiler, Runner/Repair, Evidence/Claim, các entry point và Web UI.

**Chưa chứng minh trên thiết bị thật:** OpenWrt Function, NPU deployment, Task DAG tổng quát, RCA thật, cấu hình router WRITE.

Xem kết quả kiểm thử mới nhất trong workflow của nhánh refactor thay vì cộng số liệu giữa các báo cáo lịch sử.

## Foundation v0.2

- [FND-01: Function Contract v0.2 — chuẩn và mapping](contracts/catalog-v02/README.md).
- [FND-01: kết quả nghiệm thu local](reports/FND01_CONTRACT_V02_20261113.md).
- [Foundation design và FND-01 đến FND-07](superpowers/specs/2026-11-13-command-catalog-v02-design.md).
- [Todo triển khai](../TODO.md).

- [FND-02: catalog READ theo domain](../catalog/README.md).
- [FND-02: kết quả nghiệm thu local](reports/FND02_READ_SEED_CATALOG_20261113.md).
