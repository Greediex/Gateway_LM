# Gateway LM v2 — Kế hoạch hoàn thiện 120 Skill

Cập nhật **18/11/2026**, nhánh **v2**, baseline runtime **`2f6be0a`**.

**Mục tiêu:** phủ đủ 120 Skill bằng mô phỏng có ý nghĩa và kiểm thử qua các thành phần hiện có; người dùng hỏi bằng ngôn ngữ tự nhiên, LLM tra catalog/graph, phối hợp Skill, Core thực thi, Verifier xác minh, RCA đánh giá và LLM trả lời theo bằng chứng. Sau đó nối nguồn thật theo khả năng laptop/router. Không xây executor hoặc kiến trúc agent thứ hai.

## Quy tắc cập nhật

**Chỉ dùng `TODO.md` ở gốc repo để ghi kế hoạch, backlog, checklist và tiến độ.** Sửa trực tiếp file này, giữ mã task còn hiệu lực, bỏ mục cũ/trùng; không tạo roadmap/status/worklog/kế hoạch theo ngày song song. Tài liệu thiết kế và báo cáo chỉ ghi thiết kế/kết quả, không sao chép backlog. Chỉ tách kế hoạch khi người dùng yêu cầu rõ ràng.

Lần cập nhật này **chỉ lập kế hoạch**, không đánh dấu triển khai mới. Các batch dưới chưa được nghiệm thu 120 Skill; ba Skill replay đã có phải kiểm lại theo tiêu chí mới trước khi đánh dấu.

## Baseline và giới hạn đã biết

- Catalog: **120 Skill / 15 domain / 8 Skill mỗi domain**; mapping gồm **72 READ proposals + 40 Skill không có READ Function trực tiếp + 8 legacy references**. Một Function có thể được nhiều Skill dùng lại; không tạo 120 Function cho đủ số.
- Live laptop đã nghiệm thu trước đây: SK01/A08 scope local + 6 action laptop. Profile Skill replay hiện có B02/B03/B05. **74 workflow fixtures và 72 individual READ smoke không phải 120 Skill end-to-end.**
- Đã có Registry, ReadSession, GraphRunner, Verifier, RCAAgent, TaskRuntime, retrieval BM25/graph/semantic, checkpoint/journal và Web Trace. Các mục USE-01…05, FINALIZE-01, SIM-01 đã có nghiệm thu trong lịch sử Git/tài liệu; tái sử dụng, không làm lại.
- Qwen3:4b đã chạy Replay/ReAct `WEB-CLIENT-DNS-1`: intake và lựa chọn DNS được chấp nhận, 10 Function calls, 3 evidence IDs. Kết luận do Core dựng. **LLM tự diễn đạt câu trả lời live còn FINALIZE-02**, không coi nâng timeout là đã sửa xong.
- Qwen4B tối đa 240s/RPC; live turn 240s còn chịu hạn phiên và TTL thật. Không tăng TTL hay bỏ kiểm tra scope để làm kết quả đẹp.
- Baseline local: 855 tests, 850 pass, 5 Windows-only skips; [CI baseline đã đạt](https://github.com/Greediex/Gateway_LM/actions/runs/44217840366). Đây là kiểm chứng baseline, không phải nghiệm thu kế hoạch mới.

## “Đủ 120” được tính thế nào

| Mức | Điều kiện | Có được tính là Skill đã chạy? |
|---|---|---|
| Catalog | Có ID/tên/mô tả | Không |
| Contract reviewed | Có input/output, scope, nguồn, đơn vị, TTL, dependency, completion và quyền | Chưa |
| Simulation verified | Fixture có ý nghĩa → adapter/profile được review → Core/Verifier → output/Claim đúng; có negative cases | Có, **chỉ trong mô phỏng** |
| Laptop verified | Đọc nguồn thật trên laptop, đúng interface/client/scope, có test quyền và thiếu capability | Chỉ ghi khả năng local đã kiểm chứng |
| Router verified | Có backend/firmware thật, provenance và nghiệm thu trên thiết bị | Chỉ ghi khả năng router đã kiểm chứng |

Không ép mọi Skill thành một READ call. Skill tổng hợp dùng Function/evidence đã có, Claim hoặc workflow riêng. Skill lịch sử cần chuỗi thời gian; topology cần nhiều client/AP/router được mô phỏng. Không dùng JSON rỗng, output cố định luôn thành công hoặc nhãn lỗi gold làm evidence.

**SK13 là ngoại lệ WRITE:** phải có kịch bản approve/reject/apply/readback/rollback trong sandbox tách thiết bị thật, dùng controller hiện có. Chat chỉ được giải thích/lập kế hoạch/handoff; không cấp quyền WRITE cho LLM/Web. Chỉ phản hồi BLOCKED không đủ để đánh dấu SK13 mô phỏng hoàn chỉnh. Báo coverage riêng: READ/analysis qua chat và sandbox change workflow; không quảng bá 120 READ Skill hoặc 120 Skill tự thi hành không cần phê duyệt.

## P0 — Hoàn thiện nền dùng chung trước khi mở batch

| Xong | Task | Việc triển khai và vị trí chính | Điều kiện nghiệm thu |
|---|---|---|---|
| [x] | **COV-01 — Kiểm kê chính xác 120 ID** | `gateway_pilot/skill_expansion/coverage.py`, lệnh `python -m gateway_pilot.skill_expansion.cli coverage [--output FILE]`, test `tests/test_skill_coverage.py`. Số liệu sinh từ data + Registry v0.1 + deployment, không nhập tay. | Đạt 18/11: 120 ID, 15×8; mỗi ID có type/batch/dependency/mức hỗ trợ/gap. Kết quả: direct 70, composite 34, history 8, legacy_v01 7, change 1; contract reviewed 0, replay launchable 3 (B02/B03/B05), live launchable 2 (SK01/A08), simulation/router verified 0. laptop.* không tính vào 120. |
| [ ] | **DATA-02 — Chốt contract theo batch** | Dùng builder/loader và approval profile hiện có. Bổ sung contract được version riêng, mapping exact Function/Port versions, completion, schema, binding, scope và Claim. Giữ source/frozen baseline nguyên vẹn. | Mỗi batch build được profile có pin được review; dữ liệu không hợp lệ/foreign target/missing permission bị chặn. 40 composite có workflow/Claim, không thêm READ Function giả. |
| [ ] | **COV-02 — Bộ dữ liệu mô phỏng dùng chung** | Mở rộng có version `replay_backend.py`, fixture/profile dưới `data/skill_expansion_v1/`, `config/skill_profiles/` và examples. Tái dùng StrictSkillReplayBackend; mô phỏng client/AP/router/interface/time/config tách scope. | Có trạng thái bình thường, lỗi và thiếu dữ liệu; các counter/rate/time/topology nhất quán. Gold chỉ ở scorer. Thời gian mô phỏng khai báo rõ, không dùng clock mô phỏng để nới TTL live. Tiến độ 18/11: `data/skill_expansion_v1/simulation_v1/` (scenarios + gold tách riêng), `gateway_pilot/skill_expansion/simulation.py`, `scripts/simulate_skills.py`; COV-A direct A02/A04/A06/A08 × normal/fault/missing chạy qua Core: 12/12 khớp gold. **Chưa xong:** mới kiểm tra Core admit evidence, chưa có Claim phân biệt normal/fault (DATA-02), chưa có composite/history/topology, các batch B–O. |
| [ ] | **COV-03 — Đăng ký và gọi đủ loại Skill** | Mở rộng `runtime_bridge.py`, `deployment.py`, `application/skill_launcher.py` và TaskRuntime theo interface có sẵn; reuse ReadSession/GraphRunner/kernel. | Catalog chỉ READY khi probe/approval/profile phù hợp. Direct, composite và history thực thi đúng cùng Runner/budget; thiếu fixture báo chính xác, không fallback từ live sang replay. WRITE tiếp tục tách sandbox. |
| [ ] | **FINALIZE-02 — Qwen hoàn tất câu trả lời** | `application/skill_chat.py`, `graph_v3/ollama_goal_model.py`, `application/grounded_answer.py`: nối chế độ mô phỏng vào cùng luồng catalog/Skill/Verifier/RCA và completion hiện có, không chỉ dùng advisor của workflow cũ. | Qwen thật vừa chọn Skill vừa tạo câu trả lời được hậu kiểm. Báo riêng `used_llm`, renderer fallback, thời gian mỗi RPC, hạn lượt/phiên và proof còn hiệu lực. Hết hạn/timeout không xuất Claim hiện tại. Mô phỏng dài không thay chính sách live. Tiến độ 18/11: `skill_chat` nhận `mode=replay` cùng luồng Core/Verifier/RCA/grounded answer; `config/skill_launcher/replay.diagnostics.json` (3 workflow, 6 Claim cho B02/B03/B05); Web replay + LLM dùng luồng này khi đã duyệt; test `tests/test_skill_chat_replay.py`. **Chờ người duyệt** digest từ `python -m scripts.prepare_replay_chat_approval` vào `approvals.json`. **Chưa có:** chạy Qwen thật trên laptop và ghi `answer_synthesis.used_llm`; fixture replay v2 vẫn là giá trị `demo`. Chế độ nhanh (mặc định Web, tắt bằng `GATEWAY_LM_CHAT_FAST=0`): câu hỏi rõ ràng định tuyến bằng phrase/BM25+graph tới action đã duyệt, **0 lần gọi LLM**; câu mơ hồ tối đa **1** lần chọn Skill; không gọi LLM diễn đạt câu trả lời. Test `tests/test_skill_chat_fast.py`. Chưa đo thời gian thật trên laptop. |
| [ ] | **CHAT-01 — Hỏi tự nhiên và chọn tiếp khi thiếu** | Dùng retrieval/graph + TaskDecomposer/BoundedGoalProposer + RCAAgent trong session. Thêm câu hỏi đa ý, tiếp nối, thiếu target, ngoài catalog, prompt injection. | Thiếu evidence thì chọn Skill bổ sung hoặc hỏi lại; không dừng sau một Skill, không chạy hết 120 Skill cho mọi câu. Câu ngoài phạm vi vẫn phản hồi rõ giới hạn, không bịa kết quả. |
| [ ] | **COV-04 — Graph có dependency thật** | Dùng `edge_gate.py`, `review.py`, `profiles.py`; review 203 proposed edges và đối chiếu 3 legacy references. | Mỗi edge có quyết định review và lý do; chỉ supplier/consumer đúng port/version/scope mới thành DATA/STATE/ORDER. Affinity chỉ dùng retrieval, không ép vào DAG; không yêu cầu duyệt hết edge. |
| [ ] | **DATA-01 — Nối nguồn laptop phù hợp** | `adapters/laptop_skills.py`, contracts/actions/profile local. Ưu tiên C02/G04: counter RX/TX, error/drop, link rate nếu OS/driver cung cấp; lấy mẫu theo thời gian khi cần. | Phân biệt counter tổng, delta, rate và tốc độ liên kết; chỉ nói interface laptop, không thay số đo port router. Không dùng signal % làm RSSI/SNR hoặc link rate làm throughput. Thiếu quyền/driver báo riêng, không gắn REQUIRES_ROUTER_BACKEND cho toàn bộ phần local có thể đọc. |
| [ ] | **UI-01 — Coverage và lỗi dễ hiểu** | API/Web launcher/chat/Trace đọc coverage runtime; source badge và availability theo từng backend/profile, không phải theo tên Skill cố định. | Tách `NOT_RUN`, lỗi tool, `EXPIRED`, thiếu capability, sai scope, unsupported, model timeout; thống kê 120 có mẫu số đúng và không tính BLOCKED là thành công. Hiện nguồn mô phỏng/live và từng phần yêu cầu chưa đáp ứng. |

Mỗi task có negative-path test đúng ranh giới, chạy test fail trước bản sửa khi phù hợp, thực thi qua Core rồi xác minh và commit batch nhỏ lên `v2`. Chỉ cập nhật approval sau review semantic/schema; không cập nhật hash tự động để ép test xanh.

## Giao việc cho Codex (điều phối: Claude)

Codex thực hiện từng gói **WP** dưới đây theo thứ tự; Claude review trước khi đánh dấu. Mỗi gói một nhánh con từ `v2` (`codex/<wp-id>`), commit nhỏ, không sửa `main`.

**Quy tắc chung cho mọi WP** (bắt buộc, cùng khối KHÓA trong `CLAUDE.md`):
- Không sửa khối `LOCKED-CRITERIA`, `LOCKED_CRITERIA_SHA256`, `data/frozen_manifest.json`, fixture frozen, báo cáo lịch sử.
- **Không ghi `config/skill_launcher/approvals.json`.** Gói nào cần digest mới thì in digest đề xuất bằng script, để người duyệt ghi.
- Không xóa/skip/làm yếu test; interface mới phải có negative test (sai target/scope, thiếu quyền, response hỏng, timeout, fact hết hạn).
- Mọi thực thi đi qua `execute_ready_once`/`GraphRunner.step`; không thêm đường WRITE; gold chỉ ở scorer.
- Trước khi báo xong: `python -m scripts.check_project`, `python -m unittest discover -s tests`, `python -m scripts.simulate_skills`, `python -m gateway_pilot.skill_expansion.cli coverage`; dán số pass/skip và output coverage vào mô tả.

| Xong | WP | Việc | Đầu ra / nghiệm thu | Ai |
|---|---|---|---|---|
| [ ] | **WP-A1 — Claim batch A** | Thêm Claim có version cho A02/A04/A06/A08 (vd. `inventory_empty`, `oui_unknown`, `ip_mac_conflict`, `client_not_associated` + bản HEALTHY), theo định dạng `replay.diagnostics.json`, file mới `config/skill_launcher/replay_a.diagnostics.json`. Mở rộng `scripts/simulate_skills.py` để chấm verdict Claim (FAULT/HEALTHY/UNKNOWN) với gold tách riêng `simulation_v1/gold_claims_v1.json`. | 12 kịch bản: normal→HEALTHY, fault→FAULT, missing→UNKNOWN/NOT_READY; test phủ ngưỡng biên và fact hết hạn. | Codex |
| [ ] | **WP-A2 — Profile đa domain / đa scope** | Mở rộng `skill_expansion/profiles.py` để một profile replay chứa nhiều domain **cùng scope** (giữ chặn khác scope). Không đổi hành vi profile v1 (test cũ giữ nguyên). | Profile v1 vẫn hợp lệ, digest không đổi; profile mới gộp A02 (gateway) + B02/B03/B05 qua được validator; profile trộn scope bị từ chối. | Codex |
| [ ] | **WP-A3 — Deployment replay client** | Deployment replay scope `client` cho A04/A06/A08 (identity dependency khai báo đúng như `core_replay_smoke_v2`), fixture lấy từ `simulation_v1` trạng thái normal. Script in digest đề xuất (giống `prepare_replay_chat_approval.py`). | `composition('replay_client')` hoặc tương đương chạy được trong test với approval giả lập; production vẫn tắt tới khi người duyệt ghi digest. | Codex |
| [ ] | **WP-A4 — Composite A03/A05/A07** | Workflow + Claim cho Skill tổng hợp dựa trên evidence đã có (A03 = inventory+identity, A05 = inventory+vendor, A07 = inventory+history), không tạo READ Function giả. A07 cần chuỗi thời gian ≥2 mẫu mô phỏng. | Mỗi composite có kịch bản normal/fault/missing qua Core; thiếu một nguồn → UNKNOWN, không suy diễn. | Codex |
| [ ] | **WP-A5 — Coverage ghi nhận nghiệm thu** | Thêm nguồn nghiệm thu có version cho `coverage.py` (vd. `simulation_v1/acceptance.json` sinh từ `simulate_skills`, không nhập tay) để `simulation_verified` tăng **chỉ khi** Skill có đủ normal/fault/missing qua Core + Claim đúng. | `cli coverage` báo đúng số Skill batch A đạt; sửa tay acceptance mà không khớp kết quả chạy → fail. | Codex |
| [ ] | **WP-L1 — Đo Qwen thật trên laptop** | Chạy Web live (`./web_gateway/start_linux.sh`) với `qwen3:4b`; 10 câu hỏi (rõ ràng/mơ hồ/WRITE/ngoài phạm vi); ghi `routing`, `model_calls`, `timings_ms`, `answer_synthesis`, `case_status`. Thử thêm `GATEWAY_LM_CHAT_FAST=0` để so sánh. | Bảng kết quả (không kèm định danh người dùng/capture mạng) gửi Claude để chỉnh; ghi tóm tắt số liệu vào FINALIZE-02. | Người dùng / Codex trên laptop |
| [ ] | **WP-R1 — Duyệt digest** | Đọc `replay.diagnostics.json` (+ file của WP-A1/A3 khi có), chạy script in digest, ghi vào `approvals.json` trong commit riêng. | Commit do người duyệt; Claude kiểm lại digest khớp. | **Người duyệt** |

Tiến độ WP-A1 (18/11/2026, `codex/wp-a1`, chờ review; giữ nguyên checkbox): thêm `replay_a.diagnostics.json` v1.0.0 với 9 Claim cho A02/A04/A06/A08 (gồm hostname conflict riêng), gold Claim tách biệt; scorer đánh giá bằng ClaimBook trên CaseState do Core tạo. Kiểm tra local bằng `.venv-graph/bin/python`: check_project PASS; unittest 891 tổng / 886 pass / 0 fail / 5 skip Windows-only; simulate_skills 12/12 pass; 14 test tập trung pass. Coverage: total/catalog 120; type change 1, composite 34, direct 70, history 8, legacy_v01 7; contract_reviewed 0, replay_launchable 3, live_launchable 2, simulation_verified 0, router_verified 0; COV-A…O mỗi batch 8. Chỉ kiểm chứng synthetic, chưa nghiệm thu deployment/coverage WP-A5. Digest đề xuất: `328f982bc4671e4986d771f3ed772f3014d5e1962e8ced1672ea079ef055e7c9`; không ghi approvals. Không có CI run mới vì không push. Commit đang chờ danh tính tác giả Git (user.name/user.email chưa cấu hình).

Tiến độ WP-A2 (18/11/2026, `v2`, chờ review; giữ nguyên checkbox): thêm format `gateway-lm.skill-profile/v2` với `domains` là danh sách không rỗng, không trùng và khớp chính xác domain của các Skill được chọn; vẫn bắt buộc cùng scope. Profile mới `inventory_wifi_gateway_replay_v2.json` chọn A02+B02/B03/B05 scope gateway; metadata vẫn PROPOSED, không cấp quyền chạy. V1 giữ nguyên validator semantics và canonical digest `9b3d15ed7dc9d3e1e55f439397e9793982d6d1a276d3309016cb661ddce94862`. Đã chạy bằng `.venv-graph/bin/python`: 21 test profile pass; check_project PASS; simulate_skills 12/12 pass; core_replay_smoke_v2 72/72 pass. Unittest toàn repo: 898 tổng / 893 pass / 0 fail / 5 skip (Windows-only), 183.473s. Coverage CLI: total/catalog 120; by_type change 1, composite 34, direct 70, history 8, legacy_v01 7; contract_reviewed 0, replay_launchable 3, live_launchable 2, simulation_verified 0, router_verified 0; COV-A…O mỗi batch 8. Đây là kiểm chứng metadata/synthetic, chưa phải nghiệm thu deployment hay phần cứng. Không ghi approvals, không đổi source/frozen fixtures. Không có CI run mới vì không push.

Tiến độ WP-A3 (18/11/2026, `v2`, chờ review; giữ nguyên checkbox): thêm deployment `replay_client` cho A04/A06/A08 scope client, catalog synthetic riêng với dependency DATA `client.identity` do Core xác minh; dùng fixture normal từ `simulation_v1`, không đọc gold trong runtime. `composition('replay_client')` chạy với approval giả lập trong test; cấu hình thật vẫn bị chặn `skill_deployment_not_approved`. Script `.venv-graph/bin/python -m scripts.prepare_replay_client_approval` chỉ in đề xuất, không ghi approvals; registry artifact chỉ nằm trong `runs/`. Chưa mở mode này cho Web/chat, chưa nghiệm thu phần cứng. Đã chạy local bằng `.venv-graph/bin/python`: check_project PASS; unittest toàn repo 905 tổng / 900 pass / 0 fail / 5 skip Windows-only (182.623s); 7 test WP-A3 pass, gồm sai target/scope, thiếu quyền, schema hỏng, timeout, identity sai, fact hết hạn, fixture/pin drift và production chưa duyệt; simulate_skills 12/12 pass; core_replay_smoke_v2 72/72 pass. Coverage CLI: total/catalog 120; by_type change 1, composite 34, direct 70, history 8, legacy_v01 7; contract_reviewed 0, replay_launchable 3, live_launchable 2, simulation_verified 0, router_verified 0; COV-A…O mỗi batch 8. Digest đề xuất: registry `bed7956e9d955b982f751570b7e83709ad05192ccfc3e4166e47c77b0f9022d9`, actions `33a980221f424b9373e6a4c1c20935057b21b3d0a3bba10ea2c13af133e87843`, fixtures `966d99b5ff2e190e4a119980235bbaa8cba08d082a4186743d3579e6ff60f9f2`. Không ghi approvals, không đổi frozen/source fixtures, không có CI run mới vì không push.

Sau khi WP-A1…A5 đạt: Claude review, đánh dấu Batch COV-A, rồi tạo WP cho COV-B theo cùng mẫu.

## 15 batch — danh sách nghiệm thu đủ 120 Skill

Mỗi checkbox bên dưới là **nghiệm thu mô phỏng của cả batch**, không phải đánh dấu catalog tồn tại. Dùng ID gốc (gồm SKxx legacy), không đổi tên thành 120 ID mới. Từng ID phải được ghi kết quả riêng trong coverage được sinh từ kiểm thử.

### COV-A — A: Identity & Inventory · 8 Skill

- [ ] **Batch COV-A** · Ưu tiên: P0. Phụ thuộc: COV-01…03.

Identity, inventory, OUI, lifecycle và association có target/time rõ; đối chiếu IP–MAC–hostname bằng nguồn độc lập.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK01` | Xác định client đích |
| `A02` | Kiểm kê thiết bị trong mạng |
| `A03` | Chuẩn hóa và gộp định danh thiết bị |
| `A04` | Nhận diện hãng từ MAC/OUI |
| `A05` | Phân loại loại thiết bị |
| `A06` | Đối chiếu IP–MAC–hostname |
| `A07` | Theo dõi vòng đời thiết bị |
| `A08` | Theo dõi thiết bị gắn với AP |

### COV-B — B: Wi-Fi & RF · 8 Skill

- [ ] **Batch COV-B** · Ưu tiên: P0. Phụ thuộc: A, COV-02…04.

RSSI/SNR đúng đơn vị, airtime/kênh, roaming timeline và mesh nhiều AP; không quy RSSI yếu thành nguyên nhân duy nhất.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK02` | Chẩn đoán kết nối Wi-Fi |
| `B02` | Trạng thái radio và SSID |
| `B03` | Kiểm tra cấu hình SSID |
| `B04` | Đánh giá RSSI/SNR/chất lượng liên kết |
| `B05` | Theo dõi airtime và sử dụng kênh |
| `B06` | Phân tích nhiễu và trùng kênh |
| `B07` | Chẩn đoán roaming |
| `B08` | Chẩn đoán mesh/backhaul |

### COV-C — C: Ethernet & Layer 2 · 8 Skill

- [ ] **Batch COV-C** · Ưu tiên: P0. Phụ thuộc: A, COV-02…04.

Port/counter/link rate, FDB/bridge/VLAN/STP/MTU; vòng lặp L2 cần nhiều bằng chứng, không suy từ một counter.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `C01` | Trạng thái cổng Ethernet |
| `C02` | Lỗi RX/TX và tốc độ liên kết |
| `C03` | Bảng MAC/FDB của switch |
| `C04` | Sức khỏe bridge |
| `C05` | Phân tích membership VLAN |
| `C06` | Phát hiện dấu hiệu vòng lặp L2 |
| `C07` | Kiểm tra STP/RSTP |
| `C08` | Phát hiện bất tương thích MTU |

### COV-D — D: IP, DHCP & IPv6 · 8 Skill

- [ ] **Batch COV-D** · Ưu tiên: P0. Phụ thuộc: A, COV-02…04.

IPv4/DHCP lease/pool, duplicate IP, neighbor, IPv6 RA/SLAAC/DHCPv6; dữ liệu client/gateway không trộn scope.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK03` | Chẩn đoán DHCP và IPv4 |
| `D02` | Theo dõi vùng cấp phát DHCP |
| `D03` | Theo dõi vòng đời DHCP lease |
| `D04` | Phát hiện xung đột địa chỉ IP |
| `D05` | Phân tích ARP/neighbor cache |
| `D06` | Chẩn đoán IPv6 RA/SLAAC |
| `D07` | Chẩn đoán DHCPv6 |
| `D08` | Xác minh subnet/prefix/gateway |

### COV-E — E: WAN & Internet · 8 Skill

- [ ] **Batch COV-E** · Ưu tiên: P0. Phụ thuộc: A/C/D.

WAN link/route, PPPoE/upstream, NAT/CGNAT, multi-WAN và gián đoạn; đối chiếu probe theo đường/interface.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK04` | Chẩn đoán kết nối WAN |
| `E02` | Theo dõi vật lý/link WAN |
| `E03` | Xác minh default route WAN |
| `E04` | Chẩn đoán PPPoE/DHCP upstream |
| `E05` | Phát hiện NAT/CGNAT |
| `E06` | Chẩn đoán multi-WAN/failover |
| `E07` | Phân tích WAN chập chờn |
| `E08` | Kiểm chứng reachability thượng nguồn |

### COV-F — F: DNS & Core Services · 8 Skill

- [ ] **Batch COV-F** · Ưu tiên: P0. Phụ thuộc: A/D/E.

So sánh DNS client/router/upstream, resolver/cache/split-horizon/DNSSEC/DoT/DoH/NTP; DNS tốt không chứng minh HTTPS tốt.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK05` | Chẩn đoán phân giải DNS |
| `F02` | So sánh chất lượng DNS resolver |
| `F03` | Theo dõi trạng thái DNS cache |
| `F04` | Chẩn đoán split-horizon DNS |
| `F05` | Kiểm tra DNS option từ DHCP |
| `F06` | Kiểm tra trạng thái DNSSEC |
| `F07` | Quan sát cấu hình DoT/DoH |
| `F08` | Chẩn đoán đồng bộ giờ NTP |

### COV-G — G: Performance & QoS · 8 Skill

- [ ] **Batch COV-G** · Ưu tiên: P1. Phụ thuộc: B/C/E/F.

Latency/loss/jitter, RX/TX/throughput, băng thông/SQM và bufferbloat; mô phỏng tải có chặn, không tự chạy load test live.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `G01` | Độ trễ và mất gói |
| `G02` | Phân tích jitter |
| `G03` | Đánh giá throughput có kiểm soát |
| `G04` | Thống kê lưu lượng từng interface |
| `G05` | Xác định điểm tiêu thụ băng thông |
| `G06` | Phân tích bufferbloat |
| `G07` | Kiểm tra chính sách QoS/SQM |
| `G08` | Khoanh vùng tắc nghẽn |

### COV-H — H: Router/System Health · 8 Skill

- [ ] **Batch COV-H** · Ưu tiên: P1. Phụ thuộc: COV-02…03.

Tài nguyên/service/storage/kernel/driver/nhiệt/reboot/firmware-readiness; readiness chỉ là đánh giá, không cập nhật firmware.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK08` | Sức khỏe tài nguyên gateway |
| `H02` | Tình trạng dịch vụ và tiến trình |
| `H03` | Theo dõi dung lượng và wear lưu trữ |
| `H04` | Phân tích log kernel và hệ thống |
| `H05` | Giám sát nhiệt độ thiết bị |
| `H06` | Kiểm tra driver/interface |
| `H07` | Phân tích reboot/crash |
| `H08` | Đánh giá sẵn sàng cập nhật firmware |

### COV-I — I: Security & Segmentation · 8 Skill

- [ ] **Batch COV-I** · Ưu tiên: P1. Phụ thuộc: A/B/C/D/H.

Firewall/exposure/isolation/encryption/auth/segmentation/compliance; nguồn mô phỏng không chứa secret, không tự quét mạng ngoài.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `I01` | Kiểm tra chính sách firewall (READ) |
| `I02` | Kiểm tra dịch vụ/cổng phơi lộ |
| `I03` | Đánh giá guest/client isolation |
| `I04` | Kiểm tra chuẩn mã hóa Wi-Fi |
| `I05` | Kiểm tra cấu hình xác thực quản trị |
| `I06` | Xác minh phân đoạn mạng/VLAN |
| `I07` | Phát hiện bất thường client có giải thích |
| `I08` | Kiểm toán tuân thủ cấu hình |

### COV-J — J: VPN & Remote Connectivity · 8 Skill

- [ ] **Batch COV-J** · Ưu tiên: P1. Phụ thuộc: D/E/F/I.

VPN tunnel/peer/routes/IPv6/PBR/remote-access; DNS leak và site-to-site cần đối chiếu nhiều nguồn/đường đi.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `J01` | Kiểm tra sức khỏe VPN tunnel |
| `J02` | Xác minh định tuyến qua VPN |
| `J03` | Phân tích dấu hiệu DNS leak |
| `J04` | Kiểm tra reachability của VPN peer |
| `J05` | Chẩn đoán VPN site-to-site |
| `J06` | Kiểm tra IPv6 qua VPN |
| `J07` | Chẩn đoán policy-based routing |
| `J08` | Chẩn đoán truy cập từ xa |

### COV-K — K: History, Monitoring & Incidents · 8 Skill

- [ ] **Batch COV-K** · Ưu tiên: P1. Phụ thuộc: A và snapshot/checkpoint/journal hiện có.

Chuỗi evidence có clock, trend/alert/dedup/incident/recovery/retention; không tự tạo lịch sử từ một snapshot hoặc coi hết alert là phục hồi.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `K01` | Lịch sử Verified Evidence |
| `K02` | Phân tích xu hướng theo thời gian |
| `K03` | Quy tắc tạo cảnh báo |
| `K04` | Chống cảnh báo trùng |
| `K05` | Dựng timeline sự cố |
| `K06` | Phát hiện khoảng mất kết nối |
| `K07` | Xác minh trạng thái phục hồi |
| `K08` | Chính sách TTL và lưu trữ lịch sử |

### COV-L — L: Topology & Multi-Gateway · 8 Skill

- [ ] **Batch COV-L** · Ưu tiên: P1. Phụ thuộc: A/B/C/D/E và K.

Topology nhiều client/AP/router/site; mỗi cạnh có provenance/thời gian và scope, thiếu dữ liệu để unknown thay vì bịa quan hệ.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `L01` | Khám phá topology theo dữ liệu quan sát |
| `L02` | Ánh xạ client–AP–router |
| `L03` | Ánh xạ uplink/gateway |
| `L04` | Truy vết đường đi của client |
| `L05` | Bản đồ subnet/VLAN |
| `L06` | Tổng hợp sức khỏe theo site |
| `L07` | So sánh nhiều gateway |
| `L08` | Ước lượng phạm vi ảnh hưởng sự cố |

### COV-M — M: Evidence & Adaptive Diagnosis · 8 Skill

- [ ] **Batch COV-M** · Ưu tiên: P0 xuyên suốt; chốt sau A…L. Phụ thuộc: COV-03…04, RCA/Claim Engine hiện có.

Hypothesis ranking, gap, adaptive measurement, multi-source/cross-client, giải thích evidence; tách quan sát, tương quan và causal Claim.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK09` | Tương quan và kiểm chứng bằng chứng |
| `M02` | Xếp hạng giả thuyết RCA |
| `M03` | Nhận diện bằng chứng còn thiếu |
| `M04` | Chọn phép đo bổ sung thích ứng |
| `M05` | Phân biệt quan sát và nguyên nhân |
| `M06` | Chẩn đoán đối chiếu nhiều nguồn |
| `M07` | Liên kết sự cố nhiều thiết bị |
| `M08` | Giải thích kết luận kèm evidence ID |

### COV-N — N: Change & Guided Remediation · 8 Skill

- [ ] **Batch COV-N** · Ưu tiên: P1; sandbox riêng. Phụ thuộc: H/I/K/L/M và transaction controller hiện có.

Impact/config snapshot/drift/approval/dry-run/readback/rollback/guidance; SK13 thử sandbox approve/reject/in-doubt, không WRITE thiết bị thật.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `SK13` | Áp dụng và xác minh cấu hình có phê duyệt |
| `N02` | Phân tích tác động trước thay đổi |
| `N03` | Snapshot cấu hình (READ) |
| `N04` | Phát hiện configuration drift |
| `N05` | Theo dõi phê duyệt thay đổi |
| `N06` | Lập kế hoạch dry-run |
| `N07` | Xác minh rollback/readback |
| `N08` | Hướng dẫn khắc phục không tự WRITE |

### COV-O — O: Composite Troubleshooting Skills · 8 Skill

- [ ] **Batch COV-O** · Ưu tiên: P0 nghiệm thu cuối. Phụ thuộc: A…M; N08 cho hướng dẫn.

Bài toán tổng hợp nhiều Skill, tiếp tục đo khi thiếu, dừng hữu hạn; hướng dẫn xử lý tương ứng bằng chứng, không chỉ trả danh sách số đo.

| ID | Skill cần nghiệm thu mô phỏng |
|---|---|
| `O01` | Điều tra client có Wi-Fi nhưng mất Internet |
| `O02` | Điều tra Wi-Fi chậm |
| `O03` | Điều tra mạng chập chờn |
| `O04` | Điều tra lỗi DNS theo thiết bị |
| `O05` | Điều tra IoT/camera mất kết nối |
| `O06` | Điều tra gọi video/VoIP giật |
| `O07` | Điều tra mất Internet diện rộng |
| `O08` | Điều tra bất thường nhiều client |

## Definition of Done cho từng Skill

1. **Contract:** exact ID/version, input/output/completion, nguồn, unit, scope/target, TTL, permission/budget và dependency được review; composite có Claim/workflow và không nhân bản Function sẵn có.
2. **Fixture:** ít nhất 6 kịch bản phù hợp ngữ nghĩa: bình thường/hoàn thành hợp lệ, sự cố hoặc giá trị bất thường, thiếu dữ liệu, evidence cũ hoặc sai thứ tự thời gian, sai scope/quyền, dữ liệu mâu thuẫn hoặc tool lỗi. Với lookup dùng not-found/unknown; với SK13 dùng approve/reject/failure/readback mismatch/in-doubt/rollback. Không bịa “fault” cho lookup.
3. **Execution:** chạy qua API/CLI/launcher phù hợp → shared session/kernel/GraphRunner → Verifier. Không inject raw facts để vượt dependency/ACL. Lưu Function calls, plan, evidence IDs, provenance, stop reason và budget; ghi rõ simulator output.
4. **Answer/RCA:** trả đúng phần câu hỏi bằng evidence; diagnostic Claim chỉ khi đủ điều kiện TRUE. Thiếu dữ liệu phải partial/unknown; đo xong không đồng nghĩa đã khôi phục. SK13 là sandbox có approval, không thử WRITE từ chat.
5. **Regression:** direct, composite và history có kiểm thử riêng; API/Trace phản ánh đúng lỗi và coverage. Checked batch chỉ khi cả 8 Skill đạt, không dùng tỷ lệ trung bình để che một Skill chưa chạy.

## COV-EVAL — Nghiệm thu 120 Skill và Qwen thật

- [ ] **COV-EVAL-01 — Coverage tất định:** đúng 120/120 ID có contract và scenario harness; ít nhất 720 kịch bản theo Definition of Done, không coi unit test count là scenario count. Báo từng Skill và từng mode; READ/chat và sandbox SK13 tách riêng. Không chấp nhận placeholder hoặc chỉ BLOCKED làm “đã mô phỏng”.
- [ ] **COV-EVAL-02 — LLM end-to-end:** test set độc lập tối thiểu 2 cách hỏi/Skill (240), thêm 60 đa ý/tiếp nối và 60 ngoài phạm vi/injection = tối thiểu 360 câu/chuỗi. Prompt không nhận gold/diagnosis labels. SK13 đánh giá route/approval handoff, không phát lệnh WRITE. Qwen3:4b thật, pin model digest/runtime/profile/seed; không thay bằng test double khi báo chất lượng LLM.
- [ ] **COV-EVAL-03 — Ngưỡng chất lượng:** chốt trước khi tune: selection theo nhóm Skill hợp lệ ≥90%; trả đủ các phần có dữ liệu ≥95%; mọi nhóm Skill phải có kết quả riêng; không có unsafe WRITE, live/replay confusion hoặc evidence sai target/hết hạn được chấp nhận trong suite. Độ đúng RCA và abstention báo riêng, không gộp với lookup/retrieval; fail phải giữ nguyên, không sửa gold để đạt.
- [ ] **COV-EVAL-04 — Latency và lỗi:** đo cold/warm, p50/p95, RPC/total time, tool calls, CPU/RAM và tỷ lệ timeout/fallback theo mode/domain. Giữ bound 240s/RPC, budget calls/rounds/session và giới hạn đồng thời; bài dài partial rõ ràng. Tách LLM hoàn tất chọn bước, LLM synthesis được chấp nhận và renderer fallback. Không gọi inference time bị cắt là latency thành công.
- [ ] **COV-EVAL-05 — EVAL1000:** dùng lại pack/harness đã có, pin nguyên dataset và split, không tune trên test/frozen data. Báo riêng catalog retrieval, Function selection, RCA/answer và latency; không nhập điểm smoke/model double thành accuracy Qwen.
- [ ] **COV-EVAL-06 — Release v2:** chạy `python -m scripts.check_project`, `python -m unittest discover -s tests -v`, `python -m scripts.core_replay_smoke_v2 --synthetic-only --all`, DOM/API và scenario suite theo batch. Ghi CI URL, runtime SHA, skip/fail, model/profile pins; cập nhật README/coverage rồi đẩy `v2`. Chỉ đánh dấu simulation 120 khi đủ điều kiện; laptop/router live vẫn có cột coverage riêng.

## Thứ tự triển khai

1. **COV-01 → DATA-02/COV-02 → COV-03.** Làm hai lát cắt hoàn chỉnh đầu tiên: C02/G04 (RX/TX đúng scope) và O04 (DNS đa nguồn) để kiểm cả direct và composite; batch chứa chúng chỉ đánh dấu khi đủ 8 Skill.
2. **FINALIZE-02 + CHAT-01 + COV-04 + UI-01** chạy theo các lát cắt đầu tiên, rồi áp dụng cùng luồng cho mọi batch. DATA-01 nối các phần laptop có nguồn thật, không chờ 120 mô phỏng mới sửa lỗi availability local.
3. **A → B/C/D → E/F → G/H → I/J → K/L → chốt M → N → O.** M được nối sớm bằng RCA/Verifier hiện có; hoàn thiện 8 Skill M sau khi có các nguồn liên quan. Không chạy một Skill composite trước dữ liệu prerequisite của nó.
4. **COV-EVAL-01…06** nghiệm thu từng batch rồi toàn bộ. Không chờ đến cuối mới phát hiện Skill chỉ có metadata.
5. **Thiết bị thật:** batch laptop nào đạt thì công bố đúng phạm vi local; OpenWrt/Ubus, multi-gateway và firmware acceptance thực hiện sau, trên backend/thiết bị được cấp quyền. Đạt 120 mô phỏng không tự cho phép bật router/WRITE/cloud.

## Thành phần tái sử dụng và vị trí sửa khi triển khai

| Công việc | Điểm sửa chính |
|---|---|
| Catalog/mapping/contracts/profile/coverage | `data/skill_expansion_v1/`, `examples/skill_deployments/`, `config/skill_profiles/`, `config/skill_launcher/`, `gateway_pilot/skill_expansion/{profiles,deployment,runtime_bridge,edge_gate}.py`, `scripts/skill_profiles.py` |
| Fixture và READ adapter | `gateway_pilot/skill_expansion/replay_backend.py`, `gateway_pilot/adapters/laptop_skills.py`, builder/binding/capability interface hiện có |
| Chọn Skill và trả lời | `gateway_pilot/application/{skill_chat,skill_launcher,grounded_answer}.py`, `gateway_pilot/graph_v3/{ollama_goal_model,task_runtime,rca_agent}.py` |
| History/topology/Claim/change sandbox | snapshot/checkpoint/journal, Claim Engine, graph registry và WRITE transaction controller đã có; bổ sung domain data theo interface, không thay shared executor |
| UI/API | `web_gateway/server.py`, `web_gateway/static/`; source/mode/coverage/availability lấy từ runtime |
| Tests | mở rộng `tests/test_skill_profiles.py`, `tests/test_skill_launcher.py`, `tests/test_skill_chat*.py`, `tests/test_grounded*.py`, `tests/graph_v3/`, `tests/web/`; fixture suite có version và scorer độc lập |

[Catalog 120 Skill](docs/skill_expansion/SKILLS_120.md) · [Mapping nguồn](docs/skill_expansion/SKILL_FUNCTION_MAPPING_120.md) · [Luồng LLM–Skill–RCA](docs/LLM_SKILL_CHAT.md) · [Launcher/session](docs/LAPTOP_SKILL_LAUNCHER.md)
