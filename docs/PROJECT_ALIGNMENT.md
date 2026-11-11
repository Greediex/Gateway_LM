# Phạm vi pilot so với Gateway LM v0.1

Nguồn thiết kế: HTML người dùng cung cấp `gateway-lm-v0.1-xem-truc-tiep-1-file.html`, phần 03 và Architecture Deep Dive ngày 06/11/2026; mô tả Skill Graph kèm theo. Đây là một pilot biệt lập trong `gateway_lm_pilot`, không đổi command mapper đang có trong `Edge_Agent`.

| Thành phần bản thiết kế | Pilot đã thực hiện | Phần chưa kiểm chứng |
|---|---|---|
| Tool / Skill / Workflow phân biệt | 16 Function Contract, 8 Skill, membership nhiều–nhiều; 4 workflow chính và 2 nhóm mở rộng | Chưa bao phủ đủ 22 Skill / 270 backlog items / 101 UC |
| Joint Skill–Function Retrieval | BM25 trên cả Skill và Function, skill affinity là soft prior | Chưa vector/reranker hoặc học từ dữ liệu |
| Tool–Schema Graph | Producer theo typed port, scope và schema output; mở rộng missing evidence goals từ workflow contract | Chưa thực hiện JSON Schema subsumption tổng quát hoặc nhiều producer cost-optimal |
| Function DAG Compiler | Dependency closure, cycle/node budget, reuse fresh fact, scope binding, per-invocation gate | Chưa local graph repair tổng quát, persistence/reboot hoặc concurrent scheduler |
| Policy Gate | Read-only, allowlist capability/function/arguments, target/scope, budget | Không có executor ghi; không chứng minh giao dịch/rollback thực |
| Evidence Validator | OK/UNKNOWN theo status, parse, TTL, scope; FINISH phải có fact hỗ trợ và citation thật | Thời gian trong fixture là mô phỏng; chưa đồng bộ clock/boot/config thật |
| Case State / replan | Cập nhật sau mỗi observation, lặp quyết định với feedback khi Core từ chối | Chưa job journal/transaction store phục hồi sau crash |
| Fastpath / Edge LLM / Cloud | Baseline luật và model local qua Ollama, cùng Core | Chưa NPU/QNN/HTP; không gọi Cloud hoặc router |
| Nghiệm thu | Ca lỗi/khỏe/thiếu dữ liệu/nhầm target/stale/parse/ambiguous/log injection | Chưa dữ liệu thật, unseen fault family, firmware captures, throughput forwarding |

## Thí nghiệm có thể kết luận gì?

- Model nhỏ có chọn được tool, dùng fact và tự dừng đúng trên các kịch bản được kiểm soát không?
- Retrieval thu hẹp tool có bỏ sót producer/phép đo cần cho kết luận không?
- Goal contracts và dependency compiler hỗ trợ orchestration bao nhiêu so với tool phẳng/retrieval?
- Model có kết luận sớm, nhầm evidence ID, nhầm target, bỏ qua UNKNOWN hay lặp bước không?
- Với quy trình định trước, baseline luật có đủ tốt để giữ Fastpath không?

Không thể dùng pilot này để tuyên bố root-cause accuracy trên mạng thật, NPU performance, hiệu quả học graph, hoặc tái lập kết quả của paper. Chấm `diagnosis` dạng nhãn có kiểm chứng, chưa chấm chất lượng văn bản giải thích tự do.

## Công bằng và giới hạn thiết kế so sánh

Mọi arm model có cùng prompt, model/quantization, workflow ID cho sẵn, checklist nghiệp vụ, JSON syntax mode, gate, validator, tool budget, decision budget và dữ liệu. Khác biệt là catalog được expose và khả năng compiler tự bổ sung prerequisite. `graph` thêm biểu diễn máy đọc của checklist (`workflow_evidence`) để truy xuất producer cho mục tiêu còn thiếu; đây là kiến thức kỹ thuật được khai báo, không phải model tự học. Vì vậy tên chính xác của arm là **model + goal contracts + retrieval + typed graph compiler**, không quy toàn bộ lợi ích cho một loại cạnh Skill Graph.

Arm thứ năm `graph_batch` cố ý thay đổi phân công: Core biên dịch và đọc gói evidence trước, sau đó model nhận prompt riêng cho analyst và chỉ chọn verdict. Đây là thí nghiệm về cách phân công Core/model; không được gọi là ablation chỉ thay retrieval. Cùng checklist, model, gold, gate và validator; chi phí probe và số model call được báo riêng. Graph batch không tự tạo chẩn đoán, vì vậy verdict vẫn có thể sai hoặc không đủ citation và bị gate từ chối.

24 họ template × 3 biến thể = 72 ca: biến thể 0 dùng dev; biến thể 1 (Việt) và 2 (Anh) dùng test. Chưa có holdout theo họ lỗi; hai biến thể test có tương quan. Prompt được chỉnh bằng dev và ghi lại các run thử; sau khi khóa protocol thì không chỉnh dựa trên kết quả test. Các run dev cũ có thể chưa hoàn tất do dừng để sửa giao thức; không trộn chúng vào bảng test.

Simulator là adapter replay có chủ ý, không thực thi code tùy ý. Model chỉ thấy observation đã đọc, target, checklist và Function Contract; world và gold được giữ ngoài prompt. FINISH validator là mã sản phẩm tách với scorer. Vì validator có luật hỗ trợ nhãn chẩn đoán, đây là **hybrid LLM + rules/graph**, không phải đo suy luận thuần của model.

Giới hạn giao diện model: pilot dùng JSON action qua prompt, chưa dùng native tool-calling của Ollama/Qwen. Catalog expose requires/produces/ready và mô tả Function, hướng dẫn arguments rỗng để Core bind, nhưng chưa expose JSON Schema argument đầy đủ. `unknown_argument` vì model nhầm typed fact với tên tham số cần được phân tích như lỗi contract/prompt tương tác với model, không chỉ quy về thiếu kiến thức mạng. Test này không xác lập trần năng lực của model <3B.
