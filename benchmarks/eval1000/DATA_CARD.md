# DATA CARD — EVAL-1000 v1 (2026-11-16)

## Mục đích
Đánh giá retrieval & LLM selection trên design catalog 120 Skill IDs; đánh giá đường chạy LLM Skill Chat trên Linux laptop qua backend tổng hợp; và kiểm tra các ranh giới tin cậy của runtime khi có lỗi.

## Thành phần, provenance
- **390 Catalog cases**: 120 intent seeds do người viết benchmark diễn đạt từ metadata kỹ thuật của repository; các kết hợp hai/ba intent và paraphrase tạo thành 390 scenarios. Gold là Skill ID, chỉ đánh giá matching ở mức thiết kế, không xác nhận runtime.
- **320 E2E cases, 337 turns**: dựa trên 52 seed cases đã tạo trong EVAL-01, có các ràng buộc selected Skill groups/expected ports/partial statuses. Câu hỏi được biến thể, đôi khi có thêm yêu cầu không suy đoán.
- **290 Fault cases**: các trigger model errors, TTL, adaptive/claim, unsupported, safety. Trigger xác định; câu hỏi là nhiều cách diễn đạt cùng một tình huống.
- **Tổng**: 1.000 records và 1.017 turns. Split dev: 683 cases, test: 317; giữ cùng `scenario_family` trong một split.

## Label quality
Gold được biên soạn bằng tay ở mức **seed**, gắn qua generator xác định. Không xác nhận 1.000 câu đã qua chuyên gia độc lập. Không thể coi 1.000 như kích thước mẫu độc lập. Cần human-review khi sử dụng để quyết định triển khai thực tế hoặc công bố nghiên cứu. Đặc biệt review labels có Skill thay thế và trường hợp có nhiều cách thu thập dữ liệu hợp lệ.

## Scope & exclusions
- Linux laptop read-only; không giả lập OpenWrt/NPU/hardware acceptance; không tự chạy lệnh hay ghi mạng/router.
- Catalog-mode chỉ phân loại ID, không kết luận khả năng thực thi.
- Fixture E2E dùng backend có trong unit tests repo; không mô phỏng Internet thật.
- Fault mode dùng model double, không có thống kê chất lượng Qwen.
- Chưa có bộ đánh giá mù từ người quản trị mạng, chưa có ground truth RCA cho đa dạng lỗi vật lý.

## Usage risks
Dễ bị **benchmark contamination** nếu model được chỉnh prompt trực tiếp theo test split hoặc dùng các golden case làm few-shot examples. Khi đã mở holdout test, phải ghi và giữ lại kết quả trước khi tuning. Khi chạy `--store-raw` trên máy thật có thể chứa IP, DNS, SSID, MAC; không commit raw output.

## Tái lập
`cases.jsonl` đóng băng qua SHA256 ở `manifest.json`; generator chạy chuẩn Python 3.12+ không phụ thuộc random ngoài; `tests/test_eval1000.py` kiểm toàn vẹn và rubric. Các kết quả Qwen còn phụ thuộc model digest, inference settings, phiên bản Git và môi trường.
