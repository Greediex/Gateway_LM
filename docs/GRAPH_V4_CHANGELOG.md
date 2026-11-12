# Thay đổi hành vi graph v4

## T8 — adapter boundary và capability probe (2026-11-11)

`gateway_pilot/adapters`: `ReplayAdapter`, `WindowsLiveAdapter`, khung `OpenWrtUbusAdapter` (mọi ánh xạ ubus `None`).
`diagnose` gate capability theo `adapter.probe()` khi replay có `adapter`; runner gọi qua adapter. Cờ
`Port.untrusted_text` thay chuỗi `system.logs` gắn cứng trong `state_query`. Web chạy qua `ReplayAdapter`.
288 lượt `diagnose()` không đổi, có hoặc không có adapter. Không test cũ nào phải sửa.

## C3 — G20, Answer Composer (2026-11-11)

`assistant.answer` trả cấu trúc `Turn` có `grounding`, `evidence_ids`, `doc_ids`, `next_steps`, `contracts`.
Câu chẩn đoán = câu claim + evidence có điểm đo và thời điểm; `PARTIAL` luôn có "Chưa xác minh". LOOKUP đo đủ
mọi port được hỏi giờ là `RESOLVED` (trước C3 là `PARTIAL`). LLM tuỳ chọn bị hậu kiểm số và mã. Không test cũ
nào phải sửa.

## C4 — G22 / G23, claim contract và Case theo phiên (2026-11-11)

Registry v0.1 thêm khối `claims` (22 claim: mọi luật của `core.support()` cùng các kết luận quan sát của
workflow; `no_fault_observed` tách theo workflow) và `partial_claims` cho WF-023. `graph_v3/claims.py`
đánh giá tri-state, tự lắp evidence id. `Diagnostic.proof`/`observed` và kết luận cuối của cả hai route
(`verify_terminal`) đi qua claims; `finish()` lấy `case_status` từ scope/severity của claim thay cho hai tập
`ROUTER_FAULTS`/`PARTIAL_OBSERVATIONS` (đã xoá). `core.support()` giữ nguyên làm baseline v1 và làm chuẩn
đối chiếu. Next-best-action tất định có ở `ClaimBook.next_best_action`, bật bằng `diagnose(selection="nba")`;
mặc định giữ thứ tự của resolver vì NBA tốn thêm lượt gọi trên replay (ghi ở báo cáo C4).
`gateway_pilot/session.py`: `Session`/`SessionStore` trong bộ nhớ có TTL. `assistant.answer(session=Session)`
và web (`session_id`) giữ một Case qua các lượt; `app.js` bỏ ghép chuỗi. Router nhận "còn <thiết bị> thì
sao" là `FOLLOW_UP` khi phiên đang có Case. Không test cũ nào phải sửa; 288 lượt `diagnose()` y hệt.

## T7 — G17, evidence layer và Contract B/C (2026-11-11)

Registry v0.1 thêm khối `facts` (15 fact `router_*` / `client_*`): ánh xạ `port.field op value` → fact có
phạm vi. Loader từ chối fact khác phạm vi với port, nên quan sát tại gateway không thể sinh fact client.
`Predicate` thêm phép so số `ge`, `lt`, `le`. `CaseState.usable` tách thành `validator()` →
`{schema, target, fresh}` (cùng ngữ nghĩa); thêm `fact_table`, `state_revision`, `hypotheses`,
`set_environment`, `evidence_record`, `case_status`, `export_contract_c`. Runner bỏ `ttl_s=30` và
`observed_at` ghi cứng: TTL lấy từ contract, thời điểm từ clock tiêm vào; xuất Contract B
(`tool_status` tách khỏi `goal_claim: NOT_EVALUATED`). Trace của `Diagnostic` có `contract_b`,
`contract_c`. 288 lượt `diagnose()` cho kết quả y hệt trước T7.

| Test cũ đã sửa | Mã G | Hành vi cũ | Hành vi mới |
|---|---|---|---|
| `RegistryV01Tests.test_compiler_and_replay_match_legacy` | G17 | Evidence legacy và v0.1 giống hệt sau khi bỏ `contract_digest`. | Evidence có thêm `case_id`; v0.1 cấp UUID cho Case (T5) nên test bỏ thêm `case_id` sau khi kiểm nó bằng `state.case_id`. Mọi trường khác vẫn phải giống hệt. |

## T6 — G13 / G14, verifier có kiểu và local repair (2026-11-11)

Node lỗi mang `failure = {type, status, message}` với `type` ∈ precondition / postcondition / execution /
timeout. `runner.repair` chạy RETRY (như cũ), rồi `repair.local_repair` vá trên chính DAG
(`revision + 1`, audit diff), hết cách mới leo thang **một** lần `GLOBAL_REPLAN`, sau đó `INCOMPLETE`.
Nhánh biên dịch lại cũ trở thành `GLOBAL_REPLAN`; node tái dùng giữ cạnh giữa chúng và không ghi đè node
cùng khoá của plan mới (nợ #15). `runner.run` thử vá precondition khi các node BLOCKED vì guard UNKNOWN
(không bao giờ khi guard FALSE). Thêm chuyển tiếp FAILED/INCONCLUSIVE → SKIPPED, chỉ dùng cho BYPASS.
`workflow.diagnose` không gọi repair: 288 lượt (72 fixture × 2 route × 2 registry) cho kết quả y hệt trước T6.

| Test cũ đã sửa | Mã G | Hành vi cũ | Hành vi mới |
|---|---|---|---|
| `GraphTests.test_timed_out_producer_substituted_and_unrelated_evidence_preserved` | G13 | Audit ghi `SUBSTITUTE_REWIRE_INSERT_PREREQ` sau khi biên dịch lại toàn bộ. | Vá cục bộ trên cùng DAG: audit `SUBSTITUTE` với `replaced={'wan.status': 'z.status.backup'}`; các assert revision/evidence/attempts giữ nguyên. |

## C1 — G21, catalog ba cấp và client.dns (2026-11-10)

Registry v0.1 thêm 101 workflow HTML được chép vào `data/workflow_catalog_v01.json`
(giữ tiêu đề/triệu chứng và Skill thiết kế, kèm SHA-256 nguồn), cộng hai khóa pilot
`WF-INTERNET` và `WF-WRITE`. Năm workflow chạy được giữ ID pilot, lưu ánh xạ HTML
riêng; goal WF-INTERNET thêm `client.dns`. Function này có contract và precondition
giống `workflow.workflow_registry()`, risk `PROBE`, status `REPLAY_ONLY`.

Graph tĩnh thêm Workflow→Skill đã triển khai. Workflow có ngân sách kết quả riêng
`workflow_top_n=3`, dùng BM25, field rerank và kernel PPR hiện có trên cùng index/graph.
Lượt xếp workflow độc lập với seed chọn Function để `CATALOG_ONLY`/`CHANGE` không
trở thành seed Function. Những bản ghi này không có goal/minimal goal; compiler
nhận goal rỗng thì không có node. Không đổi router, dynamic policy, CLI/web mặc định.

| Test cũ đã sửa | Mã G | Hành vi cũ | Hành vi mới |
|---|---|---|---|
| `RegistryV01Tests.test_field_by_field_legacy_equivalence` | G21; nợ T1 #1 | So 16 Function với `GraphRegistry()` chưa thêm `client.dns`. | So 17 Function/port/precondition với `workflow_registry()`; phân loại thêm `client.dns` là PROBE; goal có bản ghi catalog rỗng và thêm client.dns cho WF-INTERNET. |
| `RegistryV01Tests.test_loader_does_not_read_frozen_registry_or_catalog` | G21 | Reader chỉ cho hai file data, đếm 16 Function. | Cho thêm bản catalog được ship trong data/, đếm 17 Function; vẫn không cho đọc nguồn runs/ hoặc registry frozen. |
| `RegistryV01Tests.test_write_and_unverified_never_eligible_even_with_permissive_state` | G21 | Loader nhận catalog mà mọi producer đều WRITE/unverified rồi kiểm gate. | Loader C1 từ chối goal không có producer hợp lệ; nạp catalog hợp lệ rồi đổi contract trong bộ nhớ để giữ nguyên kiểm tra hai gate và compiler. |
| `RegistryV01Tests.test_status_and_adapter_hard_gate` | G21 | Đổi producer duy nhất của client.identity trước khi load. | Nạp catalog hợp lệ rồi đổi status/adapter trong bộ nhớ; giữ nguyên mọi tổ hợp và kết quả gate. |

Test mới `CatalogC1Tests.test_loader_rejects_goal_without_eligible_in_principle_producer`
kiểm riêng việc loader từ chối producer thiếu, WRITE, PROBE_FAILED hoặc sai adapter.
Các test mới khác nằm trong `tests/graph_v3/test_catalog_c1.py`. Toàn bộ phần catalog
là `GATEWAY_DESIGN`; công thức rerank và kernel upstream của T3 không đổi.

## T3 — G2 / G3 / G4 / G5 / G6 (2026-11-10)

Không sửa test cũ. Thêm 8 test trong `tests/graph_v3/test_gos_retrieval.py`: parity kernel với seed reciprocal-rank, công thức rerank tính tay trên sáu node, transition membership và weight I/O, hard gate trên graph đầy đủ, query không match trả rỗng và caller fallback, cache theo G_S version, budget/alias `k`, cùng pipeline seed fusion và scan PPR trước rerank top_n.

Hành vi mới: seed/top_n độc lập; không dùng BM25 thô làm personalization; bỏ fallback chữ cái; graph tĩnh đầy đủ; dependency weight theo phần input consumer được `Port.accepts` xác nhận; một cạnh membership Skill→Function kiểu workflow và reverse do kernel. Nhãn: GoS lexical-seed mode, không có embedding/LLM rewrite. READY vẫn dùng PPR, khi retrieval rỗng dùng objective rồi id; không thay resolver (T4).

## T2 — G7 / G8 / G9 (2026-11-10)

| Test cũ đã sửa | Mã G | Hành vi cũ | Hành vi mới |
|---|---|---|---|
| `GraphTests.test_skill_dependency_cycle_rejected` | G7 | Chỉ kiểm cycle `depends_on`, lỗi `skill_dependency_cycle` do pilot. | Kiểm backbone `depends_on` + `specializes` qua upstream, lỗi `WOULD_CREATE_CYCLE`. |
| `GraphTests.test_dry_run_edit_permission_version_and_rollback` | G7 | Đề xuất/rollback không có lý do. | Bắt buộc `reason`; vẫn kiểm quyền, version và hoàn tác extension riêng của pilot. |
| `GraphTests.test_conflicting_skill_dependency_proposal_rejected` | G7 | Không có reason, lỗi `dependency_conflict` riêng. | Có reason và lỗi polarity `CONTRADICTORY_EDGE` của upstream. |
| `GraphTests.test_skill_graph_revision_change_invalidates_compiled_plan` | G7 | Thêm `composes_with(SK05,SK04)` ngược cạnh có sẵn `(SK04,SK05)`, được tính như sửa graph. | Upstream chuẩn hóa đối xứng nên cạnh đó là `EDGE_ALREADY_EXISTS`; dùng cạnh `similar_to` mới, có reason, vẫn kiểm plan cũ bị vô hiệu. |

## C2 — G20 / G21 (2026-11-10)

| Test cũ đã sửa | Mã G | Hành vi cũ | Hành vi mới |
|---|---|---|---|
| `ResolverTests.test_c_change_dns_is_blocked_without_adapter_calls` | G20; nợ T4 #1 | Resolver tự nhận diện yêu cầu thay đổi bằng regex trùng `CHANGE_REQUEST`. | Caller truyền `intent="CHANGE"`; giữ nguyên mọi assert BLOCKED, WRITE bị từ chối và 0 tool call. Turn Router dùng duy nhất `workflow.CHANGE_REQUEST`. |

Thêm `tests/graph_v3/test_turn_router.py`; mặc định `workflow.diagnose()` vẫn dùng registry legacy,
chỉ `assistant.answer()` mặc định registry v0.1. Không sửa symptoms, web, dữ liệu frozen, runs hay mã/SHA upstream.

### C2 — Sửa lần 1 (2026-11-10)

Goal scope lấy từ port; goal client chưa có target được hoãn, gateway vẫn đo được trước khi hỏi thiết bị.
Cue song ngữ nằm trong JSON có kiểm kiểu; phạm vi được xác lập bằng cue network hoặc điểm retrieval.
Catalog dưới ngưỡng không chặn supported top-3; menu chỉ có supported. Subject tường minh dùng IDF/metadata,
không còn nhánh quang riêng. Workflow bị hạ khi mọi producer eligible của một goal thiếu có predicate FALSE;
không suy link-down thành DNS-blocked. Thêm tags PON/LOS trong registry và đưa tags tùy chọn vào index.

| Test có sẵn được sửa | Mã G | Hành vi cũ | Hành vi mới / lý do |
|---|---|---|---|
| `TurnRouterTests.test_mid_dns_wan_reroutes_same_case_without_dns_probe` → `test_mid_dns_wan_continues_minimal_goals_without_invented_preconditions` | G20/G21 | Ép WF-018/HIGH sau link-down, chỉ một call. | Contract DNS không có predicate link-up: giữ MID, đo `wan.status` và `dns.config`, không đo `dns.probe` vì nó không thuộc minimal goals; history một phần tử, không giả vờ đã đổi nhánh. Claim routing thuộc C4. |
| `TurnRouterTests.test_missing_or_ambiguous_client_asks_with_inventory_selectors` | G20/G21 | Coi toàn workflow DHCP là client và luôn hỏi ngay. | Dựng retrieval MID chỉ có DHCP/minimal goal `client.identity` để kiểm đúng trường hợp mọi goal đều cần client; giữ hai câu và assert danh sách selector/không plan. Full DHCP có goal gateway thì được đo trước. |
| `TurnRouterTests.test_five_examples_per_turn_in_three_languages` | G20 | Bắt buộc mọi câu nhãn OUT_OF_SCOPE luôn bị loại bởi keyword. | Kiểm ngoại lệ retrieval_score ≥ tau_low theo luật scope mới; giữ nguyên nhãn dev và báo các phân loại sai riêng, không đổi nhãn để tăng accuracy. |
| `TurnRouterTests.test_non_measurement_turns_never_execute` | G20 | Dùng câu thơ làm mẫu OUT_OF_SCOPE. | Dùng câu hỏi nấu ăn có retrieval dưới ngưỡng; vẫn assert loại lượt, không graph và hai executor không được gọi. Câu thơ gốc vẫn ở dev, sai loại được báo và có 0 call. |
| `CatalogC1Tests.test_static_workflow_projection_has_one_directed_edge_per_implemented_skill` | G21 | Tags index chỉ gồm kind/scope. | Kiểm thêm toàn bộ tags metadata tùy chọn, giữ nguyên assert cạnh và fields khác. Cần cho subject tường minh PON/LOS qua index chung. |

Không sửa test legacy hoặc web. Thêm 9 test router, từ 203 lên 212 graph tests.
