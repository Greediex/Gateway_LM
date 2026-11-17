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
- [ ] **PERF-01 — Đo và giảm độ trễ thực tế.** Profile riêng thời gian tra catalog, inference, probe/Function, Verifier và RCA; tối ưu prompt/cache còn hợp lệ và lời gọi trùng. Kiểm giới hạn đồng thời, output, timeout và giải phóng phiên. **Nghiệm thu:** có số đo cold/warm, p50/p95, tool calls và tài nguyên laptop trước/sau; không bỏ gates để tăng tốc.
- [ ] **EVAL-01 — Đánh giá độc lập trước khi mở rộng.** Tạo bộ câu hỏi và replay có nhãn, tách dev/test trước khi tune; gồm đa ý định, ngoài khả năng, evidence cũ, sai scope, lỗi tool và prompt injection. **Nghiệm thu:** báo Skill/Function selection, độ đầy đủ câu trả lời, RCA/abstention, proposal sai, calls và latency; phân biệt rõ test double, Qwen thật, replay và live. Các ví dụ nghiệm thu hiện có chưa phải holdout benchmark.

**Đang xử lý P0:** đã sửa bao phủ nhiều ý định/phần chưa nhận diện, nhầm scope AP/router với laptop, thiếu SSID/kênh trong câu trả lời, phục hồi evidence một lần qua cùng Core/budget và vòng sửa proposal hữu hạn. Khởi tạo/inference nhận thời gian còn lại; có giới hạn response và đồng thời. Review độc lập đã kiểm lại các lỗi này; full regression 768 tests (763 pass, 5 Windows-only skips) và review độc lập đã đạt; đang đo Qwen trước/sau. CHAT-02/03 nghiệm thu bằng Core/provider/model doubles, chưa suy sang firmware thật. Bộ dev/test EVAL-01 được đóng băng trước thay đổi runtime tại `benchmarks/skill_chat_v1/`; nhãn do agent soạn, chưa được người ngoài thẩm định. Dev model giả đạt coverage 14/14 lượt, abstention 11/14; đây là kiểm tra tích hợp, không phải chất lượng Qwen. Chưa đánh dấu hoàn tất khi chưa có kết quả cuối.

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
