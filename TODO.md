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
- Tiến độ CHAT-CONCISE — Chat laptop ở fast mode ưu tiên phép đo theo chủ đề. Câu WAN nêu phạm vi quyền đọc và các giới hạn nằm trong chi tiết phép đo.
- Tiến độ REPLAY-SIM — Chat Web dùng 101 Skill lấy từ acceptance với các kịch bản normal/fault/missing, qua Core và Claim Engine. Đã đối chiếu 303/303 verdict mô phỏng bằng approval trong bộ nhớ. Unittest local 1096 pass, 0 fail, 5 skip Windows. Deployment chờ chủ dự án duyệt digest từ `.venv-graph/bin/python -m scripts.prepare_replay_sim_approval`.

## IGATE-PARITY

- Mô phỏng iGate trong `replay_sim` với năm Skill đọc qua Core, câu trả lời tức thì, kho kiến thức song ngữ và 11 loại đề xuất lệnh theo hợp đồng firmware. Theo dõi kết quả iGate riêng khỏi coverage 120 Skill.
- Sau giai đoạn mô phỏng, đối chiếu schema, nguồn dữ liệu và ngân sách trên router thật. Mọi quyền triển khai và kiểm chứng phần cứng cần một đợt nghiệm thu riêng.

Tiến độ IGATE-PARITY-1 (20/11/2026, `v2`) — Năm Skill IG01–IG05 có 15/15 kịch bản khớp gold qua Core. Coverage riêng `igate_simulated` có 5 Skill. HTTP localhost với approval giả lập đo 30 lượt hỏi nhanh, trung vị 49,064 ms và tối đa 173,020 ms. Đã kiểm tra 11 đề xuất lệnh chỉ hiển thị. Unittest 1.116 tổng, 1.111 pass, 0 fail, 5 skip Windows, 337,548 s. Hai kiểm tra Node và script in pin PASS. Pin `igate_digest` chờ duyệt là `9883919316a93befe57fad38aae54472594faf112abf6071cd48242bfbb5557b`. `check_project` báo 51 lỗi do quy tắc cấm theo dõi file dưới `third_party/` bao gồm gói vendor iGate. Chưa có run CI và chưa nghiệm thu phần cứng.

Tiến độ IGATE-INCIDENTS (20/11/2026, `v2`) — Replay 14/14 sự cố, 36/36 câu tiếng Việt chọn đúng Skill và trả `FAULT` đúng Claim qua Core với approval giả lập. Web thêm 14 lựa chọn tiếng Việt và khuyến nghị kèm nguồn. Ma trận 1.582 lượt giữ coverage 101/120. Pin `incident_scenarios_digest` chờ chủ dự án duyệt. [Báo cáo replay sự cố](docs/reports/IGATE_INCIDENTS_REPLAY_V1.md)

Tiến độ TRIAGE-01 (20/11/2026, `v2`) — Web Replay thêm luồng đóng vai khách hàng với seed 14 nhóm, đề xuất tối đa 6 thẻ và chỉ chạy các Skill đã chọn qua Core trong phiên hiện tại. 14/14 kịch bản sự cố trả `FAULT` có bằng chứng khi chạy ba thẻ mặc định. Unittest 1.149 tổng, 1.144 pass, 0 fail, 5 skip Windows (472,534 s). `check_project`, hai kiểm tra Node và Chromium desktop/mobile PASS. Scorer đạt 303/303 kịch bản Skill và 21/21 kịch bản kiểm tra sự cố. Cả 10 giá trị pin replay khớp approval hiện hành. Commit local, chưa có CI riêng. [CI của commit nền](https://github.com/Greediex/Gateway_LM/actions/runs/44690676549)

Tiến độ ADVICE-01 (20/11/2026, `v2`) — Replay có mục “Cần làm gì” cho FAULT, HEALTHY và UNKNOWN. Có diễn giải tiếng Việt cho 271/271 Claim, gồm 244 mục mới và 27 mục có sẵn. Role-play hiển thị 15 kịch bản nhất quán và nút chạy các thẻ còn lại khi kết quả bình thường. Unittest 1.156 tổng, 1.151 pass, 0 fail, 5 skip Windows (461,923 s). `check_project`, hai kiểm tra Node và Chromium desktop/mobile PASS. Scorer đạt 303/303 kịch bản Skill và 21/21 kịch bản kiểm tra sự cố. 10/10 pin khớp approval hiện hành. Commit local, chưa có CI riêng. [CI của commit nền `a7f97d8`](https://github.com/Greediex/Gateway_LM/actions/runs/44705437165)

Tiến độ EVAL-01 (26/11/2026, `v2`) — Bộ đánh giá có 250 mô tả tiếng Việt (151 dev, 99 test khóa SHA-256), nhãn AI chờ duyệt. Baseline tắt LLM đạt top-3 27/132 dev và 13/80 test. Replay dev có 7/45 `FAULT` kèm bằng chứng và 0/45 `FAULT` trên đối chứng `normal`. Unittest 1.164 tổng, 1.159 pass, 0 fail, 5 skip Windows (425,997 s). `check_project` và hai kiểm tra Node PASS. Scorer mô phỏng đạt 303/303 kịch bản Skill và 21/21 kịch bản kiểm tra sự cố. 10/10 pin khớp approval. Commit local, chưa có CI riêng. [Báo cáo v1](docs/reports/TRIAGE_EVAL_V1.md) · [CI của `v2` tại `a7f97d8`](https://github.com/Greediex/Gateway_LM/actions/runs/44705437165)

Tiến độ TRIAGE-02 (26/11/2026, `v2`) — Role-play chuẩn hóa tiếng Việt, xen kẽ thẻ READ theo nhóm và hỏi lại bằng chip trong cùng phiên. Top-3 tất định tăng từ 27/132 lên 126/132 trên dev và giảm từ 13/80 xuống 10/80 trên test khóa, với 41 từ chối sai trên test. Hệ thống chấp nhận đề xuất từ Qwen3:4b ở 1/23 lượt gọi và top-3 dev giữ ở 126/132. Unittest 1.169 tổng, 1.164 pass, 0 fail, 5 skip Windows. Hai kiểm tra Node và `check_project` PASS. Scorer đạt 303/303 kịch bản Skill và 21/21 kiểm tra sự cố. 10/10 pin replay khớp approval. Commit local, chưa có CI riêng. [Báo cáo V2](docs/reports/TRIAGE_EVAL_V2.md) · [CI nền](https://github.com/Greediex/Gateway_LM/actions/runs/44705437165)

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

Tiến độ UI-GRAPH (19/11/2026, `v2`) — Mở Mạng Skill từ thanh chat, hiển thị 120 Skill, 72 Function, 15 domain và 129 cạnh. Coverage hiện có là 101 Skill nghiệm thu mô phỏng và 5 Skill có cấu hình gọi từ chat. Đã kiểm tra HTTP live (1 Skill, 2 Function) và replay (8 Function), endpoint 200/503 qua test, cùng thứ tự sáng và nút ngoài catalog qua Node. `check_project` PASS. Unittest 1.083 tổng, 1.078 pass, 0 fail, 5 skip Windows-only (340,999 s). Hai script Node PASS. Trình duyệt tích hợp chưa truy cập được. Không có run CI mới vì commit local.
Tiến độ UI-GRAPH force (20/11/2026, `v2`) — SVG lực tất định dừng sau 97 bước, hâm nóng lại 48 bước sau kéo. Có pan, zoom, tìm Skill, thẻ nút, toàn màn hình và chế độ giảm chuyển động. Giữ trace live/replay và đối chiếu HTTP local được 120 Skill, 72 Function, 15 domain, 129 cạnh, 101 Skill nghiệm thu mô phỏng và 5 Skill gọi được từ chat. `check_project` và hai script Node PASS. Unittest 1.083 tổng, 1.078 pass, 0 fail, 5 skip (306,202 s). Trình duyệt tích hợp không khả dụng. Commit local, chưa có run CI mới.
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
| [x] | **WP-A1 — Claim batch A** | Thêm Claim có version cho A02/A04/A06/A08 (vd. `inventory_empty`, `oui_unknown`, `ip_mac_conflict`, `client_not_associated` + bản HEALTHY), theo định dạng `replay.diagnostics.json`, file mới `config/skill_launcher/replay_a.diagnostics.json`. Mở rộng `scripts/simulate_skills.py` để chấm verdict Claim (FAULT/HEALTHY/UNKNOWN) với gold tách riêng `simulation_v1/gold_claims_v1.json`. | 12 kịch bản: normal→HEALTHY, fault→FAULT, missing→UNKNOWN/NOT_READY; test phủ ngưỡng biên và fact hết hạn. | Codex |
| [x] | **WP-A2 — Profile đa domain / đa scope** | Mở rộng `skill_expansion/profiles.py` để một profile replay chứa nhiều domain **cùng scope** (giữ chặn khác scope). Không đổi hành vi profile v1 (test cũ giữ nguyên). | Profile v1 vẫn hợp lệ, digest không đổi; profile mới gộp A02 (gateway) + B02/B03/B05 qua được validator; profile trộn scope bị từ chối. | Codex |
| [x] | **WP-A3 — Deployment replay client** | Deployment replay scope `client` cho A04/A06/A08 (identity dependency khai báo đúng như `core_replay_smoke_v2`), fixture lấy từ `simulation_v1` trạng thái normal. Script in digest đề xuất (giống `prepare_replay_chat_approval.py`). | `composition('replay_client')` hoặc tương đương chạy được trong test với approval giả lập; production vẫn tắt tới khi người duyệt ghi digest. | Codex |
| [x] | **WP-A4 — Composite A03/A05/A07** | Workflow + Claim cho Skill tổng hợp dựa trên evidence đã có (A03 = inventory+identity, A05 = inventory+vendor, A07 = inventory+history), không tạo READ Function giả. A07 cần chuỗi thời gian ≥2 mẫu mô phỏng. | Mỗi composite có kịch bản normal/fault/missing qua Core; thiếu một nguồn → UNKNOWN, không suy diễn. | Codex |
| [x] | **WP-A5 — Coverage ghi nhận nghiệm thu** | Thêm nguồn nghiệm thu có version cho `coverage.py` (vd. `simulation_v1/acceptance.json` sinh từ `simulate_skills`, không nhập tay) để `simulation_verified` tăng **chỉ khi** Skill có đủ normal/fault/missing qua Core + Claim đúng. | `cli coverage` báo đúng số Skill batch A đạt; sửa tay acceptance mà không khớp kết quả chạy → fail. | Codex |
| [x] | **WP-L1 — Đo Qwen thật trên laptop** | Chạy Web live (`./web_gateway/start_linux.sh`) với `qwen3:4b`; 10 câu hỏi (rõ ràng/mơ hồ/WRITE/ngoài phạm vi); ghi `routing`, `model_calls`, `timings_ms`, `answer_synthesis`, `case_status`. Thử thêm `GATEWAY_LM_CHAT_FAST=0` để so sánh. | Bảng kết quả (không kèm định danh người dùng/capture mạng) gửi Claude để chỉnh; ghi tóm tắt số liệu vào FINALIZE-02. | Người dùng / Codex trên laptop |
| [ ] | **WP-R1 — Duyệt digest** | Đọc `replay.diagnostics.json` (+ file của WP-A1/A3 khi có), chạy script in digest, ghi vào `approvals.json` trong commit riêng. | Commit do người duyệt; Claude kiểm lại digest khớp. | **Người duyệt** |

Tiến độ WP-A1 (18/11/2026, `codex/wp-a1`, chờ review; giữ nguyên checkbox): thêm `replay_a.diagnostics.json` v1.0.0 với 9 Claim cho A02/A04/A06/A08 (gồm hostname conflict riêng), gold Claim tách biệt; scorer đánh giá bằng ClaimBook trên CaseState do Core tạo. Kiểm tra local bằng `.venv-graph/bin/python`: check_project PASS; unittest 891 tổng / 886 pass / 0 fail / 5 skip Windows-only; simulate_skills 12/12 pass; 14 test tập trung pass. Coverage: total/catalog 120; type change 1, composite 34, direct 70, history 8, legacy_v01 7; contract_reviewed 0, replay_launchable 3, live_launchable 2, simulation_verified 0, router_verified 0; COV-A…O mỗi batch 8. Chỉ kiểm chứng synthetic, chưa nghiệm thu deployment/coverage WP-A5. Digest đề xuất: `328f982bc4671e4986d771f3ed772f3014d5e1962e8ced1672ea079ef055e7c9`; không ghi approvals. Không có CI run mới vì không push. Commit đang chờ danh tính tác giả Git (user.name/user.email chưa cấu hình).

Tiến độ WP-A2 (18/11/2026, `v2`, chờ review; giữ nguyên checkbox): thêm format `gateway-lm.skill-profile/v2` với `domains` là danh sách không rỗng, không trùng và khớp chính xác domain của các Skill được chọn; vẫn bắt buộc cùng scope. Profile mới `inventory_wifi_gateway_replay_v2.json` chọn A02+B02/B03/B05 scope gateway; metadata vẫn PROPOSED, không cấp quyền chạy. V1 giữ nguyên validator semantics và canonical digest `9b3d15ed7dc9d3e1e55f439397e9793982d6d1a276d3309016cb661ddce94862`. Đã chạy bằng `.venv-graph/bin/python`: 21 test profile pass; check_project PASS; simulate_skills 12/12 pass; core_replay_smoke_v2 72/72 pass. Unittest toàn repo: 898 tổng / 893 pass / 0 fail / 5 skip (Windows-only), 183.473s. Coverage CLI: total/catalog 120; by_type change 1, composite 34, direct 70, history 8, legacy_v01 7; contract_reviewed 0, replay_launchable 3, live_launchable 2, simulation_verified 0, router_verified 0; COV-A…O mỗi batch 8. Đây là kiểm chứng metadata/synthetic, chưa phải nghiệm thu deployment hay phần cứng. Không ghi approvals, không đổi source/frozen fixtures. Không có CI run mới vì không push.

Tiến độ WP-A3 (18/11/2026, `v2`, chờ review; giữ nguyên checkbox): thêm deployment `replay_client` cho A04/A06/A08 scope client, catalog synthetic riêng với dependency DATA `client.identity` do Core xác minh; dùng fixture normal từ `simulation_v1`, không đọc gold trong runtime. `composition('replay_client')` chạy với approval giả lập trong test; cấu hình thật vẫn bị chặn `skill_deployment_not_approved`. Script `.venv-graph/bin/python -m scripts.prepare_replay_client_approval` chỉ in đề xuất, không ghi approvals; registry artifact chỉ nằm trong `runs/`. Chưa mở mode này cho Web/chat, chưa nghiệm thu phần cứng. Đã chạy local bằng `.venv-graph/bin/python`: check_project PASS; unittest toàn repo 905 tổng / 900 pass / 0 fail / 5 skip Windows-only (182.623s); 7 test WP-A3 pass, gồm sai target/scope, thiếu quyền, schema hỏng, timeout, identity sai, fact hết hạn, fixture/pin drift và production chưa duyệt; simulate_skills 12/12 pass; core_replay_smoke_v2 72/72 pass. Coverage CLI: total/catalog 120; by_type change 1, composite 34, direct 70, history 8, legacy_v01 7; contract_reviewed 0, replay_launchable 3, live_launchable 2, simulation_verified 0, router_verified 0; COV-A…O mỗi batch 8. Digest đề xuất: registry `bed7956e9d955b982f751570b7e83709ad05192ccfc3e4166e47c77b0f9022d9`, actions `33a980221f424b9373e6a4c1c20935057b21b3d0a3bba10ea2c13af133e87843`, fixtures `966d99b5ff2e190e4a119980235bbaa8cba08d082a4186743d3579e6ff60f9f2`. Không ghi approvals, không đổi frozen/source fixtures, không có CI run mới vì không push.

Tiến độ WP-A4 (18/11/2026, `v2`, chờ review; giữ nguyên checkbox): Codex dừng giữa chừng do hết hạn mức, Claude hoàn thiện. Thêm `replay_a_composite.diagnostics.json` v1.0.0 cho A03 (inventory+identity), A05 (inventory+vendor), A07 (inventory hiện tại+trước, ≥2 mẫu có thứ tự), `simulation_composite_v1` (9 kịch bản, gold tách riêng), `composite.py`, `scripts/simulate_composites.py`. Mỗi nguồn chạy qua Core (`smoke` → `GraphRunner`), không tạo READ Function mới; thiếu/sai một nguồn → mọi Claim UNKNOWN. simulate_composites 9/9; giới hạn: A03 không gộp từng thiết bị, A05 không suy loại thiết bị, A07 chỉ so số lượng. Chưa nghiệm thu coverage (WP-A5).

Tiến độ WP-A5 (18/11/2026, `v2`, chờ review; giữ nguyên checkbox; Claude làm vì Codex hết hạn mức): `scripts.simulate_skills --write-acceptance` sinh `simulation_v1/acceptance.json` từ kết quả chạy, ghim `inputs_digest` (scenarios, gold, diagnostics). `coverage.py` chỉ tính `simulation_verified` khi Skill có đủ normal/fault/missing đều pass, normal/fault có `core_calls` > 0; digest lệch → CoverageError. Test chạy lại mô phỏng và so khớp file đã commit. Coverage: `simulation_verified` 7 (A02–A08), `router_verified` 0; SK01 (legacy) chưa có kịch bản.

Tiến độ WP-L1 (18/11/2026, laptop Linux, `qwen3:4b`, commit `13afb6e`; số liệu cho FINALIZE-02): 10 câu × 2 chế độ. **Nhanh (mặc định):** 4 câu rõ ràng đi `direct_route`, 0 lượt LLM, MEASURED, tổng 8–15 s; 2 câu mơ hồ 1 lượt LLM, `intent_scope_unconfirmed` PARTIAL, 70–100 s (inference 56–85 s); 2 câu WRITE BLOCKED, 0 LLM, ~2,4 s; 2 câu ngoài phạm vi 1 lượt LLM, `needs_clarification` NEEDS_INPUT, 11–52 s. **`GATEWAY_LM_CHAT_FAST=0`:** câu rõ ràng 2 lượt LLM, 98–107 s, 2/4 `model_timeout` PARTIAL, 2/4 MEASURED nhưng `insufficient_freshness_window`; câu mơ hồ 3 lượt, ~141 s, `model_timeout`; WRITE BLOCKED ~4 s; ngoài phạm vi 2 lượt, 88–98 s, NEEDS_INPUT. **Ở cả 20 lượt `answer_synthesis.used_llm` = false** (renderer hoặc freshness): Qwen chưa lần nào viết câu trả lời cuối. Ghi chú đo: script không đóng session nên lần đầu 2 câu ngoài phạm vi chế độ nhanh bị `session_capacity_limit`; đã đo lại trên server mới.

Tiến độ CHAT (18/11/2026, `v2`): (1) Qwen chỉ thấy Skill READY/DEGRADED, cộng Skill UNAVAILABLE do luật cụm từ phát hiện; không còn chọn K07/M02 không chạy được. (2) Chế độ nhanh: câu triệu chứng mơ hồ (`diagnostic_request`: chậm, do đâu, vấn đề…) không có route → đo cơ bản mọi port của question_intent mà action chạy được sản xuất, 0 lượt LLM; WRITE/IP lạ vẫn chặn trước. Live: "mạng đang hơi chậm do đâu" 21,6 s MEASURED (trước: 60 s, UNAVAILABLE). (3) Cho Qwen diễn đạt ở chế độ nhanh: đã thử và **bỏ** — Qwen CPU vượt 12 s/lượt (`selection_TimeoutError`) hoặc fact hết hạn trước khi xong; không nới TTL (L4). Đổi 2 test cũ theo hợp đồng mới (danh sách cho model chỉ gồm Skill chạy được), thêm 4 test.

Tiến độ CLAIM hiệu năng (18/11/2026, `v2`): workflow `LAPTOP-PERFORMANCE` trong `live.diagnostics.json` (gắn `laptop.network.inspect`): `wifi_signal_weak` (signal_pct < 40), `gateway_latency_high` (> 20 ms), `internet_latency_high` (> 100 ms), `performance_path_normal` (HEALTHY khi đủ ngưỡng và không mất gói). Ngưỡng heuristic phía laptop, chưa hiệu chỉnh trên nhiều mạng. Câu trả lời in một dòng cho mỗi Claim TRUE còn hạn; dòng gợi ý ghi rõ chưa phải nguyên nhân (L5). Digest live đổi `80e3c865…` → `d272b0b6…`, chủ dự án duyệt trong chat, ghi trong commit riêng.

Tiến độ WP-S1 (18/11/2026, `v2`): nguyên nhân `semantic_encoder_failed` không phải RAM mà là giới hạn 10 s mỗi request của `LocalOllamaEncoder`: nhúng cả catalog (126 tài liệu) bằng một lệnh gọi trên CPU mất khoảng 27 s (đo 1 tài liệu 0,2 s, 32 tài liệu 6,7 s). Sửa: `encode_many` chia khối 16 tài liệu, kiểm digest quanh mỗi khối, không trả vector từng phần khi một khối lỗi; thêm `ChatContext.warm` và luồng nền khi server khởi động để lượt Qwen đầu không tốn thời gian. Đo live: chỉ mục sẵn sàng sau 7 s, lượt Qwen `catalog_semantic: READY` (trước: ERROR). 6 test mới.

Tiến độ WP-S2/S3 (18/11/2026, `v2`): `python -m scripts.scaffold_batch <A-O> [--out F]` in bảng việc của một batch từ dữ liệu catalog: loại Skill, Function/port khai báo, trường của port và 3 kịch bản mẫu normal/fault/missing với giá trị `TODO:<kiểu>` cố ý không qua được schema (không thể bị nạp nhầm như kịch bản thật); không bao giờ sinh gold. `python -m scripts.suggest_phrases <ID...>` gợi ý cụm từ từ tên Skill (bỏ động từ mở đầu chung chung) và báo cụm nào trùng với cụm đã có của intent/Skill khác; không ghi file. Phát hiện khi viết test: bộ chặn gold ở `simulation.load_scenarios` từ chối trường port hợp lệ `expected_routes` (batch J) và `expected_match` (batch N). Sửa hẹp: tên trường do chính port schema của kịch bản khai báo được phép; mọi khóa giống nhãn khác vẫn bị từ chối, có test. Chưa sửa tương tự cho `composite.py` vì chưa có kịch bản composite dùng các trường này. WP-S4 (rà soát hợp đồng) vẫn chờ người duyệt.

Tiến độ COV-B (18/11/2026, `v2`, chờ review; chưa đánh dấu Batch COV-B): Claim cho 7/8 Skill (B02–B08) trong `replay_b.diagnostics.json` (16 Claim, mỗi Claim đuôi `_v1`), 21 kịch bản normal/fault/missing trong `simulation_b_v1/` cùng gold tách riêng; `simulate_skills` chạy theo danh sách batch (`BATCHES`), `evaluate_all` gộp cả composite; `acceptance.json` sinh lại → `simulation_verified` 7 → **14** (A02–A08, B02–B08). **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh trên dữ liệu thật:** B04 RSSI < −75 dBm hoặc SNR < 20 dB; B05 airtime > 70%; B06 > 5 BSS lân cận; B07 > 10 lần roam; B08 chất lượng backhaul < 50% hoặc backhaul_up=false. Giá trị ngoài miền (phần trăm <0 hoặc >100, số đếm âm) ra UNKNOWN, không ra HEALTHY/FAULT. Giới hạn: B03 chỉ dựa cờ `ssid_present` (chưa kiểm `ssid` không rỗng); B07 port không có cửa sổ thời gian nên `roam_count` chỉ là đếm thô; B06 chỉ đếm BSS lân cận, chưa biết chồng kênh thật; RSSI/SNR của B04 là dBm/dB, khác `signal_pct` của laptop. Chưa làm: **SK02** (legacy, cần thiết kế riêng), profile/deployment replay cho B (không cần cho mức Simulation verified, cần cho chat replay), mọi đo thật (M2/M3). 28 trường hợp biên + 6 lỗi giá trị trong `tests/test_batch_b_simulation.py`.

Tiến độ COV-D (18/11/2026, `v2`, chờ review; chưa đánh dấu Batch COV-D): Claim cho 5/8 Skill direct (D02, D03, D05, D06, D07) trong `replay_d.diagnostics.json` (12 Claim), 15 kịch bản trong `simulation_d_v1/` cùng gold tách riêng; `simulation_verified` 14 → **19**. Đăng ký batch tại một bảng `DIRECT_BATCHES` trong `coverage.py` (đọc bởi `simulate_skills` và digest nghiệm thu); kiểm tra dùng chung ở `tests/batch_sim_support.py`, B và D chỉ khai báo bảng biên. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh:** D02 còn ≤ 5 địa chỉ trống là FAULT, = 0 là cạn; D03 > 20 lease hết hạn; D05 > 3 mục neighbor thất bại; D06 FAULT khi không có RA hoặc có RA nhưng 0 prefix; D07 FAULT khi server DHCPv6 tắt. Giá trị âm ra UNKNOWN. Giới hạn: D03 port không có cửa sổ thời gian nên số lease hết hạn chỉ là đếm thô; D07 giả định mạng dùng DHCPv6 có trạng thái — tắt DHCPv6 là bình thường nếu chỉ dùng SLAAC, cần cấu hình mong đợi mới kết luận đúng; D05 không so được `failed_entries` với `neighbor_count` (Claim không so hai trường). Chưa làm: **D04, D08** (composite, cần workflow trên nhiều nguồn), **SK03** (legacy), profile/deployment replay, mọi đo thật.

Tiến độ COV-F (18/11/2026, `v2`, chờ review; chưa đánh dấu Batch COV-F): Claim cho 7/8 Skill (F02–F08) trong `replay_f.diagnostics.json` (18 Claim), 21 kịch bản trong `simulation_f_v1/` cùng gold tách riêng; `simulation_verified` 19 → **26**. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh:** F02 FAULT khi không có resolver hoặc 0 resolver khỏe; F03 FAULT khi 0 cache hit và > 100 miss; F04 FAULT khi có xung đột; F05 FAULT khi thiếu DNS option từ DHCP; F06 FAULT khi DNSSEC bật và có lỗi xác thực; F07 FAULT khi cả DoT và DoH đều tắt; F08 FAULT khi chưa đồng bộ hoặc lệch > 500 ms. Trường hợp một mẫu không đủ để kết luận cho **UNKNOWN**, không ép thành HEALTHY/FAULT: cache nhàn rỗi (0 hit, ≤ 100 miss) và DNSSEC tắt. Giới hạn: F02 không phát hiện resolver khỏe một phần (Claim không so hai trường); F03 không có tỉ lệ hit hay cửa sổ thời gian; F05 chỉ kiểm có option, chưa kiểm giá trị; F07 coi tắt cả DoT và DoH là FAULT chỉ đúng khi chính sách yêu cầu DNS mã hóa; F08 chỉ so độ lệch với ±500 ms. Chưa làm: **SK05** (legacy), profile/deployment replay, mọi đo thật. 34 ca biên + 7 lỗi giá trị trong `tests/test_batch_f_simulation.py`.

Tiến độ COV-E (18/11/2026, `v2`, chờ review; chưa đánh dấu Batch COV-E): Claim cho 7/8 Skill (E02–E08) trong `replay_e.diagnostics.json` (16 Claim), 21 kịch bản trong `simulation_e_v1/` cùng gold tách riêng; `simulation_verified` 26 → **33**. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh:** E02 FAULT khi link down; HEALTHY khi up ≥ 60 s; E03 FAULT khi không có default route; E04 FAULT khi phiên PPPoE/DHCP/static không kết nối; E05 FAULT khi NAT tắt hoặc nghi CGNAT; E06 FAULT khi 0 uplink khỏe; E07 FAULT khi > 3 lần ngắt; HEALTHY chỉ khi cửa sổ quan sát ≥ 3600 s; E08 FAULT khi không tới được hoặc mất gói > 5%. Mẫu không đủ kết luận cho **UNKNOWN**: link mới lên < 60 s, nhiều default route (có thể multi-WAN), giao thức không thuộc pppoe/dhcp/static, cửa sổ quan sát ngắn, số âm. Giới hạn: E05 coi NAT tắt và CGNAT là FAULT nhưng bridge mode hợp lệ hoặc CGNAT không phải sự cố hỏng, chỉ là hạn chế truy cập vào; E06 không phát hiện uplink khỏe một phần; E02/E07 không phân biệt nguyên nhân (cáp, nhà mạng, thiết bị). Chưa làm: **SK04** (legacy), profile/deployment replay, mọi đo thật. 38 ca biên + 7 lỗi giá trị trong `tests/test_batch_e_simulation.py`.

Tiến độ COV-G (18/11/2026, `v2`, chờ review; chưa đánh dấu Batch COV-G): Claim cho 6/8 Skill direct (G01, G02, G04, G05, G06, G07) trong `replay_g.diagnostics.json` (15 Claim), 18 kịch bản trong `simulation_g_v1/` cùng gold tách riêng; `simulation_verified` 33 → **39**. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh:** G01 FAULT khi độ trễ > 100 ms hoặc mất gói > 2%; G02 jitter > 30 ms; G04 FAULT khi cả rx và tx bằng 0; G05 FAULT khi rx hoặc tx > 800 Mbps; G06 hàng đợi > 50 ms (bufferbloat); G07 FAULT khi SQM tắt hoặc bật nhưng tốc độ cấu hình bằng 0. Mẫu không đủ kết luận cho **UNKNOWN**: G04 chỉ một chiều có lưu lượng; phần trăm ngoài [0,100]; số âm. Giới hạn: G04 là bộ đếm tích lũy không có cửa sổ thời gian nên chỉ phân biệt "có/không có lưu lượng"; G05 giả định đường truyền 1 Gbps vì port không có dung lượng liên kết, nên ngưỡng 800 Mbps không đúng với đường chậm hơn; G06 dùng một ngưỡng độ trễ hàng đợi, chưa đo dưới tải nên không chứng minh bufferbloat; G07 tắt SQM là FAULT chỉ đúng khi chính sách yêu cầu SQM. Chưa làm: **G03, G08** (composite), mọi đo thật. 34 ca biên + 6 lỗi giá trị trong `tests/test_batch_g_simulation.py`.
Tiến độ COV-C (19/11/2026, `v2`, chờ review): 7 Skill direct C01–C05, C07, C08 có 14 Claim `_v1` trong `replay_c.diagnostics.json`, 21 kịch bản qua Core/Verifier và gold tách riêng trong `simulation_c_v1/`. Coverage sinh từ acceptance tăng từ 39 lên **46/120** `simulation_verified`. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh.** C01 giả định có 4 cổng, FAULT khi 0 cổng active, HEALTHY khi 1–4. C02 giả định link được kỳ vọng lên, FAULT khi tốc độ bằng 0 Mbps, HEALTHY khi tốc độ dương và cả hai bộ đếm lỗi bằng 0. C03 giả định FDB chứa tối đa 1024 mục, FAULT tại 1024, HEALTHY từ 1 đến 1023. C04 cần ít nhất 1 cổng thành viên, bridge down là FAULT và up là HEALTHY. C05 cần ít nhất 1 VLAN, số membership sai dương là FAULT và bằng 0 là HEALTHY. C07 giả định chính sách yêu cầu STP, tắt là FAULT, bật với 0 lần đổi topology ghi nhận là HEALTHY. C08 chỉ xét MTU 68–9216 byte, cờ báo mismatch quyết định FAULT/HEALTHY. **UNKNOWN** khi số âm, thiếu nguồn, ngoài miền mô hình hoặc mẫu chưa đủ căn cứ, gồm RX/TX có lỗi tích lũy khi link đang lên, FDB rỗng, bridge không có thành viên, 0 VLAN và STP đang bật với số lần đổi topology dương. Giới hạn: Claim chỉ so từng trường với hằng số nên C01 giới hạn ở mô hình 4 cổng và C08 dựa vào cờ mismatch từ nguồn, chưa đối chiếu MTU giữa hai đầu. Bộ đếm RX/TX và STP thiếu cửa sổ thời gian để suy ra xu hướng. Kết quả HEALTHY chỉ mô tả các trường được quan sát. C06 (composite), Skill legacy, profile/deployment replay và đo thật nằm ngoài đợt này. Test có 54 ca biên và 7 mẫu sai kiểu.
Tiến độ COV-H (19/11/2026, `v2`, chờ review). 7 Skill direct H02–H08 có 15 Claim `_v1` và 21 kịch bản READ qua Core/Verifier, mỗi Skill có normal/fault/missing. Gold chấm điểm nằm trong hai file riêng. Coverage sinh từ acceptance tăng từ 46 lên **53/120** `simulation_verified`. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh.** H02 báo FAULT khi có ít nhất 1 dịch vụ lỗi, HEALTHY khi có dịch vụ đang chạy và 0 lỗi, UNKNOWN khi cả hai bộ đếm bằng 0. H03 báo FAULT khi mức sử dụng ≥ 90% hoặc wear ≥ 80%. H04 báo FAULT khi mẫu có lỗi, HEALTHY khi cả lỗi và cảnh báo bằng 0, UNKNOWN khi chỉ có cảnh báo. H05 báo FAULT ở 85–125 °C, HEALTHY từ 0 đến dưới 85 °C, UNKNOWN ngoài miền 0–125 °C. H06 báo FAULT khi có lỗi driver được ghi nhận, HEALTHY khi bộ đếm bằng 0. H07 báo FAULT khi có crash và ít nhất 1 boot được ghi nhận, HEALTHY khi có đúng 1 boot và 0 crash, UNKNOWN khi không có boot hoặc có nhiều boot mà không ghi nhận crash. H08 đánh giá riêng điều kiện dung lượng trống, FAULT dưới 64 MB và HEALTHY từ 64 MB. Số âm, phần trăm ngoài 0–100 và thiếu nguồn đều ra UNKNOWN. Một mẫu H02 thiếu danh sách dịch vụ kỳ vọng và kiểm tra đáp ứng. H03 chưa đo tốc độ hao mòn. H04/H06 thiếu nội dung, cửa sổ thời gian và định danh sự kiện/interface. H05 chưa có ngưỡng theo board hoặc chuỗi nhiệt. H07 chưa phân loại reboot chủ động và chưa xác định thời điểm hay nguyên nhân crash. Readiness firmware đầy đủ vẫn UNKNOWN vì H08 thiếu ảnh đích, tương thích/chữ ký và thông tin phân vùng, còn version chỉ là metadata. SK08, profile/deployment replay và đo thật ngoài phạm vi đợt này. Test có 39 ca biên và 8 mẫu sai kiểu.
Tiến độ COV-I (19/11/2026, `v2`, chờ review). 7 Skill direct I01–I06, I08 có 14 Claim `_v1` và 21 kịch bản READ normal/fault/missing qua Core/Verifier, gold tách riêng. Coverage sinh từ acceptance tăng từ 53 lên **60/120** `simulation_verified`. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh trên dữ liệu thật.** I01 cần ít nhất 1 rule, báo FAULT nếu có rule lỗi và HEALTHY nếu 0 lỗi. I02 giả định chính sách không cho phơi lộ dịch vụ, báo FAULT nếu có ít nhất 1 dịch vụ lắng nghe và 1 dịch vụ phơi lộ, HEALTHY khi báo 0 phơi lộ. I03 giả định chính sách yêu cầu guest isolation, tắt là FAULT và bật là HEALTHY theo cờ cấu hình. I04 HEALTHY cho `wpa2`/`wpa3` có mã hóa và FAULT cho `open` không mã hóa theo chính sách mô phỏng. I05 HEALTHY khi quản trị từ xa tắt và FAULT khi bật mà chưa cấu hình MFA. I06 cần ít nhất 2 phân đoạn, báo FAULT nếu có vi phạm và HEALTHY nếu 0 vi phạm. I08 báo FAULT nếu có check thất bại, HEALTHY khi ít nhất 1 check đạt và 0 check thất bại. UNKNOWN khi số âm, thiếu nguồn, 0 rule, có phơi lộ nhưng 0 dịch vụ lắng nghe, mode Wi-Fi ngoài tập mô hình hoặc không khớp cờ mã hóa, quản trị từ xa bật với MFA đã cấu hình, dưới 2 phân đoạn hoặc không có check nào. Các port không có trường phần trăm. Claim chỉ so từng trường với hằng số, nên I01/I02 dựa vào nguồn để bảo đảm số rule lỗi hoặc dịch vụ phơi lộ không vượt bộ đếm tổng dương. I01/I08 thiếu nội dung rule, danh tính và độ phủ bộ kiểm tra. I02 thiếu vùng truy cập và allowlist dịch vụ. I03/I06 thiếu phép đo lưu lượng liên vùng. I04 thiếu cipher và chế độ thực tế khi client kết nối. I05 thiếu scope truy cập và bằng chứng cưỡng chế MFA. HEALTHY/FAULT chỉ mô tả điều kiện cấu hình hoặc kết quả kiểm tra được báo trong mẫu. I07, profile/deployment replay và đo thật ngoài phạm vi đợt này. Test có 39 ca biên và 9 mẫu sai kiểu.
Tiến độ COV-J (19/11/2026, `v2`, chờ review). 6 Skill direct J01, J02, J04, J06, J07, J08 có 12 Claim `_v1` và 18 kịch bản READ normal/fault/missing qua Core/Verifier, gold tách riêng. Coverage sinh từ acceptance tăng từ 60 lên **66/120** `simulation_verified`. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh trên dữ liệu thật.** J01 cần ít nhất 1 peer, dùng cờ tunnel up/down để báo HEALTHY/FAULT theo trạng thái tunnel trong mẫu. J02 cần ít nhất 1 route kỳ vọng, HEALTHY khi thiếu 0 và FAULT khi thiếu đúng 1. J04 HEALTHY khi có ít nhất 1 peer reachable và 0 unreachable, FAULT khi có ít nhất 1 peer unreachable, kể cả mẫu có cả peer reachable. J06 khi IPv6 bật thì có route là HEALTHY và thiếu route là FAULT. J07 cần ít nhất 1 rule, HEALTHY khi 0 và FAULT khi đúng 1 rule chưa phân giải. J08 giả định dịch vụ truy cập từ xa được yêu cầu, HEALTHY khi dịch vụ bật và có ít nhất 1 kết nối được báo, FAULT khi dịch vụ tắt và 0 kết nối. UNKNOWN khi số âm, thiếu nguồn, J01 không có peer, J02/J07 không có mục kỳ vọng/đã cấu hình hoặc báo hơn 1 mục lỗi, J04 không có kết quả cho peer nào, J06 tắt IPv6, J08 bật mà 0 kết nối hoặc tắt mà vẫn có kết nối được báo. Các port không có trường phần trăm. Giới hạn: J01/J04 thiếu handshake, ID peer và chuỗi thời gian; J02/J07 chỉ so được với hằng số nên chưa thể kiểm quan hệ giữa hai bộ đếm khi có hơn 1 mục lỗi, cũng chưa xác minh prefix, bảng định tuyến, thứ tự rule hay đường đi thật; J06 chỉ có cờ route, chưa đo kết nối IPv6 đầu cuối; J08 thiếu chính sách kỳ vọng trong port, tuổi kết nối và probe từ bên ngoài, nên chỉ đánh giá ảnh chụp theo giả định dịch vụ bắt buộc. J03, J05, profile/deployment replay và đo thật ngoài phạm vi đợt này. Test có 37 ca biên và 8 mẫu sai kiểu.
Tiến độ COV-L (19/11/2026, `v2`, chờ review). 4 Skill direct L01, L02, L03, L05 có 8 Claim `_v1` và 12 kịch bản READ normal/fault/missing qua Core/Verifier, gold tách riêng. Coverage sinh từ acceptance tăng từ 66 lên **70/120** `simulation_verified`. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh trên dữ liệu thật.** L01 với ít nhất 2 node báo FAULT khi ảnh chụp có 0 cạnh và HEALTHY khi có ít nhất 1 cạnh. L02 báo FAULT khi có ít nhất 1 client chưa ánh xạ, HEALTHY khi có ít nhất 1 association và 0 client chưa ánh xạ. L03 báo FAULT khi có ít nhất 1 gateway đã biết và 0 reachable, HEALTHY khi cả hai bộ đếm bằng 1. L05 báo FAULT cho thiếu dữ liệu kiểm kê subnet khi có ít nhất 1 VLAN nhưng 0 subnet, HEALTHY khi cả hai danh mục đều có mục. UNKNOWN khi thiếu nguồn, có số âm, L01 dưới 2 node, L02 cả hai bộ đếm bằng 0, L03 không có gateway đã biết, có số reachable vượt tổng hoặc có nhiều gateway đã biết với số reachable dương, hay L05 không có VLAN. Các port chỉ có bộ đếm nguyên. L01 thiếu ID node, hai đầu cạnh và provenance theo cạnh để kiểm tính liên thông, độ phủ hoặc cạnh trùng. L02 thiếu ID client/AP/router và nguồn theo liên kết để xác minh từng ánh xạ. L03 chỉ xét reachability được báo tại một thời điểm, thiếu ID gateway/uplink, đích probe và chuỗi thời gian; Claim chỉ so được với hằng số. L05 thiếu prefix, VLAN ID và quan hệ giữa chúng; VLAN L2-only có thể có 0 subnet, nên FAULT chỉ mô tả khoảng trống trong mẫu kiểm kê theo tiêu chí mô phỏng. L04, L06, L07, L08, profile/deployment replay và đo thật ngoài phạm vi đợt này. Test có 31 ca biên và 8 mẫu sai kiểu.
Tiến độ COV-N (19/11/2026, `v2`, chờ review). 3 Skill direct N03, N04, N07 có 6 Claim `_v1` và 9 kịch bản READ normal/fault/missing qua Core/Verifier, gold tách riêng. Coverage sinh từ acceptance tăng từ 70 lên **73/120** `simulation_verified`. **Ngưỡng là heuristic tổng hợp, chưa hiệu chỉnh trên dữ liệu thật.** N03 báo HEALTHY khi cờ có snapshot và revision khác chuỗi rỗng, FAULT khi cờ không có snapshot và revision rỗng; các cặp còn lại ra UNKNOWN. N04 báo HEALTHY khi số mục drift bằng 0, FAULT từ 1 mục, UNKNOWN khi số âm. N07 báo HEALTHY/FAULT theo cờ readback khớp/không khớp được nguồn báo. Thiếu nguồn ra NOT_READY/UNKNOWN; các port không có trường phần trăm. N03 chỉ có metadata, thiếu nội dung, định dạng revision và hash để kiểm tính đầy đủ hay toàn vẹn của snapshot. N04 thiếu revision đối chiếu, chi tiết mục thay đổi và lịch sử, nên không suy ra phạm vi hay diễn biến drift. N07 thiếu định danh cấu hình đích, giá trị kỳ vọng và quan sát, trạng thái giao dịch và chuỗi thời gian; việc rollback có thực sự diễn ra và khôi phục thành công vẫn UNKNOWN. SK13, N02, N05, N06, N08, profile/deployment replay và đo thật ngoài phạm vi đợt này. Test có 9 ca biên và 9 mẫu fixture sai kiểu hoặc thiếu trường.

Tiến độ COV-L composite (19/11/2026, `v2`, chờ review). L06 và L07 có 4 Claim `_v1` và 6 kịch bản normal/fault/missing qua Core/Verifier, gold tách riêng, nâng `simulation_verified` từ 76 lên **78/120**. L06 đánh giá bộ đếm dịch vụ trong một mẫu site tổng hợp có ≥ 2 node, ≥ 1 cạnh và cửa sổ WAN ≥ 1 giây với 0 lần ngắt. HEALTHY khi có dịch vụ chạy và 0 lỗi, FAULT từ 1 lỗi. L07 xét đúng 2 gateway đã biết và probe thượng nguồn reachable với mất gói từ 0 đến dưới 100%. HEALTHY khi 2/2 được báo reachable, FAULT khi 1/2, UNKNOWN khi 0/2. Thiếu nguồn, khác thời điểm mẫu, số âm, phần trăm ngoài miền và mẫu không đủ điều kiện đều ra UNKNOWN. Các Claim chỉ mô tả bộ đếm tổng hợp, thiếu định danh và dữ liệu ghép nối để xác định sức khỏe toàn site, thiết bị riêng lẻ, failover hay nguyên nhân. Bỏ L04 vì thiếu định danh client, hai đầu cạnh và các hop theo đường đi. Bỏ L08 vì thiếu định danh/phạm vi sự cố và liên kết từ sự cố đến các thực thể bị ảnh hưởng. Test có 29 ca biên và 59 mẫu sai kiểu hoặc không hữu hạn.

Sau khi WP-A1…A5 đạt: Claude review, đánh dấu Batch COV-A, rồi tạo WP cho COV-B theo cùng mẫu.

## Kế hoạch chạy đủ 120 Skill (18/11/2026, Claude điều phối)

**Hiện trạng đo được:** catalog 120; chạy thật trên laptop 8 action; Simulation verified 7 (A02–A08); Router verified 0. Gap toàn catalog: CONTRACT_NOT_REVIEWED 120, NO_ROUTER_BACKEND 120, NO_LIVE_BINDING 118, NO_REPLAY_PROFILE 116, NEEDS_CLAIM_OR_WORKFLOW 40. Mô phỏng và laptop làm được ngay; router thật cần phần cứng (L2), nên "chạy đủ" chia thành 3 mức nghiệm thu độc lập, không gộp số.

| Mức | Mục tiêu | Cần phần cứng? | Ai làm |
|---|---|---|---|
| **M1 Simulation verified** | 120/120 có normal/fault/missing qua Core + Claim đúng, sinh từ `acceptance.json` | Không | Codex + Claude review |
| **M2 Live trên laptop** | Mọi Skill đo được từ laptop Linux có adapter READ thật (ước tính 20–30 Skill: batch B, D, một phần A/F/E/G) | Laptop này | Codex + Claude |
| **M3 Router verified** | Skill phía gateway/network có output Ubus thật, hash firmware, đo CPU/RAM | **Router thật (người dùng cung cấp)** | Người dùng chạy, Claude/Codex viết adapter |

Loại trừ vĩnh viễn khỏi "chạy": WRITE thật (N). Skill N chỉ ở sandbox, ghi nhãn WRITE_SANDBOX_ONLY (L3).

### Pha 0 — Nền móng (làm trước, mở khóa tốc độ)

| Xong | WP | Việc | Nghiệm thu |
|---|---|---|---|
| [x] | **WP-S1 — Sửa embedding** | `embeddinggemma` lỗi `semantic_encoder_failed` khi RAM đầy; đo RAM, giảm `keep_alive`/tải tuần tự, thêm cảnh báo rõ ràng | Hỏi 10 câu không còn `catalog_semantic: ERROR` khi Qwen đang nạp; test fallback giữ nguyên |
| [x] | **WP-S2 — Scaffold batch** | Script `scripts/scaffold_batch.py <BATCH>` sinh khung từ `skill_contract_stubs_120.json`: file kịch bản (normal/fault/missing, **chưa có gold**), khung Claim, khung workflow, khung test | Chạy cho batch B ra file hợp lệ; gold luôn do người/Codex điền riêng, không sinh tự động (L1/L5) |
| [x] | **WP-S3 — Danh sách cụm từ từ catalog** | Gợi ý cụm từ từ `name_vi`/`goal_description` để giảm việc viết tay; kết quả vẫn qua review, không tự cấp quyền | Câu hỏi thường gặp của batch mới rơi vào route đúng mà không cần Qwen; test không khớp nhầm Skill UNAVAILABLE |
| [ ] | **WP-S4 — Rà soát hợp đồng** | Người duyệt đọc `skill_contract_stubs_120.json` theo batch, đặt `runtime_binding_approved` theo từng Skill đã nghiệm thu mô phỏng | Mức `contract_reviewed` tăng theo batch; mỗi lần là commit riêng của người duyệt |

### Pha 1 — M1: mô phỏng đủ 120 (mỗi batch = 3 WP theo mẫu WP-A)

Mẫu mỗi batch X: **WP-X1** Claim + kịch bản + gold cho Skill `direct`; **WP-X2** workflow/Claim cho Skill `composite`/`history` (không tạo READ Function giả; thiếu nguồn → UNKNOWN); **WP-X3** profile/deployment replay + `acceptance.json` + sinh lại coverage. Mỗi WP theo "Quy tắc chung cho mọi WP" ở trên.

Thứ tự (đi từ ít phụ thuộc đến nhiều; M, O phụ thuộc kết quả các batch trước):

| Thứ tự | Batch | Ghi chú loại Skill (từ coverage) |
|---|---|---|
| 1 | **B** Wi-Fi & RF | 7 direct + 1 legacy; RSSI/SNR đúng đơn vị, không quy nguyên nhân duy nhất |
| 2 | **D** IP/DHCP/IPv6, **F** DNS | 5+7 direct; làm sớm vì laptop đo được (M2) |
| 3 | **E** WAN & Internet, **G** Performance/QoS | 7+6 direct, 2 composite; tái dùng Claim hiệu năng |
| 4 | **C** Ethernet L2, **H** System Health | 7 direct mỗi batch |
| 5 | **I** Security, **J** VPN | 7+6 direct, 3 composite |
| 6 | **K** History/Monitoring | 8 history; dùng `monitor_window`, cần ≥2 mẫu mô phỏng có thứ tự |
| 7 | **L** Topology/Multi-gateway | 4 direct + 4 composite |
| 8 | **M** Evidence/Adaptive, **O** Composite troubleshooting | 15 composite; chỉ làm khi nguồn đã có |
| 9 | **N** Change/Guided remediation | 1 change + 3 direct + 4 composite; WRITE chỉ sandbox |
| 10 | **A còn lại** | SK01 (legacy) cần kịch bản để đạt 8/8 |

Ước lượng: ~14 batch × 3 WP ≈ 42 WP. Pha 0 giảm khối lượng mỗi WP; Codex hết hạn mức thì Claude làm tiếp (đã áp dụng ở WP-A4/A5). Mốc kiểm tra: sau mỗi batch chạy 4 lệnh bắt buộc và chốt số `simulation_verified`.

### Pha 2 — M2: Live trên laptop

| Xong | WP | Việc | Nghiệm thu |
|---|---|---|---|
| [ ] | **WP-LV1 — Rà soát khả thi** | Với 120 Skill, ghi Skill nào đo được từ laptop Linux bằng lệnh READ allowlist (ví dụ `nmcli dev wifi list`, `ip -6`, `resolvectl`), Skill nào cần router | Bảng trong `docs/`: ID, lệnh/nguồn, quyền cần, kết luận; không đoán |
| [ ] | **WP-LV2… — Adapter theo nhóm** | Mỗi nhóm 3–5 Skill: adapter READ, hợp đồng Function/port, action, Claim, test timeout/output hỏng/sai interface/fact hết hạn | Mỗi nhóm một commit; digest `approvals.json` do người duyệt ghi; đo thật trên laptop ghi số vào TODO |

### Pha 3 — M3: Router thật (bị chặn bởi phần cứng)

Điều kiện: người dùng cho biết router/firmware và cách truy cập READ (ví dụ Ubus/SSH) cùng quyền chỉ đọc. Bắt buộc (L2): output Ubus từ board thật, hash firmware, số đo CPU/RAM; metric CI Ubuntu không tính. Chỉ khi đủ mới đặt `router_verified`. Việc: WP-RT1 backend chỉ đọc + allowlist; WP-RT2… adapter theo domain C/E/G/H/I/J; mỗi WP kèm test negative (sai target, thiếu quyền, response hỏng, timeout, fact cũ).

### Khung quản trị

- Mỗi mức đếm riêng trong `cli coverage`; không viết "đủ 120" nếu mới đạt M1. Báo cáo luôn ghi "mô phỏng" hay "thật".
- Claim phải có ngưỡng ghi trong file, version riêng, kèm kịch bản biên; kết luận là gợi ý, không là nguyên nhân gốc (L5).
- Mỗi batch kết thúc bằng: 4 lệnh kiểm tra, số `simulation_verified`/`live_launchable`, các digest chờ người duyệt (WP-R1 cũ vẫn mở).
- Rủi ro đã biết: cụm từ viết tay không mở rộng tốt khi số Skill tăng (WP-S3), Qwen 4B CPU chậm (không phụ thuộc vào Qwen cho đường chính), RAM laptop gần đầy (WP-S1).

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

Tiến độ COV-C composite (19/11/2026, `v2`): C06 đạt Simulation verified (3/3 kịch bản qua Core), coverage tăng từ 78 lên 79/120. Workflow dùng bridge, STP và mất gói cùng thời điểm mô phỏng. Bridge phải up, có ≥2 cổng thành viên và STP phải bật. HEALTHY khi ghi nhận 0 thay đổi STP và mất gói ≤1%; FAULT khi bộ đếm ≥3 và mất gói ≥10%; thiếu nguồn, mẫu không hợp lệ, tín hiệu trung gian hoặc trái chiều đều UNKNOWN. Ngưỡng mô phỏng chưa hiệu chỉnh. Bộ đếm thiếu cửa sổ quan sát và phép đo mất gói thiếu định danh bridge/VLAN, nên kết quả chỉ nêu dấu hiệu, chưa xác nhận vòng lặp, thiết bị hay nguyên nhân. Kiểm tra local: check_project PASS, simulate_skills 237/237, unittest 1033 pass, 0 fail, 5 skip Windows-only. Không có CI mới vì commit chỉ ở local.

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

Tiến độ COV-D composite (19/11/2026, `v2`): dùng chung bộ đăng ký batch composite và giữ fixture WP-A4. D04 đạt Simulation verified (3/3 ca qua Core); mẫu neighbor cần ≥ 1 mục và 0 mục lỗi, Claim gắn nhãn theo cờ nhất quán IP–MAC trong mẫu. Bất nhất là dấu hiệu sàng lọc, chưa đủ bằng chứng xác nhận trùng IP, xác định thiết bị hay quy nguyên nhân. D08 chưa nghiệm thu vì thiếu địa chỉ subnet/prefix và next hop để đối chiếu. Tổng mô phỏng 222/222 ca, `simulation_verified` 73 → 74; chưa đo trên router.

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

Tiến độ COV-G composite (19/11/2026, `v2`): G08 đạt Simulation verified (3/3 ca qua Core), sàng lọc độ trễ hàng đợi gateway với mẫu lưu lượng cùng thời điểm và RX hoặc TX > 0 Mbps. Ngưỡng mô phỏng 50 ms: ≤ 50 HEALTHY, > 50 FAULT. Thiếu nguồn, lệch thời điểm, lưu lượng hai chiều đều bằng 0 hoặc giá trị sai miền → UNKNOWN. Mẫu chỉ mô tả hàng đợi đã quan sát, chưa xác định điểm nghẽn, interface, thiết bị hay nguyên nhân. G03 chưa nghiệm thu vì bộ đếm và tốc độ lưu lượng thiếu bằng chứng về tải kiểm soát. Tổng 225/225 ca, `simulation_verified` 74 → 75, chưa đo trên router.

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

Tiến độ COV-I composite (19/11/2026, `v2`). I07 đạt Simulation verified với 3/3 kịch bản qua Core/Verifier, nâng `simulation_verified` từ 79 lên 80/120. Hai nguồn READ cùng client và cùng thời điểm mô phỏng phải báo liên kết AP có ID khác rỗng và IP–MAC nhất quán. Cờ xung đột hostname `false` → HEALTHY, `true` → FAULT. Thiếu nguồn, sai kiểu hoặc mẫu không đủ điều kiện → UNKNOWN. Các nguồn chỉ có cờ boolean và ID chuỗi. Kết quả mô tả xung đột được báo trong mẫu. Việc xác định thiết bị liên quan, nguyên nhân hay hành vi bất thường khác cần thêm bằng chứng. Chưa đo trên router.

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

Tiến độ COV-J composite (19/11/2026, `v2`): J05 đạt Simulation verified với 3/3 ca qua Core và 2 Claim `_v1`, gold tách riêng; coverage sinh từ acceptance tăng từ 75 lên **76/120**. Chỉ xét ba nguồn cùng thời điểm khi tunnel báo up và có đúng 1 peer, có ≥ 1 route kỳ vọng và thiếu 0 route, mẫu reachability có đúng 1 kết quả. Trong miền này, số peer unreachable bằng 0 cho HEALTHY, bằng 1 cho FAULT; thiếu nguồn, sai kiểu hoặc ngoài miền cho UNKNOWN. Đây là sàng lọc reachability tổng hợp trong mô phỏng; thiếu ID để ghép peer, tunnel, site và prefix, thiếu lưu lượng đầu cuối để xác minh đường đi hoặc quy nguyên nhân. Bỏ J03 vì số đếm resolver/route và cờ DoT/DoH thiếu định danh resolver, chính sách DNS kỳ vọng và đường đi quan sát được của truy vấn; chưa đủ căn cứ đánh giá DNS leak.

### COV-K — K: History, Monitoring & Incidents · 8 Skill

- [ ] **Batch COV-K** · Ưu tiên: P1. Phụ thuộc: A và snapshot/checkpoint/journal hiện có.

Tiến độ COV-K composite (19/11/2026, `v2`). K01, K02, K03, K05, K06, K07 đạt Simulation verified (18/18 ca qua Core/Verifier), nâng `simulation_verified` từ 92 lên 98/120. Mỗi workflow dùng 2 hoặc 3 mẫu cùng nguồn, tăng nghiêm ngặt theo thời gian và cách nhau tối đa 30 giây từ đầu đến cuối. Thiếu, sai thứ tự, hết TTL hoặc ngoài miền cho UNKNOWN. Ngưỡng mô phỏng gồm 2 mẫu do nguồn lịch sử báo, loss 2% cho chuyển mức, loss 5% cho điều kiện cảnh báo ba mẫu, 0 sự cố mở và loss ≤5% hoặc 100% cho hai trạng thái probe. K04 thiếu định danh và trạng thái cảnh báo để xác minh chống trùng. K08 thiếu nguồn READ khai báo retention. Timeline chỉ gồm số đếm tổng hợp ở thời điểm lấy mẫu. Chưa xác minh thời lượng mất kết nối, phục hồi bền vững, nguyên nhân hay thiết bị riêng lẻ. Kiểm tra local: check_project PASS, simulate_skills 294/294, unittest 1.067 pass, 0 fail, 5 skip Windows-only. Không có CI mới vì commit chỉ ở local.

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

Tiến độ COV-M composite (19/11/2026, `v2`). M03, M05, M06, M08 đạt Simulation verified, 12/12 ca qua Core/Verifier, nâng `simulation_verified` từ 80 lên 84/120. M03 kiểm ngưỡng tối thiểu 2 mẫu do nguồn lịch sử báo trong cửa sổ dương với topology có ít nhất 1 nút. M05 chỉ ghi nhận cờ upstream reachable. M06 đối chiếu ngưỡng loss upstream 5% và loss đường đo 2% khi upstream báo reachable, hai nguồn khác mức thì UNKNOWN. M08 dẫn evidence ID của số sự cố đang mở, ngưỡng 0. M05/M08 yêu cầu lịch sử báo ít nhất 2 mẫu trong cửa sổ dương làm ngữ cảnh. M02 thiếu bằng chứng phân biệt các giả thuyết, M04 cần kiểm thử hành vi chọn phép đo, M07 thiếu ID và liên kết sự cố theo thiết bị. Các Claim chỉ dùng cho mẫu tổng hợp cấp gateway, chưa đo trên router.

### COV-N — N: Change & Guided Remediation · 8 Skill

- [ ] **Batch COV-N** · Ưu tiên: P1; sandbox riêng. Phụ thuộc: H/I/K/L/M và transaction controller hiện có.

Tiến độ COV-N composite (19/11/2026, `v2`). N02, N06 và N08 đạt Simulation verified (9/9 ca READ qua Core/Verifier), nâng `simulation_verified` từ 89 lên 92/120. N02 sàng lọc số rule firewall không hợp lệ trên mẫu có ít nhất một rule và snapshot có revision. N06 kiểm điều kiện lập kế hoạch từ trạng thái snapshot và số mục drift, tín hiệu trái chiều cho UNKNOWN. N08 dùng số sự cố mở để hướng dẫn rà timeline và thu thập evidence READ. Mẫu thiếu, sai miền hoặc lệch thời điểm cho UNKNOWN. N05 thiếu nguồn READ về hồ sơ phê duyệt gắn với thay đổi cụ thể. Phạm vi là hiện trạng mô phỏng, chưa xác minh tác động, nguyên nhân, thiết bị riêng lẻ, tính khả thi của dry-run hay kết quả khắc phục.

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

Tiến độ COV-O composite (19/11/2026, `v2`). O01, O02, O03, O06 và O07 đạt Simulation verified (15/15 kịch bản qua Core/Verifier), nâng `simulation_verified` từ 84 lên 89/120. Mỗi Claim so một trường với một hằng số. Mẫu thiếu, sai miền, lệch thời điểm hoặc tín hiệu trái chiều cho verdict UNKNOWN. Kết quả mô tả nguồn mô phỏng. O04 thiếu phép đo DNS phía client, O05 thiếu trạng thái kết nối/dịch vụ gắn với thiết bị IoT/camera, O08 thiếu quan sát phân biệt được nhiều client. Chưa đo trên router.

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

Tiến độ COV-S legacy composite (19/11/2026, `v2`). SK02 dùng A08/B04 để sàng lọc RSSI/SNR của client đã liên kết. SK04 dùng E02/E03/E08 để sàng lọc mất gói upstream khi link đã up ít nhất 60 giây và có đúng một default route. SK08 dùng H03/H05 để sàng lọc nhiệt độ và mức sử dụng lưu trữ, kết quả chung là UNKNOWN nếu hai chỉ số khác mức. Ba Skill đạt 9/9 kịch bản qua Core/Verifier, coverage sinh từ acceptance tăng từ 98 lên 101/120. SK01 thiếu tra cứu và phân giải danh tính client. SK03 thiếu IPv4, lease của client và trạng thái dịch vụ DHCP. SK05 thiếu kết quả truy vấn DNS theo scope và tên miền. SK09 thiếu sự kiện có định danh và mốc thời gian để đối chiếu. Ngưỡng chỉ dùng cho mô phỏng, chưa đo trên router. Kiểm tra local đạt check_project PASS, simulate_skills 303/303, coverage 101/120 và unittest 1.072 pass, 0 fail, 5 skip Windows-only. Không có CI mới vì commit ở local.

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
- 2026-11-20 Tiến độ INCIDENT-GAPS: 7 kiểm tra sự cố mô phỏng GP01..GP07 (DNS, MTU/MSS, IPv6, quá tải, NAT hai lớp/CGNAT, radar DFS, bám AP xa) có 6 port READ mới và chạy trong replay_sim; không thuộc 120 Skill, báo riêng `incident_checks_simulated`; chưa ghép kịch bản incidents_v1.
