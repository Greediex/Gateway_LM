# LLM kết nối Skill trên laptop

Mục tiêu: nối các thành phần hiện có để người dùng hỏi tự nhiên, không phải chọn Skill thủ công. Không tăng số Skill đã có backend.

Luồng thực tế: `/api/chat` (Linux, with_llm=true) → `SkillChat` → `OllamaGoalModel.choose_skills` → `SkillLauncher.run` → `RuntimeSkillBridge` → cùng `ReadSession`/GraphRunner/shared execution kernel → Verifier → `RCAAgent.assess_session` → model chọn tiếp hoặc chọn verified finding để trả lời.

## Cách chạy và hỏi

Dùng hướng dẫn Linux trong README; chạy Ollama với `qwen3:4b` đã có sẵn, rồi mở Web. Chat Linux bật LLM mặc định. Ví dụ: “Gateway laptop là gì?”, “Kiểm tra DNS”, “Wi-Fi và gateway hiện thế nào?”. Nút chọn Skill thủ công vẫn là công cụ kiểm tra riêng, không cần dùng trước khi chat.

Cùng `session_id` giữ state/runner/budget và evidence còn hạn qua nhiều câu hỏi. Đổi source/xóa chat/chọn gợi ý mới sẽ giải phóng phiên trước. HTTP 410 xóa handle cũ; gửi lại để tạo phiên mới. Model/endpoint cấu hình bởi server (`GATEWAY_LM_CHAT_MODEL`, mặc định `qwen3:4b`, loopback Ollama), model name từ request không được dùng cho luồng này.

## Vai trò từng thành phần

- Bộ tìm kiếm catalog hiện có tra toàn bộ 120 Skill thiết kế, kết hợp BM25 (0,70) và graph diffusion (0,30) để lấy tối đa 6 ứng viên theo thứ hạng; prompt chứa các mục liên quan, toàn bộ action runnable và các mục chưa hỗ trợ được yêu cầu rõ. Trace `advice[].catalog_retrieval` ghi method, trọng số, thứ hạng ứng viên, điểm lexical/graph và trạng thái catalog. Cạnh PROPOSED chỉ phục vụ liên quan khi truy xuất, không trở thành cạnh phụ thuộc thực thi hoặc cấp quyền. Retrieval không cấp quyền thực thi. Đầu ra có đúng một quyết định: đo các ID đã cấp, chọn finding IDs để trả lời, hoặc hỏi rõ/báo Skill chưa hỗ trợ.
- Core kiểm proposal lại, không nhận Function/command/target/quyền từ model. Chọn lại Skill đã thử trong lượt, ID lạ hoặc enum sai bị từ chối; model có tối đa hai lần proposal sai trước khi dừng. Không fallback sang replay.
- `ReadSession.refresh` probe lại và thu hồi facts từ producer không còn hỗ trợ. Session context/ACL/contracts/bindings/diagnostics thay đổi sẽ đóng phiên.
- `RCAAgent.assess_session` dùng ClaimBook, state và runner hiện có; chỉ đọc facts đã verified, refresh capability trước khi đánh giá. Workflow/Claim theo scope của Skill đã chọn nằm trong `config/skill_launcher/live.diagnostics.json`, có approval digest. Không tạo Runner hay gọi tool riêng trong assessor.
- Model nhận findings, các pattern/predicate đã kiểm chứng và missing-goal candidates của RCA. Model có thể chọn thêm Skill nếu phần còn lại của câu hỏi chưa đủ dữ liệu. Hoàn tất Skill đã chọn không đồng nghĩa hoàn tất toàn bộ yêu cầu; model vẫn có thể phối hợp thêm Skill hoặc evidence còn hạn từ lượt trước.
- `missing_goal_actions` chỉ liệt kê producer từ action đã đăng ký, capability hiện còn AVAILABLE và chưa thử trong lượt. Các output tùy chọn không khả dụng không được quảng bá qua action DEGRADED. Đây là dữ liệu gợi ý cho model, không tự cấp quyền hay tự thực thi. Khi facts đã đủ theo intent đã nhận diện, bỏ mapping dư khỏi prompt; TTL/coverage gates vẫn giữ nguyên.
- Model chọn nội dung/trọng tâm bằng finding IDs. Tầng `grounded_answer` tiếp tục dùng cùng model local: chọn field IDs đã xác minh rồi chọn câu diễn đạt có placeholder. Validator đối chiếu toàn bộ quan hệ field–nhãn–giá trị bằng một ngữ pháp có kiểm soát; các giá trị do Core chèn sau kiểm tra. Câu đổi SSID thành BSSID, phủ định không có căn cứ, thêm số/nhận định hoặc bỏ phần yêu cầu đều bị từ chối và dùng renderer theo ngữ cảnh. Đây không phải chứng minh ngữ nghĩa của văn bản tự do bất kỳ.
- Metadata intent được pin với deployment đặt mức bao phủ tối thiểu, độc lập với Skill model đã chọn. Các phần yêu cầu ghép bằng liên từ/danh sách nhưng chưa nhận diện được vẫn được báo chưa xác minh. Đây là kiểm tra bảo thủ, không phải bộ hiểu ngôn ngữ hoàn chỉnh. Các số liệu Wi-Fi được render từ facts đã xác minh, gồm SSID/BSSID, kênh, tần số và signal phần trăm.

## Giới hạn

Mặc định tối đa 4 vòng lập kế hoạch mỗi lượt (vòng cuối chỉ kết thúc), tối đa 3 Skill/batch; tầng trả lời có tối đa 2 lượt gọi bổ sung, mỗi lượt tối đa 12 giây và không vượt thời gian còn lại; budget session giữ nguyên 300s/24 calls/64 plans. Web Qwen 4B có deadline 180s; constructor mặc định 120s cho các caller khác; khởi tạo model và inference nhận timeout không vượt thời gian còn lại (mỗi RPC tối đa 90s cho qwen3:4b, model khác 60s). Chat RPC giới hạn response 64KiB, model metadata 1MiB. Local model có xác minh parameter count: riêng `qwen3:4b` tối đa 4,5B (metadata thực khoảng 4,02B), model khác giữ giới hạn 3B; không tải model hoặc gọi cloud tự động. Một model request và một lượt hỏi mỗi phiên được xử lý đồng thời; HTTP 429/409 báo bận, không xếp hàng vô hạn.

Nếu finding đã được đưa cho model hết TTL trong lúc suy luận, ứng dụng được phục hồi tối đa một đợt mỗi lượt, bằng action READ đã đăng ký qua cùng ReadSession/Core và budget. Không tăng TTL hoặc chuyển context. Nếu vẫn thiếu dữ liệu hoặc không còn thời gian/capability/budget, trả PARTIAL/NEEDS_INPUT với lý do; không dùng số đo hoặc RCA proof hết hạn. Trace phân biệt `recovery_attempts`/`recovery_runs` (đọc lại TTL) và `repairs` của Runner, không coi các bộ đếm này là sự cố đã phục hồi.

Câu hỏi field như SSID/BSSID/kênh chỉ trả field được hỏi; dữ liệu phụ vẫn ở Trace. Câu hỏi chẩn đoán có nhận định RCA theo bằng chứng được chọn và giới hạn chưa đủ kết luận nguyên nhân. Cảnh báo route khác Wi-Fi chỉ xuất hiện trong ngữ cảnh chẩn đoán, kèm evidence route; không chen vào lookup SSID. Không khẳng định SSID không đổi nếu chưa có bằng chứng so sánh.

Trước khi bắt đầu tổng hợp, host kiểm tra TTL còn đủ cho ngân sách hai lượt và thời gian còn lại; thiếu cửa sổ freshness thì trả renderer ngay, không đọc lại dữ liệu chỉ để phục vụ diễn đạt. Sau mỗi lượt tổng hợp, host kiểm lại session/context và freshness/ID của proof. Draft cũ bị bỏ nếu proof đổi hoặc hết hạn; dùng tối đa một đợt phục hồi hiện có, rồi dựng fallback từ snapshot mới, không gọi lại LLM vô hạn. `answer_synthesis` ghi số lần gọi, lý do fallback và `used_llm`; `model_calls` tính cả tầng trả lời. `answer_kind` và `diagnostic_status` tách nhận định khỏi `case_status` đo đạc. Giao diện đặt metadata trong details đóng mặc định, vẫn giữ Trace đầy đủ. Biến server `GATEWAY_LM_ANSWER_SYNTHESIS=0` tắt hai lượt bổ sung, vẫn giữ renderer theo ngữ cảnh. Không thêm AgentLoop/CapabilityRegistry hoặc endpoint/model riêng từ gói patch.

Live vẫn chỉ có SK01/A08 scope local và 6 action laptop. 118 thiết kế chưa có backend live, bao gồm RSSI/SNR, router health và inventory toàn mạng. Model có thể tra chúng để báo thiếu capability, không thực thi bằng dữ liệu giả. Custom IP/MAC targets và WRITE không được thực thi. Câu hỏi ngoài khả năng được hỏi rõ/báo chưa hỗ trợ; đây không phải cam kết trả lời đúng mọi câu hỏi bất kỳ.

Các Claim chỉ xác nhận route, association, mất gói ICMP và phân giải DNS đã quan sát; HEALTHY_OBSERVED giới hạn theo từng workflow. Không suy ra sức khỏe router, causal root cause, tốc độ tải hay sự cố đã phục hồi. Trace có Skill đã chọn, số calls/reuse, DAG, evidence và từng đánh giá RCA.

## Kiểm chứng

`tests/test_skill_chat.py` kiểm multi-Skill, vòng tiếp theo nhận evidence/RCA, session reuse, question focus, unsupported/WRITE/target/ID injection, model outage, vòng lặp/budget, stale facts trong lúc suy luận, ACL/context/Claim drift, capability revocation và source separation. HTTP tests kiểm dispatch và giữ model configuration ở server. Các test này dùng model/provider double, không giả làm chất lượng LLM thật.


[Kiểm tra Qwen thật trên laptop](reports/LLM_SKILL_CHAT_ACCEPTANCE_20261116.json): DNS chọn `laptop.dns.inspect`, 3 calls; câu hỏi Wi-Fi + gateway chọn 2 Skill, 4 calls, tái sử dụng route; SNR trả PARTIAL, nêu rõ B04 chưa hỗ trợ. Các ví dụ mất khoảng 26–34 giây trên CPU ở lần kiểm tra này, không phải benchmark p50/p95 hoặc cam kết latency. Một lượt CPU bận làm evidence hết TTL đã bị từ chối; cần đo lại. Browser localhost đã hiển thị luồng chọn Skill/verified evidence/RCA trong Trace.

Nghiệm thu ngày 16/11/2026: full unittest discovery **734 tests: 729 pass, 5 Windows-only skips**; `scripts.check_project`, JS syntax/lifecycle checks và independent review đạt. Đây là kết quả lịch sử trước P0. Bộ semantic dev/test mới có version riêng ở `benchmarks/skill_chat_v1/`, đóng băng trước tuning; nhãn sinh bằng chương trình chưa được người ngoài thẩm định. Harness báo riêng model double/Qwen thật và provider replay/live; không dùng nhãn test để sửa runtime. Kết quả P0 hiện hành được ghi duy nhất tại [TODO gốc](../TODO.md), cùng các báo cáo JSON nghiệm thu.


## Tích hợp READ sau audit 17/11/2026

Chat production dùng `ChatContext.trusted_default` qua singleton local: semantic catalog + runbook đúng `linux-laptop/linux-read-docs-v1`; `GATEWAY_EMBED_MODEL` chỉ nhận ở startup, không từ HTTP. LocalOllamaEncoder pin digest, từ chối model không có capability embedding/redirect/output sai. `catalog_semantic` và `function_semantic` trong `runtime_features` là hai tầng khác nhau; ERROR có thể đi kèm fallback GoS, không báo embedding đã thành công. Failed catalog indexing chỉ thử một lần trong một lượt hỏi; không cache chỉ mục dở dang.

TaskRuntime.run_session không tạo Runner mới. Lookup chỉ đánh giá facts; diagnostic cho phép RCA đọc thêm candidate goals trong tập port đã chọn, tối đa hai bước và deadline còn lại. Assessment/diagnosis cấp mạng vẫn khác observation predicates; câu trả lời không suy causal root cause từ MEASURED. Các đề xuất goal của LLM phải thuộc registry READ được cấp quyền và có trích đoạn khớp câu hỏi.

Session live bật repair budget 2 với metadata max_attempts=2. Mỗi retry đi qua probe/ACL/Verifier, mỗi plan attach tiêu thụ plan budget. Deadline của lượt hỏi được áp dụng cả trong một Skill nhiều Function, trong recovery và trong RCA. Semantic ranking lỗi chỉ đổi phương pháp xếp hạng, không đổi contract hoặc quyền.

`GET /api/skills/history` trả tối đa 20 tóm tắt, không trả raw conversation/network values. `POST /api/skills/resume` chỉ nhận `{session_id}`; không nhận path/key/budget/evidence. Checkpoint và journal dùng SessionStorage để khôi phục cùng case/context/OS boot với budget và deadline còn lại; close tạo tombstone bền. Signed files không chống trusted owner rollback toàn bộ storage; không hỗ trợ nhiều process cùng ghi một phiên. Untrusted-text ports không được checkpoint nên một số trường cần đo lại sau restore.

`runtime_features`, `goal_proposal`, `task_trace`, `function_retrievals`, `persistence` và `runbooks` cho biết các tầng thực sự đã được dùng. ReAct và GoS legacy vẫn là đường thử nghiệm thay thế; không chạy đồng thời thêm một executor vào session. Cloud/WRITE không được bật từ chat và cần cấu hình/operator flow riêng; monitor_window không biến thành collector/Incident service chỉ do có History.
