# Dynamic Agent cho các luồng chẩn đoán

`gateway_pilot.workflow` mặc định dùng `DiagnosticPolicy` cho cả năm luồng chẩn đoán đọc. Sau khi xác định intent và thiết bị, policy chọn mục tiêu dựa trên evidence đã xác minh, compiler tạo DAG cho một nhóm mục tiêu, runner chạy các bước READY và trả evidence để policy xét lại. Dùng `--core` để đối chứng với luồng cũ.

| Thành phần | Cơ chế trong pilot |
|---|---|
| Policy | Internet có thể chuyển sang đo từ client khi WAN chưa xác minh. WAN gom route và probe vào một DAG sau khi xác minh link. DNS có thể chuyển sang đo IP của router để trả kết quả một phần. DHCP đổi từ kiểm pool sang kiểm dịch vụ khi cần. Kiểm tra hệ thống dùng evidence CPU/RAM/dung lượng và trả thiếu bằng chứng khi phép đo lỗi. |
| Catalog và DAG | Compiler chỉ đưa ra mục tiêu có kế hoạch đọc hợp lệ trong giới hạn phiên. GoS vẫn xếp hạng các node READY. `--context-bytes` dùng adapter SkillDAG hiện có cho ngữ cảnh skill. |
| Runner và verifier | Kiểm tra dependency, đối tượng, schema, nguồn và độ mới. Nếu tool lỗi, runner thử sửa plan trong giới hạn trước khi policy xem xét mục tiêu khác. |
| Edge advisor | Model tùy chọn chỉ tham gia khi cả hai probe IP từ client và DNS từ router đều có plan hợp lệ. |

Ví dụ, cùng câu “Máy tính phòng khách vẫn có Wi-Fi nhưng không mở được trang web”, khi `wan.probe` timeout, agent chuyển sang `client.probe`. Nếu phép đo từ client thấy mất gói 80%, câu trả lời chỉ mô tả mất gói từ thiết bị và để trạng thái `PARTIAL` vì chưa định vị được nguyên nhân.

```powershell
python -m gateway_pilot.workflow --fixture GLM-21-1 --request "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?" --trace
python run_dynamic_benchmark.py --output runs/dynamic-policy.json --model qwen3:1.7b
```

| Chế độ | Ca đạt | Ca đạt khi chèn lỗi | DAG | Tool calls | Model calls |
|---|---:|---:|---:|---:|---:|
| Core | 15/18 | 6/9 | 75 | 94 | 0 |
| Dynamic | 18/18 | 9/9 | 68 | 97 | 0 |
| Dynamic + Qwen3 | 18/18 | 9/9 | 68 | 97 | 5 |

Qwen3 có 2.031.739.904 tham số theo Ollama. Cả 5 đề xuất được chấp nhận. Bộ test 96 graph/workflow + 34 legacy và 36 ca benchmark HTML đều đạt. Benchmark dùng replay tổng hợp với lỗi timeout, sai kiểu, quá hạn và nhầm đích. Ca lỗi được tính đạt nếu kết quả khớp với kỳ vọng, kể cả khi kỳ vọng là dừng vì thiếu evidence. Tiêu chí gồm chẩn đoán, bằng chứng, thứ tự dependency và quyền đọc.

Vòng chọn mục tiêu học từ [LangGraph ReAct](https://github.com/langchain-ai/react-agent/blob/main/src/react_agent/graph.py), giới hạn sửa kế hoạch từ [GraSP](https://arxiv.org/abs/2604.17870), truy xuất từ [GoS](https://arxiv.org/abs/2604.05333) và [SkillDAG](https://arxiv.org/abs/2606.03056), kiểm thử chèn lỗi từ [ToolMaze](https://arxiv.org/abs/2606.05806), và chỉ hỏi model khi cần từ [nghiên cứu về planning horizon](https://arxiv.org/abs/2605.08477). Phạm vi thử nghiệm là năm luồng đọc với tập mục tiêu do policy định nghĩa. Các luồng thay đổi cấu hình và lịch dùng cơ chế quyền và phê duyệt riêng. Việc kiểm chứng trên router thật, mở rộng đủ 22 nhóm skill và cập nhật Skill Graph tự động nằm ngoài phạm vi hiện tại.
