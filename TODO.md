# Gateway LM v2 — TODO hiện hành

Cập nhật **17/11/2026**, nhánh **v2**, baseline trước P0 **`5884be4`**.

**Mục tiêu:** hoàn thiện chất lượng luồng hỏi → LLM tra catalog/chọn nhiều Skill → ReadSession/GraphRunner → Verifier → RCAAgent → chọn tiếp hoặc trả lời. Tận dụng các thành phần đã có, ưu tiên chạy tốt trên laptop.

## Quy tắc cập nhật

**Chỉ dùng file `TODO.md` ở gốc repo để ghi kế hoạch, backlog, checklist và tiến độ công việc.** Mỗi lần cập nhật phải sửa trực tiếp file này, giữ mã task còn hiệu lực và bỏ mục cũ/trùng. Không tạo file kế hoạch mới theo ngày/task hoặc sao chép danh sách việc sang roadmap/status/worklog khác, kể cả khi workflow/skill gợi ý tạo file riêng. Chỉ tách sang file khác khi người dùng yêu cầu rõ ràng. Tài liệu kỹ thuật và báo cáo nghiệm thu chỉ mô tả thiết kế/kết quả, không chứa backlog song song.

## Đã có

- [x] Catalog 120 Skill thiết kế, mapping/availability và deployment READ có version/approval pins.
- [x] Linux laptop live: 8 Functions; SK01/A08 scope local và 6 action laptop riêng. Replay B02/B03/B05 tách nguồn.
- [x] Shared ReadSession, GraphRunner/Verifier, evidence có TTL, context/ACL/budget gates và tái sử dụng dữ liệu còn hạn.
- [x] Chat LLM local tự tra catalog, chọn/phối hợp Skill, nhận evidence và đánh giá từ RCAAgent trong cùng phiên.
- [x] Web chat/Trace, launcher thủ công, CLI/API; README và nghiệm thu Qwen thật trên laptop.

**Phạm vi đã xác minh:** 120 hàng thiết kế không đồng nghĩa 120 Skill chạy được. Live hiện có 2 mapping thiết kế local + 6 action laptop; 118 thiết kế còn UNAVAILABLE. Source 72 READ contracts vẫn PROPOSED, 203 cạnh đề xuất chưa được duyệt. [Bằng chứng nghiệm thu](docs/reports/LLM_SKILL_CHAT_ACCEPTANCE_20261116.json).

## P0 — Hoàn thiện luồng chat trên laptop

- [ ] **CHAT-01 — Bao phủ đủ ý định người dùng.** Kiểm tra câu hỏi đơn, nhiều yêu cầu, câu hỏi tiếp nối và yêu cầu có phần chưa hỗ trợ. LLM phải phối hợp thêm Skill/evidence khi còn thiếu; hoàn tất một Skill không được coi là hoàn tất cả câu hỏi. **Nghiệm thu:** trả lời đúng trọng tâm từng phần, hoặc chỉ rõ phần chưa xác minh; giữ khả năng dùng facts còn hạn từ lượt trước.
- [x] **CHAT-02 — Xử lý evidence hết hạn trong lúc suy luận.** Làm rõ điều kiện đo lại/hỏi lại khi model chậm hoặc context thay đổi; mọi lần đo lại vẫn qua ReadSession và budget hiện có. **Nghiệm thu:** không trả số đo/Claim hết hạn, không tăng TTL để che độ trễ, không mất kết quả đã xác minh còn dùng được.
- [x] **CHAT-03 — Dừng và xử lý lỗi nhất quán.** Hoàn thiện các tình huống timeout, output model sai, mất capability, không có tiến triển, vòng chọn lặp và hết budget; chỉ dùng phương án READ thay thế đã được đăng ký/cấp quyền. **Nghiệm thu:** dừng hữu hạn, lý do rõ, không fallback live sang replay, không báo hoàn thành khi thiếu dữ liệu.
- [x] **PERF-01 — Đo và giảm độ trễ thực tế.** Profile riêng thời gian tra catalog, inference, probe/Function, Verifier và RCA; tối ưu prompt/cache còn hợp lệ và lời gọi trùng. Kiểm giới hạn đồng thời, output, timeout và giải phóng phiên. **Nghiệm thu:** có số đo cold/warm, p50/p95, tool calls và tài nguyên laptop trước/sau; không bỏ gates để tăng tốc.
- [x] **EVAL-01 — Đánh giá độc lập trước khi mở rộng.** Tạo bộ câu hỏi và replay có nhãn, tách dev/test trước khi tune; gồm đa ý định, ngoài khả năng, evidence cũ, sai scope, lỗi tool và prompt injection. **Nghiệm thu:** báo Skill/Function selection, độ đầy đủ câu trả lời, RCA/abstention, proposal sai, calls và latency; phân biệt rõ test double, Qwen thật, replay và live. Các ví dụ nghiệm thu hiện có chưa phải holdout benchmark.

**Trạng thái 17/11/2026: hoàn tất 4/5 mục P0; CHAT-01 còn mở.** Đã đẩy runtime `b64cbe8` lên `v2`; [CI cho đúng runtime commit đã đạt](https://github.com/Greediex/Gateway_LM/actions/runs/43999117890). Full regression **768 tests: 763 pass, 5 Windows-only skips**; hygiene và review độc lập đạt. Không mở rộng kiến trúc hoặc tăng số Skill có backend.

- **CHAT-01 chưa nghiệm thu chất lượng tổng quát:** đã có guard bao phủ nhiều ý/phần chưa nhận diện, scope laptop, SSID/kênh và lọc finding phụ khỏi câu trả lời. Nhưng Qwen thật trên test đóng băng chỉ **11/14 lượt đủ phần trả lời (78,6%)**, abstention **12/14 (85,7%)**. Skill selection precision/recall **50,0%/83,3%**, Function selection **46,4%/89,7%**. Model vẫn bỏ sót hoặc chọn đo dư; không được coi catalog 120 hàng hay test giả đạt là chứng minh trả lời đúng mọi câu. Tiếp tục cải thiện task này bằng dev và một phiên bản test mới độc lập; không tune theo hay sửa nhãn bộ test đã báo cáo.
- **CHAT-02/03:** đọc lại TTL tối đa một đợt qua cùng Core/session/budget; không kéo dài TTL. Proposal sai được sửa hữu hạn; timeout/output/concurrency/close/context gates đã có negative tests. Model nhận producer theo capability hiện có; action DEGRADED không quảng bá output tùy chọn đã mất capability. Các bộ đếm đọc lại/Runner repair không phải bằng chứng khắc phục sự cố.
- **PERF-01:** cùng 4 câu × 3 lần × cold/warm, cùng profiler/fixture/Qwen CPU; 106 hash source/config giữ nguyên khi đo AFTER. Đủ finding đúng scope **12/24 → 24/24**, đây là profile dev lặp lại, không phải điểm holdout. Các ô hợp lệ trước/sau: cold gateway p50 **41,16 → 35,65s**, DNS **41,55 → 39,72s**, Wi-Fi+gateway **45,43 → 35,12s**. **DNS warm tăng 8,09 → 13,26s (+63,9%), calls 0 → 4**; cold DNS calls 3 → 7, RSS Ollama tăng khoảng 2,15 → 2,29–2,33 GiB. Không tuyên bố mọi latency đều cải thiện. p95/phase/CPU/RAM/calls và giới hạn n=3 nằm trong [báo cáo so sánh](docs/reports/P0_PERF_COMPARISON_20261117.json); network provider ở profile là synthetic.
- **EVAL-01:** dev/test `benchmarks/skill_chat_v1/` được đóng băng trước tuning, giữ nguyên SHA/nhãn; nhãn do agent soạn, chưa có thẩm định ngoài. [Qwen thật + provider replay, test 14 lượt](docs/reports/P0_EVAL_TEST_QWEN_20261117.json): **0 lỗi runtime, 0 proposal sai schema/ID, RCA proof hợp lệ 100%, không kết luận causal root cause**; 57 READ calls, chỉ 5/14 lượt nằm trong khoảng calls chuẩn tối thiểu của dataset (khác budget an toàn của Core); latency p50/p95 **24,02/30,40s**. Đọc lại TTL 1 đợt. [Dev model giả](docs/reports/P0_EVAL_DEV_SCRIPTED_20261117.json) / [test model giả](docs/reports/P0_EVAL_TEST_SCRIPTED_20261117.json) chỉ kiểm tích hợp, tách rõ khỏi chất lượng Qwen. Không dùng kết quả test để tune lại candidate này.
- **Laptop live:** [API thực với Qwen](docs/reports/P0_LAPTOP_LIVE_20261117.json), DNS và Wi-Fi+gateway đều MEASURED, chỉ chọn finding đúng câu hỏi, evidence còn hạn; lần lượt **43,17s/7 calls** và **23,13s/3 calls**, lượt thứ hai có một đợt đọc lại TTL. Phiên kiểm tra đã đóng; raw SSID/BSSID/IP chỉ lưu trong `runs/` bị Git bỏ qua. Hai ví dụ này không phải benchmark hoặc nghiệm thu firmware. Web thử tại `http://127.0.0.1:8767/`.


## Chuyển model theo yêu cầu

- [x] Chuyển chat laptop mặc định sang `qwen3:4b`; đã tải Q4_K_M và xác minh 4.022.468.096 parameters, giữ kiểm tra model local và parameter count. Regression 788 tests: 783 pass, 5 Windows skips; hygiene đạt. Lượt API cold chạm timeout 60s; lượt warm với Qwen 4B thật đạt MEASURED/model_answer, trả đúng phạm vi SSID, 72,79s, 4 model calls và 6 READ calls. Đây là một ví dụ live, chưa chứng minh chất lượng/latency tốt hơn. [CI runtime 555f2e2](https://github.com/Greediex/Gateway_LM/actions/runs/44051845760) đang chạy. Kết quả 1.7B trước đây vẫn là baseline cũ, không suy thành chất lượng 4B.

## Đã sửa câu trả lời theo grounded patch

Phạm vi đã được yêu cầu: sửa CHAT-01/UI-01 trong luồng hiện có; không cài AgentLoop/CapabilityRegistry thứ hai. Giữ nguyên dữ liệu/nhãn EVAL1000 và các kết quả baseline; lượt Qwen dài chưa khởi chạy.

- [x] Tái hiện SSID bị lẫn BSSID/route, số đo hết hạn sau synthesis và nhãn field sai; thêm regression với Core thật, model/provider giả.
- [x] Tích hợp field projection và hai bước LLM chọn evidence/diễn đạt; chỉ nhận câu có quan hệ field–giá trị được đối chiếu, còn lại fallback. Cùng local model, deadline/model slot/response limits; không gọi tool từ tầng trả lời.
- [x] Kiểm lại snapshot/context sau synthesis; bỏ draft khi evidence hết hạn/đổi ID, dùng lại phục hồi một đợt hiện có và dựng fallback từ facts mới. Export đúng evidence IDs, số RPC và lý do fallback.
- [x] Đưa metadata vào details đóng mặc định; phân biệt đã đo với chưa đủ chẩn đoán. Kiểm regression, API/Qwen và trình duyệt; cập nhật README, đẩy v2/CI. Sau khi cố định code mới tiếp tục EVAL1000.

**Kết quả sửa hiện tại:** các regression Core thật/provider-model giả đã đạt, gồm expiry ở cả hai lượt synthesis, thiếu cửa sổ TTL, deadline, đóng phiên và đổi nhãn SSID thành BSSID. Full local và [CI cho runtime `2253f2b`](https://github.com/Greediex/Gateway_LM/actions/runs/44044689069) đều đạt 787 tests: 782 pass, 5 Windows skips; code đã đẩy lên `v2`. DOM test dùng hàm render production đã đạt; UI thực đã hiển thị “Chưa đủ chẩn đoán” và details đóng. Qwen thật đã diễn đạt SSID bằng placeholder trong thử nghiệm synthetic; [lookup laptop thật](docs/reports/GROUNDED_ANSWER_LIVE_20261117.json) trả SSID đúng scope, proof còn hạn, 44,21s/7 READ calls, 2 lượt model lập kế hoạch, bỏ synthesis vì TTL không đủ; không coi đây là benchmark hoặc cam kết giảm latency. Các kết quả P0/Qwen 11/14 ở trên vẫn là baseline cũ, không nâng thành điểm của bản sửa này.

**EVAL1000:** giữ nguyên 13 file của ZIP (SHA ZIP `11acea741da2b033496fb41b44442ad9e4e12e359f305b90e8bfa9a2aa913d20`), dataset SHA `a90e39c13250ed7cdfb548816311c527e308da17edb8066c43483b6ce4259cc5`. Validate 1000 cases/1017 turns/120 design IDs và 23/23 unit tests đạt; đã có test adapter để CI chạy các kiểm tra offline này. Baseline trên runtime `1d41b4c`: retrieval 390/390 cases đã chạy, strict exact-pass 0% do luôn trả top-5 so với gold 1–3; precision/recall 16,97%/51,28%, không phải điểm LLM. Fault 290/290 đã chạy: 49,66% pass theo rubric, 0 case scorer gắn cờ safety; giữ nguyên kết quả fail để audit, không sửa label. Có cả hạn chế fixture DNS chưa available và guard scope bắt nhầm câu phủ định, không được quy mọi fail là lỗi TTL. Qwen catalog dev smoke 1 case đã chạy (~81,5s, fail), chưa phải full; toàn bộ catalog-LLM/E2E Qwen dài chưa khởi chạy trong lúc sửa/runtime chưa cố định. Kết quả riêng nằm trong `runs/eval1000/`, không commit raw output và không trộn ba track thành accuracy chung.

## P1 — Hoàn thiện khả năng và trải nghiệm hiện có

- [ ] **DATA-01 — Rà soát dữ liệu laptop còn thiếu.** Đối chiếu từng Skill với nguồn đọc thật đang khả dụng; ghi rõ RSSI/SNR, roaming/history và dữ liệu nào chỉ có từ AP/router. **Nghiệm thu:** có mapping nguồn/đơn vị/scope/TTL và gap cụ thể; signal % không thay RSSI/SNR, throughput không suy từ tốc độ AP quảng bá.
- [ ] **DATA-02 — Hoàn thiện catalog theo batch có nguồn dữ liệu.** Review semantic contracts/workflows/Claims của Wi-Fi, Devices, DHCP; dùng lại Registry, adapter và Claim Engine. Skill composite cần workflow/evidence hợp lệ; chỉ đưa cạnh đã review vào execution. **Nghiệm thu:** mỗi batch có exact mapping, schema/binding tests và acceptance riêng; không tạo Function giả để đủ 120 hay nâng PROPOSED thành capability tự động.
- [ ] **UI-01 — Làm rõ kết quả và tiến trình chat.** Rút gọn câu trả lời đúng câu hỏi; hiển thị đang suy luận/đo, Skill đã chọn, phần còn thiếu và bước tiếp theo. Giữ chi tiết evidence, thời gian/TTL, RCA và điều kiện dừng trong Trace. **Nghiệm thu:** người dùng phân biệt được phép đo hoàn thành, chẩn đoán chưa đủ dữ liệu và phiên hết hạn; không cần đọc tên kỹ thuật để biết phải làm gì tiếp.

## Để sau mốc laptop

- Adapter OpenWrt/Ubus và chọn thiết bị Client–AP–Router: chỉ mở batch đã có mapping/backend được review, nghiệm thu mock và firmware thật riêng.
- History bền, Monitoring/Alerts/Incident: triển khai theo nhu cầu sau khi luồng chat và đánh giá laptop ổn định; dùng lại snapshot/checkpoint/journal hiện có.
- WRITE không thuộc mốc READ này; vẫn giữ cơ chế kiểm soát hiện có.

## Thứ tự và điều kiện chốt

**CHAT-01 → CHAT-02/CHAT-03 → EVAL-01 → DATA-02**. PERF-01 thực hiện cùng các task chat; DATA-01 cung cấp danh sách gap cho DATA-02; UI-01 bám các trạng thái API đã chốt.

Mỗi task phải có kết quả kiểm tra phù hợp, negative paths và giới hạn được ghi rõ; giữ frozen data/benchmark và contracts v0.1. Execution tiếp tục qua shared Core/Verifier. Chỉ đánh dấu hoàn tất trong phạm vi đã nghiệm thu, không suy từ CI/replay sang hỗ trợ firmware.

[Luồng LLM–Skill–RCA](docs/LLM_SKILL_CHAT.md) · [Launcher/session](docs/LAPTOP_SKILL_LAUNCHER.md) · [Nghiệm thu local](docs/reports/LLM_SKILL_CHAT_ACCEPTANCE_20261116.json)
