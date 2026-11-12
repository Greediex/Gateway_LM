# Kết quả graph v4 — đối chiếu G1–G23 (MVP v0.1)

Kết quả kiểm thử ngày 2026-11-11. Test hiện tại: **284 graph / 34 legacy / 12 web, tất cả pass**.
Mọi số đo là **replay tổng hợp trên host**, chưa có phép đo trên router/OpenWrt.

Các nhãn trong cột mức trung thực mô tả cách dùng mã tham chiếu.
- `UPSTREAM_CALLED`: gọi đúng mã của tác giả đã ghim.
- `PORTED_WITH_PARITY_TEST`: viết lại, có test so khớp số với bản gốc.
- `GATEWAY_DESIGN`: thiết kế riêng theo HTML.

GraSP chỉ có bản tái lập **không chính thức**; không có câu "tái lập paper" nào trong mã hay tài liệu.

| Mã | Khoảng lệch đã xử lý | Task | Trạng thái | Mức trung thực | Test chứng minh |
|---|---|---|---|---|---|
| G1 | Retrieval điều khiển kế hoạch; Function Resolver + Contract 0 | T4 | Đã có | GATEWAY_DESIGN | `test_resolver.py` |
| G2 | Seed PPR theo reciprocal-rank, không dùng BM25 thô | T3 | Đã có | UPSTREAM_CALLED (kernel) | `test_gos_retrieval.py` |
| G3 | Rerank sau PPR, tách `seed_top_k` / `top_n` | T3 | Đã có | PORTED_WITH_PARITY_TEST | `test_gos_retrieval.py` |
| G4 | Không khớp từ vựng → rỗng, không seed theo chữ cái | T3 | Đã có | PORTED_WITH_PARITY_TEST | `test_gos_retrieval.py` |
| G5 | Weight cạnh theo overlap I/O, không đếm kép | T3 | Đã có | PORTED_WITH_PARITY_TEST | `test_gos_retrieval.py` |
| G6 | PPR trên graph tĩnh đầy đủ rồi mới gate | T3 | Đã có | PORTED_WITH_PARITY_TEST | `test_gos_retrieval.py` |
| G7 | G_S qua SkillDAG: reason, cycle backbone, polarity, history | T2 | Đã có | UPSTREAM_CALLED | `test_skilldag_gs.py`, `test_graph_runtime.py` |
| G8 | `search` matches / neighbors / conflicts | T2 | Đã có | UPSTREAM_CALLED | `test_skilldag_gs.py` |
| G9 | Không đẩy loại cạnh riêng sang SkillDAG | T2 | Đã có | UPSTREAM_CALLED | `test_skilldag_gs.py` |
| G10 | Invocation theo Function + target | T5 | Đã có | GATEWAY_DESIGN | `test_compiler_v01.py` |
| G11 | `skill_context` theo G_SF nhiều–nhiều | T4 | Đã có | GATEWAY_DESIGN | `test_resolver.py` |
| G12 | `src`/`snk`, bốn ràng buộc, ORDER mềm có audit | T5 | Đã có | PORTED_WITH_PARITY_TEST (cấu trúc) | `test_compiler_v01.py` (fixture apple của bản tái lập) |
| G13 | Local repair 5 toán tử + một GLOBAL_REPLAN | T6 | Đã có | GATEWAY_DESIGN (theo bảng của bản tái lập) | `test_repair_t6.py` |
| G14 | Verifier phân loại precondition / postcondition / execution / timeout | T6 | Đã có | GATEWAY_DESIGN | `test_repair_t6.py` |
| G15 | Precondition, completion port, permission trong contract | T1 | Đã có | GATEWAY_DESIGN | `test_registry_v01.py` |
| G16 | Function contract đủ `status`, `adapter`, `capability_probe`, `evidence_scope`… | T1 | Đã có | GATEWAY_DESIGN | `test_registry_v01.py` |
| G17 | Evidence record HTML, fact có phạm vi, Contract B/C | T7 | Đã có | GATEWAY_DESIGN | `test_evidence_t7.py` |
| G18 | Phân biệt `READ_ONLY` / `PROBE` / `WRITE` | T1 | Đã có | GATEWAY_DESIGN | `test_registry_v01.py` |
| G19 | Benchmark Function Selection A–E | T9 | Đã có (replay) | GATEWAY_DESIGN | `test_function_selection_t9.py` |
| G20 | Tám loại lượt, câu trả lời có căn cứ | C2, C3 | Đã có | GATEWAY_DESIGN | `test_turn_router.py`, `test_answer_c3.py` |
| G21 | Catalog ba cấp, chọn workflow động có band | C1, C2 | Đã có | GATEWAY_DESIGN | `test_catalog_c1.py`, `test_turn_router.py` |
| G22 | Claim contract dữ liệu; kết luận qua claims | C4 | Đã có | GATEWAY_DESIGN | `test_claims_session_c4.py` |
| G23 | Case giữ qua phiên | C4 | Đã có | GATEWAY_DESIGN | `test_claims_session_c4.py` |

## Số đo chính (replay)

| Benchmark | Kết quả holdout | Báo cáo |
|---|---|---|
| Function Selection (60 ca) | Arm E: recall 0.97, đúng status 30/30, 0 false-resolution, 0 vi phạm; precision 0.36, 239 lượt gọi. Arm D: 0 false-resolution, 0 vi phạm | `run_function_selection.py` |
| Hội thoại (193 lượt) | Router: đúng loại lượt 0.81 (regex 0.26), 0 câu trả lời rỗng, 0 false-resolution; gọi tool sai S/K/C 1/25 | `run_conversation_benchmark.py` |
| Claims ↔ `core.support()` | 16.320 lần so tại mọi `proof()`, 0 sai lệch | `tests/graph_v3/test_claims_session_c4.py` |

## Chưa đạt / việc mở

- **M0 chưa đạt tiêu chí firmware:** chưa có Function nào probe trên OpenWrt; adapter OpenWrt chỉ là khung (T8, chờ board).
- **Router:** câu ngoài phạm vi, câu ít từ khoá và lệnh restart/reboot (nợ #13, #14).
- **Advisor LLM:** gây false-resolution khi thiếu thiết bị (nợ #21).
- **Retrieval:** chọn Function phía client khi không có target (nợ #20).
