# Gateway LM — kết quả thử model nhỏ với graph

Model `qwen3:1.7b`, GGUF Q4_K_M, actual parameter count 2,031,739,904 (<3B). Runtime CPU; tool adapters là synthetic replay.

## Kết quả đo được

| Interface / Arm | Tự hoàn tất đúng | Buộc dừng | Tool/ca | LLM p50 / p95 (s) |
|---|---:|---:|---:|---:|
| v1 JSON-text / rules | 48/48 (100.00%) | 0 | 2.75 | 0.00 / 0.00 |
| v1 JSON-text / flat | 10/48 (20.83%) | 38 | 2.02 | 2.92 / 7.08 |
| v1 JSON-text / retrieval | 5/48 (10.42%) | 43 | 2.21 | 2.43 / 3.45 |
| v1 JSON-text / graph | 9/48 (18.75%) | 39 | 2.58 | 2.49 / 4.32 |
| v1 JSON-text / graph_batch | 22/48 (45.83%) | 20 | 3.21 | 2.90 / 5.95 |
| v2 native (exploratory) / graph_batch | 27/48 (56.25%) | 21 | 3.21 | 3.36 / 6.05 |

## Đối chiếu interface trên ca chung

- graph_batch: v1 22/48, v2 27/48; chênh lệch +10.4 điểm phần trăm trên cùng ca. Không coi đây là kiểm chứng holdout mới.

## Có thể dùng đến mức nào trong dự án?

Ở cấu hình đã thử, graph riêng chưa cải thiện khả năng model tự điều phối: 9/48 so với 10/48 ở tool phẳng. Chế độ model tốt nhất là Core/graph chuẩn bị evidence trước rồi model chọn verdict qua native tools: 27/48. Đây chưa đủ tin cậy để giao toàn bộ vòng chẩn đoán cho model.
Với bốn workflow cố định hiện tại, giữ Fastpath/luật và Core nắm điều phối, dependency, scope, policy và validator. Model dùng thử như analyst/advisor có kiểm chứng. Lỗi chính gồm lặp bước, bỏ sót tiền điều kiện, kết luận ở mức triệu chứng và citation không đầy đủ.
Trong 28 ca đủ dữ liệu, native model từng đề xuất đúng nhãn với fact hỗ trợ ở 23/28 ca, nhưng chỉ 18/28 ca hoàn tất đúng toàn bộ contract. Đây là phân tích thành phần, chưa phải một chế độ tự sửa citation đã triển khai.

## Cách đọc kết quả

- v1 là test protocol đã khóa trước khi chạy 48 ca × 5 arm. v2 là thử nghiệm interface tiếp nối sau khi quan sát lỗi v1; không gộp số liệu hoặc tuyên bố là đánh giá mù mới.
- v2 đổi cả native template, tool/argument schema, terminal function và protocol wording. Cải thiện nếu có chưa tách được tác động riêng của native serialization hay schema.
- graph tự điều phối và graph_batch là phân công khác nhau. graph_batch để Core thu thập evidence trước, model chỉ chọn verdict; nó không chứng minh model tự lập kế hoạch nhiều bước.
- Cùng model, fixture, hash Core và scorer đã được kiểm tra. Workflow ID/checklist cho sẵn; chưa đo intent routing, văn bản giải thích, router thật hoặc NPU.
- Baseline rules được xây cùng các workflow/fixture đơn giản. Điểm cao không chứng minh khả năng khái quát cho sự cố mới.
- Mọi kết quả thất bại, citation sai, đề xuất bị chặn và Core buộc dừng vẫn giữ trong JSONL. Core buộc dừng không tính là model tự thành công.

## Hồ sơ đầy đủ

- Primary: [runs/test_qwen3_v1/REPORT_VI.md](runs/test_qwen3_v1/REPORT_VI.md)
- Primary error analysis: [runs/test_qwen3_v1/TAKEAWAYS_VI.md](runs/test_qwen3_v1/TAKEAWAYS_VI.md)
- Native follow-up: [runs/test_native_v2/REPORT_VI.md](runs/test_native_v2/REPORT_VI.md)
- Native error analysis: [runs/test_native_v2/TAKEAWAYS_VI.md](runs/test_native_v2/TAKEAWAYS_VI.md)
- Code papers: [docs/PAPER_SOURCES.md](docs/PAPER_SOURCES.md)
- Scope: [docs/PROJECT_ALIGNMENT.md](docs/PROJECT_ALIGNMENT.md)
- Primary-source interface notes: [docs/MODEL_INTERFACE_NOTES.md](docs/MODEL_INTERFACE_NOTES.md)
