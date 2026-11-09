# Dynamic Agent cho chẩn đoán Internet

`gateway_pilot.workflow` đã chọn nhánh Wi-Fi, DHCP, WAN và DNS dựa trên kết quả đo. Điểm thiếu là luồng Internet dừng khi chưa xác minh được WAN, kể cả khi adapter đo từ client vẫn khả dụng. `--dynamic` giữ các bước kiểm tra ban đầu và thêm vòng chọn mục tiêu sau phép đo WAN.

| Thành phần | Cơ chế trong pilot |
|---|---|
| Policy | Dùng evidence đã xác minh để chọn đo IP từ client, đo DNS từ router hoặc đối chiếu DNS từ client. Nếu WAN chưa xác minh được, vẫn có thể đo đường truyền từ đúng thiết bị. |
| Catalog và DAG | Compiler chỉ đưa ra mục tiêu có kế hoạch đọc hợp lệ trong giới hạn phiên. GoS vẫn xếp hạng các node READY. `--context-bytes` dùng adapter SkillDAG hiện có cho ngữ cảnh skill. |
| Runner và verifier | Kiểm tra dependency, đối tượng, schema, nguồn và độ mới. Nếu tool lỗi, runner thử sửa plan trong giới hạn trước khi policy xem xét mục tiêu khác. |
| Edge advisor | Model tùy chọn chỉ chọn giữa các probe đã được compiler chấp nhận. Policy quyết định khi chỉ có một lựa chọn. |

Ví dụ, cùng câu “Máy tính phòng khách vẫn có Wi-Fi nhưng không mở được trang web”, khi `wan.probe` timeout, agent chuyển sang `client.probe`. Nếu phép đo từ client thấy mất gói 80%, câu trả lời chỉ mô tả mất gói từ thiết bị và để trạng thái `PARTIAL` vì chưa định vị được nguyên nhân.

```powershell
python -m gateway_pilot.workflow --fixture GLM-21-1 --request "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?" --dynamic --trace
python run_dynamic_benchmark.py --output runs/dynamic-policy.json --model qwen3:1.7b
```

| Chế độ | Ca đạt | Ca đạt khi chèn lỗi | Tool calls | Model calls |
|---|---:|---:|---:|---:|
| Core | 7/9 | 3/5 | 70 | 0 |
| Dynamic | 9/9 | 5/5 | 70 | 0 |
| Dynamic + Qwen3 | 9/9 | 5/5 | 70 | 5 |

Qwen3 có 2.031.739.904 tham số theo Ollama. Cả 5 đề xuất được chấp nhận. Policy mới dùng ít hơn hai lần gọi tool khi đo từ client đã thấy mất gói cao, đồng thời dùng thêm hai lần gọi ở hai ca Core dừng sớm. Bộ test 92 graph/workflow + 34 legacy và 36 ca benchmark HTML đều đạt. Các ca benchmark là replay tổng hợp với lỗi timeout, sai kiểu, quá hạn và nhầm đích. Tiêu chí đạt gồm chẩn đoán, cổng evidence, thứ tự dependency và quyền đọc.

Vòng chọn mục tiêu học từ [LangGraph ReAct](https://github.com/langchain-ai/react-agent/blob/main/src/react_agent/graph.py), giới hạn sửa kế hoạch từ [GraSP](https://arxiv.org/abs/2604.17870), truy xuất từ [GoS](https://arxiv.org/abs/2604.05333) và [SkillDAG](https://arxiv.org/abs/2606.03056), kiểm thử chèn lỗi từ [ToolMaze](https://arxiv.org/abs/2606.05806), và chỉ hỏi model khi cần từ [nghiên cứu về planning horizon](https://arxiv.org/abs/2605.08477). Thử nghiệm hiện giới hạn ở chẩn đoán Internet cho client, với tập mục tiêu do policy định nghĩa. Chưa đánh giá trên router thật, sinh mục tiêu mở hay cập nhật Skill Graph tự động.
