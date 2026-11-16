# Gateway LM v2 — Kế hoạch chạy gói 120 Skill

**Backlog hiện hành, cập nhật 16/11/2026.** [Checklist chính](../TODO.md). Thay thế cách triển khai dựa trên danh sách Foundation/GLM cũ; kết quả lịch sử vẫn có trong Git và [TASK_STATUS](TASK_STATUS.md).

## Baseline và đích cần đạt

Integration pack tại `46ba358` cung cấp 120 Skill thiết kế, 206 relation records, 72 PROPOSED Function/Port/Skill contract pairs và 40 Skill đề xuất chưa có direct READ Function. Có 8 legacy Skill references; không cộng thêm chúng lần nữa vào tổng 120. 203 edges còn là proposals chưa được duyệt. 270 trong data là requirements, không phải Skill.

Đã có validator/builder, trusted Core READ v0.2, `RuntimeSkillBridge`, synthetic provider và 72/72 smoke qua Core. Smoke hiện dựng catalog tạm từng Function; chưa phải catalog launcher/session cho người dùng. Web đang chạy profile Linux 7 READ Functions riêng; chưa hiển thị hay chạy toàn bộ gói mới. [Hướng dẫn gói](skill_expansion/README.md), [acceptance](reports/SKILL_EXPANSION_INTEGRATION_20261113.md).

Đích đầu tiên: người dùng chọn một Skill thuộc profile đã review → planner resolve đúng Function/Port versions và target → approved READ runtime → Verifier → snapshot/result có evidence và TTL. Tiếp theo tích hợp RCA và bounded LLM đề xuất phép đo.

## Ba task bắt buộc để chạy gói mới

### CAT-01 — Profile, mapping và dependency (DONE metadata)

**Tận dụng:** `skill_expansion/{catalog,repo_audit,edge_gate}.py`, mapping 120 Skill, catalog validator/builder.

- [x] Kiểm đủ 120 mapping: legacy reference, direct READ proposal, composite/workflow; ghi rõ gap thay vì gán capability giả.
- [x] Chọn batch READ đầu tiên, chia profile theo domain/scope/backend. Pin Function/Port/Skill versions và completion ports; kiểm producer dependency, identity và target.
- [x] Review semantic/typed witnesses cho các edge cần dùng. Soft retrieval affinity không được đổi thành DATA/STATE/ORDER chỉ vì có trong graph đề xuất.
- [x] Xuất coverage/missing report: declared, selected, replay-verified và live-verified là các số riêng.

**Nghiệm thu:** selection tái tạo được, builder pass, unknown/dangling/cross-scope/ambiguous mapping bị chặn. Không yêu cầu duyệt cả 203 cạnh mới được chạy batch nhỏ; chỉ cạnh đã review mới ảnh hưởng execution.

### CAT-02 — Một registry/replay runtime cho tập Skill đã chọn

**Phụ thuộc:** CAT-01. **Tận dụng:** `RuntimeSkillBridge`, `StrictSkillReplayBackend`, `BindingSelection`, `ReadRuntime`, Compiler/GraphRunner/Verifier.

- [ ] Tạo profile replay versioned, exact deployment selection/policy, artifact và binding review pins, synthetic target/environment rõ ràng.
- [ ] Tách reviewed deployment records khỏi source PROPOSED. Không auto-promote lifecycle ở startup, không lấy artifact tự tính hash làm operator approval.
- [ ] Resolve đủ identity/dependency từ contracts của profile và thực thi chúng qua Core; không chèn raw initial_evidence để vượt target gate.
- [ ] Cho nhiều Skill tái sử dụng một runtime/CaseState với freshness/context checks, tổng call/cost/deadline budget và isolation; bridge cần context/session API phù hợp nếu API hiện có chưa đủ.
- [ ] Test invocation theo Skill, dependency sharing, unsupported Function, missing approval, permission/lease/context change, contract mutation, bad output và no-fallback.

**Nghiệm thu:** các Skill trong profile chạy được qua cùng shared Core, có complete verified outputs và audit; profile không hỗ trợ phải UNAVAILABLE. Synthetic profile không được báo là live/hardware support. Smoke tạm hiện có tiếp tục là regression độc lập.

### CAT-03 — CLI/API/Web catalog launcher

**Phụ thuộc:** CAT-02. **Tận dụng:** Web UI hiện có, catalog preview, Feature Registry/AvailabilityService và verified snapshot.

- [ ] CLI chọn profile/Skill ID từ cấu hình tin cậy; API chỉ nhận ID thuộc tập server cho phép, không nhận commands/backends/targets/quyền/registry paths.
- [ ] Danh sách Skill có domain, trạng thái proposal/selected/availability, reason, required/missing ports và nguồn replay/live; không dùng `NOT_BOUND` từ design catalog làm capability thực tế.
- [ ] Runtime kiểm lại authorization/capability trước call. Feature/Skill chưa có workflow/backend không có nút chạy giả.
- [ ] Hiển thị verified evidence IDs, target/source/observed time/TTL và kết quả thiếu/error/stale; không tạo healthy hoặc root-cause Claim từ tool success.
- [ ] Giữ Linux/Windows/replay hiện có; có test HTTP isolation và visual loading/error/stale/success.

**Nghiệm thu:** người dùng chọn và chạy Skill được duyệt trên profile replay, xem được trace và snapshot; dữ liệu thiếu không hiển thị healthy. Không sửa Runner theo từng Skill ID.

## Mở rộng sau mốc launcher — giữ mã NEXT

| Task | Ưu tiên | Công việc bám gói mới | Phụ thuộc / nghiệm thu chính |
|---|---|---|---|
| NEXT-01 | P0 | Nối RCAAgent và declared Claims/workflows với v0.2 Skill runtime | CAT-02/03; Claim TRUE cần fresh scoped evidence, thiếu dữ liệu trả INCONCLUSIVE; snapshot là view, không input cấp quyền |
| NEXT-02 | P0 | Adaptive next-evidence selection và bounded repair | NEXT-01; test timeout/alternative/stale/no-progress/budget; không đo cả catalog mặc định |
| NEXT-03 | P0 | Bounded local LLM Goal Proposal | NEXT-01/02, baseline NEXT-10; chỉ registered authorized READ ports, reject hallucinated goals/WRITE/injection; fallback/clarification có audit |
| NEXT-04 | P0 | Hoàn thiện Wi-Fi/Devices/DHCP contracts và composite Skill definitions | CAT-01; tách laptop/AP/router semantics; batches có mapping/schema/binding tests; 40 Skill thiếu cần workflow/Claim hoặc gap rõ ràng |
| NEXT-05 | P0 | UbusRead/CompositeAdapter cho approved catalog qua replay/mock | NEXT-04 + phần NEXT-11; complete typed outputs, target/version/source pins, support-loss/error tests; chưa hardware acceptance |
| NEXT-06 | P1 | Device targeting, Client–AP–Router relations | NEXT-01/04/05; inventory evidence/TTL, ambiguity clarification và multi-client isolation |
| NEXT-07 | P1 | Bounded History và evidence records | CAT-02 + snapshot/checkpoint/journal; retention/quota/integrity/context mismatch; historical data không refresh TTL |
| NEXT-08 | P1 | Monitoring, Alerts và Incident lifecycle | NEXT-07, NEXT-02 cho adaptive RCA; debounce/dedup/no-overlap/quota; UNKNOWN không tự đóng thành resolved |
| NEXT-09 | P1 | RCA/Devices/History/Alerts UI | Mở từng phần theo NEXT-01/06/07/08, tái sử dụng CAT-03; API/payload isolation, scope/time/incident state rõ |
| NEXT-10 | P0 | Evaluation protocol và holdout replay có nhãn | Baseline từ CAT-01, trước tuning RCA/LLM; selection/RCA/abstention/model-invalid/tool calls/repair/latency p50/p95; version mới, dev/test tách, không relabel illustrative fixtures thành holdout |
| NEXT-11 | P1 | Ubus I/O/resource hardening | Phần cần thiết đi trước NEXT-05; bounded output tại transport, timeout/cancel/process cleanup, isolation và no payload leak |
| NEXT-12 | Để sau | READ acceptance trên OpenWrt thật | NEXT-05/06/10/11 + thiết bị/scope; board/firmware hash, actual Ubus mapping/probe/Core trace/resources; không suy từ CI/mock |

## Trình tự và gate

1. **CAT-01 → CAT-02 → CAT-03**: batch nhỏ chạy được trước, mở rộng profile sau khi có coverage report.
2. Chuẩn bị **NEXT-10 baseline từ CAT-01**, khóa protocol/dev-test trước tuning; sau launcher chạy **NEXT-01 → NEXT-02 → NEXT-03**.
3. **NEXT-04 → NEXT-05** theo domain, đưa phần cần của NEXT-11 vào trước mock acceptance. Không mở 72 Functions trên thiết bị thật bằng copy fixture.
4. **NEXT-06/07 → NEXT-08**; NEXT-09 mở màn hình theo API đã có, không chờ tất cả module mới có UI RCA.
5. **NEXT-12** để sau; không thao tác firmware/router khi chưa có thiết bị và phạm vi rõ.

Mỗi task phải có positive/negative checks và regression phù hợp, giữ frozen baselines/17 v0.1 Function digests, chỉ một shared execution Core. Không thêm WRITE hoặc nhận quyền từ JSON/model. Chỉ đánh dấu task khi có implementation và acceptance; tài liệu kế hoạch này không kích hoạt capability.

CAT-01: [profile/review đã triển khai](skill_expansion/CAT01_PROFILES.md), [machine-readable coverage](reports/CAT01_PROFILE_COVERAGE_20261116.json); runtime approvals/session vẫn thuộc CAT-02.
