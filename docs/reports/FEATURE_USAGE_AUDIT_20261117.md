# Gateway LM v2 — Audit tính năng và mức sử dụng

Ngày kiểm tra: **17/11/2026**, nhánh **v2**, source commit **`9f1ab6ba9f6cd487b038e3abf1bbf6bc622ee289`**. Phạm vi: repo hiện tại và Web Linux laptop tại `127.0.0.1:8767`. Đây là báo cáo đọc code, Graphify và kiểm tra có giới hạn; không thay đổi luồng thực thi.

## Cập nhật sau tích hợp READ

Các bảng audit bên dưới là snapshot source `9f1ab6ba` trước triển khai, không phải trạng thái mới sau tích hợp. Bản mới đã nối TaskRuntime/RCA cùng phiên, GoS/Hybrid READY selection, bounded retry/repair, BoundedGoalProposer, semantic local và runbook đúng profile, checkpoint/journal có chữ ký và API/UI lịch sử/khôi phục. Nguồn dữ liệu laptop và 118 thiết kế UNAVAILABLE không đổi. Semantic có thể timeout và fallback được ghi rõ. Cloud, WRITE, firmware, monitoring collector/Incident vẫn chưa được nghiệm thu; không bật bằng cách bỏ gates.

## Kết luận tại thời điểm audit

Hệ thống có nhiều thành phần hơn những gì luồng chat đang dùng. Đường READ laptop đã nối tương đối rõ; các phần persistence, semantic search, bộ repair nâng cao, cloud và WRITE vẫn ở mức component/opt-in hoặc mock. Không có cơ sở coi đây là Agent trả lời đúng mọi câu, hay coi 120 Skill thiết kế là 120 backend đang chạy.

**Mức đánh giá:** “Đang dùng” = được nối vào composition/entrypoint hiện tại; “Một phần” = đã nối nhưng chỉ dùng một giao diện hoặc grammar/phạm vi hẹp; “Opt-in/component” = chạy được qua CLI/API riêng/test nhưng không nằm trong chat mặc định; “Replay/thiết kế” = có mô phỏng hoặc metadata, chưa có dữ liệu/hardware thật phù hợp. Không gán phần trăm hoàn thành theo số file hay số test.

## Graphify và cách xác minh

- Đã chạy Graphify thực: `graphify extract . --code-only --out . --max-workers 4`, sau đó `cluster-only . --no-label`, và `explain SkillChat` / `explain LocalSemanticIndex`.
- Python runtime: venv có sẵn; Graphify source: `/home/nangtuan/Documents/Codex/tools/graphify`. Code-only không gọi LLM hay dịch vụ cloud.
- Graph hiện tại: **3,886 nodes, 9,119 edges, 191 communities**; 8.690 cạnh EXTRACTED, 429 INFERRED. Số cộng đồng có thể thay đổi giữa các lần clustering; không phải số tính năng.
- Graphify cảnh báo **1 file PowerShell không trích xuất được** vì thiếu `tree_sitter_powershell`. Không coi map là đầy đủ tuyệt đối cho Windows.
- Cạnh gọi/import/uses chỉ gợi ý phụ thuộc tĩnh, không chứng minh runtime activation. Các kết luận “chưa nối” còn được đối chiếu với code khởi tạo, nhánh HTTP và cấu hình của SkillChat/ReadSession.
- [Mở graph tương tác](</home/nangtuan/Documents/ChatGPT/Just Test/Gateway_LM_v2_20261116/graphify-out/graph.html:1>) · [Báo cáo Graphify](</home/nangtuan/Documents/ChatGPT/Just Test/Gateway_LM_v2_20261116/graphify-out/GRAPH_REPORT.md:1>) · [JSON graph](</home/nangtuan/Documents/ChatGPT/Just Test/Gateway_LM_v2_20261116/graphify-out/graph.json>).

Ví dụ: graph tìm thấy TaskRuntime chủ yếu được khởi tạo từ `test_task_runtime.py`; CloudHypothesisAdapter từ test delegation. Checkpoint/journal có import/hook trong GoalAgent nhưng không được khởi tạo ở SkillChat. Những quan sát này được xác minh lại bằng đọc code, không suy từ “ít cạnh” thành “code chết”.

## Những phần đã dùng trong chat hiện tại

| Tính năng | Kết nối hiện tại | Dùng được ở mức nào | Bằng chứng |
|---|---|---|---|
| Catalog + kiểm tra khả năng | Đang dùng | 120 thiết kế + 6 action laptop; phiên mới có 8 READY, 118 UNAVAILABLE. READY là khả năng đo, không phải đã trả lời đúng mọi câu. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/application/skill_launcher.py#L44) |
| Đọc dữ liệu laptop | Đang dùng | 8 Function AVAILABLE: Wi-Fi, association, identity, IPv4, route, ping gateway/Internet, DNS. Scope chỉ laptop; không suy ra tài nguyên router hay danh sách mọi client. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/skill_expansion/deployment.py#L56) |
| Function Contract v0.2 / binding / ACL | Đang dùng | Registry/policy/backend pins, schema, context và quyền READ được kiểm tra; không có quyền shell do LLM cấp. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/command_catalog/runtime.py#L23) |
| ReadSession + GraphRunner + Verifier | Đang dùng | Compiler lập DAG theo phụ thuộc, chạy qua execute_ready_once, facts có provenance/TTL; giữ state/budget qua các Skill. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/command_catalog/session.py#L111) |
| LLM chọn nhiều Skill và chọn tiếp | Đang dùng, giới hạn | Qwen3 4B local; nhận evidence/RCA mới sau đo, tối đa 4 vòng và 120s. Cách xác định phần yêu cầu còn phụ thuộc phrase metadata; chưa đủ nghiệm thu Agent tổng quát. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/application/skill_chat.py#L225) |
| BM25 + graph catalog retrieval | Đang dùng | Top-6 thiết kế được xếp hạng 0,70 lexical + 0,30 graph, cộng các action khả dụng; trace có điểm. Cạnh PROPOSED không cấp quyền thực thi. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/ollama_goal_model.py#L110) |
| RCA/Claim trong chat | Đang dùng một phần | Chat dùng assess_session trên facts có sẵn. LLM điều phối phép đo tiếp theo; chưa gọi vòng RCAAgent.run tự thu thập đầy đủ. API chat luôn diagnosis=None; không chứng minh causal root cause. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/rca_agent.py#L127) |
| Trả lời có grounding | Đang dùng có điều kiện | Chọn field + câu placeholder trong tối đa 2 RPC khi còn đủ TTL/deadline; bỏ draft sai/expired. Cách diễn đạt vẫn theo grammar hẹp; fallback renderer có thể được dùng thường xuyên. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/application/grounded_answer.py#L159) |
| Tái sử dụng fact và đo lại TTL | Đang dùng | Tái sử dụng evidence còn hạn, tối đa một đợt phục hồi TTL cùng session/budget. Đây không phải sửa sự cố mạng. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/application/skill_chat.py#L188) |
| Web chat, launcher, trace | Đang dùng | HTTP loopback, Skill thủ công, details/Trace; MEASURED khác chẩn đoán. Phiên nằm trong bộ nhớ; khởi động lại mất phiên. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/web_gateway/server.py#L433) |
| Benchmark/evaluation | Công cụ chạy được, nghiệm thu chưa đủ | Có EVAL1000, scorer, runner và dev/test; các baseline là lịch sử. Full Qwen 4B EVAL1000 chưa hoàn tất, không có accuracy tổng quát mới. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/scripts/evaluate_skill_chat.py#L199) |

## Có code nhưng chưa tận dụng trong luồng chính

| Tính năng | Kết nối hiện tại | Dùng được ở mức nào | Bằng chứng |
|---|---|---|---|
| Semantic embedding / hybrid retrieval | Có code, chưa nối chat | LocalSemanticIndex + SentenceTransformer local directory; GoalAgent CLI có --method hybrid. Test dùng encoder giả; chưa chứng minh model embedding thật đã được cấu hình hoặc chất lượng retrieval. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/semantic.py#L113) |
| GoS / Function graph ranking | Có đường replay/API, không phải mặc định chat | GraphRegistry có lexical-seed GoS/PPR/rerank; GoalAgent/RCA replay dùng được. Graph catalog mới nối là một projection khác, không đồng nghĩa toàn bộ GoS được dùng trong SkillChat. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/graphs.py#L283) |
| Planner repair nâng cao | Có code, tắt ở ReadSession live | GraphRunner có retry/local repair/global replan ở các luồng khác; ReadSession hiện tạo Runner với max_repairs=0. Vòng LLM chọn Skill khác và TTL refresh không phải bật bộ repair này. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/command_catalog/session.py#L43) |
| RCAAgent.run tự chọn phép đo | Có replay/API riêng | Vòng RCA thích ứng có candidate goals và thực thi qua Runner, nhưng chat dùng assess_session. Vì vậy có engine mà chưa tận dụng toàn bộ ở đường chat. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/rca_agent.py#L139) |
| TaskRuntime thống nhất MEASURE/DIAGNOSE | Có component, chưa làm entrypoint Web | Có state trace và test; điểm khởi tạo thấy trong test. Server và SkillChat vẫn gọi GoalAgent/RCAAgent/ReadSession trực tiếp. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/task_runtime.py#L27) |
| LLM Goal Proposal có kiểu | Có component opt-in | GoalAgent nhận goal_proposer; chat hiện dùng choose_skills thay vì gọi cơ chế đề xuất port-goal này. Không đồng nghĩa thiếu LLM planning, nhưng hai giao diện chưa được thống nhất. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/goal_agent.py#L32) |
| ReAct / LangGraph | Luồng khác, chưa dùng cho chat Linux LLM | Có template upstream, policy và stage review hữu hạn; replay/Windows có đường chọn react. Chat Linux đi vào CHAT.chat trước nhánh đó. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/react_runtime.py#L71) |
| RAG tài liệu/runbook | Chỉ nối đường replay/CLI cũ | RunbookIndex có metadata product/firmware và retrieval local; Linux LLM return sớm nên chưa nhận runbook context ở luồng chính. Runbook không được coi là evidence đo mạng. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/web_gateway/server.py#L188) |
| Checkpoint evidence có chữ ký | Có component opt-in, chưa nối chat | GoalAgent nhận checkpoint, kiểm HMAC/TTL/ACL/context khi restore; ReadSession có binding hỗ trợ nhưng SkillChat không khởi tạo store hay lưu/khôi phục checkpoint. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/checkpoint.py#L22) |
| READ job journal / crash recovery | Có component opt-in, chưa nối chat | HMAC chain, atomic append và recovery có test; GoalAgent có hook, live SkillChat chưa tạo journal. Không phải History UI hay exactly-once WRITE. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/job_journal.py#L21) |
| Registry extension khai báo | Có loader và test, chưa có luồng nạp live chat | Manifest chỉ mô tả READ preapproved; không auto-bind backend, auto-probe hay chạy code. Không có chức năng thêm Skill bằng chat rồi tự thực thi. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/extension_loader.py#L101) |
| Edge–Cloud + HTTPS hypothesis | Có component/mock, mặc định tắt | Policy cần consent, ngân sách, backend và chỉ chia sẻ telemetry tổng hợp; chưa khởi tạo trong Web/chat. Kết quả cloud luôn là hypothesis, không thành verified Claim. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/delegation.py#L29) |
| WRITE transaction / durable outbox | Có component/mock, mặc định tắt | Có phê duyệt ký, nonce, preview/readback/rollback và outbox SQLite; không có router driver đi kèm, không nối từ LLM/HTTP. Mock pass không chứng minh thay đổi firmware thật. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/graph_v3/change_transaction.py#L127) |
| OpenWrt Ubus / Composite Adapter | Có adapter/transport, chưa dùng profile laptop | Có binding READ và CLI transport hạn chế timeout/output; tests mock I/O. Composition live hiện dùng LaptopSkillBackend; chưa nghiệm thu firmware/board cho catalog mở rộng. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/adapters/ubus_read.py#L35) |

## Có mô phỏng hoặc chỉ mới có một phần sản phẩm

| Tính năng | Kết nối hiện tại | Dùng được ở mức nào | Bằng chứng |
|---|---|---|---|
| Monitoring / Alerts | Baseline replay | monitor_window kiểm 3 mẫu có provenance/TTL và ngưỡng. Chưa có collector chạy định kỳ, alert delivery hay incident lifecycle nối vào Web. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/monitor.py#L15) |
| QoS và lịch chặn truy cập | Operations replay | ReplayOperations có SQLite, approval, idempotency và lịch hết hạn; chỉ sửa dữ liệu mô phỏng, chưa áp dụng lên router từ chat. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/operations.py#L38) |
| Firmware/OTA preflight | Kiểm tra artifact mô phỏng | Kiểm manifest/hash/platform/revision/storage/recovery có sẵn; chưa phải uploader/flash/rollback firmware thật. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/lifecycle.py#L9) |
| Client–AP–Router / nhiều thiết bị | Metadata và replay, live chỉ một laptop | Association của laptop có thể đọc; chưa có inventory mọi client hoặc router telemetry để chẩn đoán xuyên các thiết bị trong live chat. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/adapters/laptop_skills.py#L9) |
| History bền / Incident UI / Memory dài hạn | Chưa có luồng sản phẩm hoàn chỉnh | Có session ngắn hạn và component checkpoint/journal riêng. Chưa có history store/query, incident lifecycle hoặc UI tương ứng trong Web chat hiện tại. | [Code](https://github.com/Greediex/Gateway_LM/blob/9f1ab6ba/gateway_pilot/application/skill_launcher.py#L21) |

## Kiểm tra thực hiện trong lần audit này

1. **90 tests chọn theo phạm vi audit: tất cả đạt**, 10,305 giây. Gồm hybrid retrieval, checkpoint, job journal, TaskRuntime, delegation/HTTPS, WRITE/outbox, extension loader, Ubus, operations và grounded/graph chat. Đây chủ yếu là test double/replay; không có model embedding thật, cloud thật hay board thật được nghiệm thu từ các test này.
2. Tạo **một phiên laptop cô lập**, probe qua Core rồi đóng phiên: **8 READY, 118 UNAVAILABLE**; cả 8 Function trong deployment laptop báo AVAILABLE. Không dùng phiên chat đang mở của người dùng. Trước khi tạo phiên, endpoint catalog trả 8 UNVERIFIED là đúng thiết kế, vì chưa probe/authorize trong session.
3. Đọc lại đường Web: Linux + with_llm đi vào SkillChat trước nhánh runbook/replay; RCA trong chat gọi assess_session; ReadSession cấu hình max_repairs=0. Không bật các chức năng còn tắt trong lần audit này.
4. Full regression **790 tests / 785 pass / 5 Windows skips** là bằng chứng CI của runtime trước audit, không phải bộ test vừa chạy lại: [CI 2a30bf9](https://github.com/Greediex/Gateway_LM/actions/runs/44053090402).
5. Các kết quả Qwen/live trước audit vẫn giữ phạm vi gốc: [283 câu retrieval dev và một ví dụ DNS Qwen 4B](</home/nangtuan/Documents/ChatGPT/Just Test/Gateway_LM_v2_20261116/docs/reports/CHAT_GRAPH_RETRIEVAL_DEV_20261117.json:2>). Recall@6 56,24% → 57,13% chỉ là retrieval; ví dụ DNS mất 101,54s không chứng minh chất lượng tổng quát hoặc cải thiện latency. Audit này không chạy lại full Qwen EVAL1000.

## Ý nghĩa đối với mục tiêu Agent

Khoảng cách quan trọng không phải thiếu file AgentLoop. Vòng LLM chọn tiếp đã có. Khoảng cách nằm ở chỗ coverage còn dựa vào phrase/port, RCA chỉ được dùng ở chế độ assessment, repair runtime tắt ở session live, câu trả lời bị giới hạn grammar, và nguồn dữ liệu laptop không đáp ứng phần lớn catalog thiết kế. Chỉ bật embedding/graph hoặc đổi model không thể tự cung cấp dữ liệu router hay chứng minh nguyên nhân.

Các component checkpoint/journal và semantic retrieval có khả năng tái sử dụng thực tế, nhưng chưa thể gọi là “sẵn dùng trong chat”. Cloud, WRITE và firmware là phạm vi triển khai riêng, không nên bật mặc định chỉ vì có code. Tiến độ và mọi kế hoạch triển khai tiếp vẫn chỉ ghi tại [TODO.md](</home/nangtuan/Documents/ChatGPT/Just Test/Gateway_LM_v2_20261116/TODO.md:1>).
