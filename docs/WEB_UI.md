# Gateway LM Web

Giao diện chat gọi `gateway_pilot.workflow.diagnose()` của pilot hiện tại. Backend trả kết luận, các mục tiêu policy đã cân nhắc, tool calls, evidence và từng phiên bản DAG. Mọi kết quả đo dùng dữ liệu replay trên máy.

Chạy từ thư mục gốc repository trên Windows:

```powershell
.\web_gateway\start_windows.ps1
```

Script ưu tiên môi trường `.venv-graph` của pilot. Trên Linux, dùng `bash web_gateway/start_linux.sh` với môi trường đã cài các phụ thuộc trong `requirements-graph-v3.lock`. Cả hai nhận `--port` nếu cổng 8765 đang bận. Mở [Gateway LM Web](http://127.0.0.1:8765). Dừng bằng `Ctrl+C` tại terminal đang chạy.

Trên Windows, chạy `.\web_gateway\start_windows.ps1 --source live` để mở web với **Đo thật từ Windows** làm nguồn mặc định. Hỏi **“Mạng chất lượng thế nào?”** để đo độ trễ và mất gói qua bốn gói ICMP tới mỗi đích, gồm gateway hiện tại và `1.1.1.1`, rồi thử DNS với `example.com`. Kết quả là mẫu ngắn từ máy đang chạy web. Để đo tốc độ tải theo Mbps hoặc đọc bảng thiết bị đang kết nối, cần thêm nguồn dữ liệu tương ứng. Có thể chuyển về **Replay mô phỏng** trong mục **Nguồn dữ liệu**.

Chọn tình huống **WAN timeout · đo từ client** và hỏi “Laptop An có Wi-Fi nhưng không vào Internet, kiểm tra giúp tôi.”

| Chế độ | Kết quả | Lượt gọi |
|---|---|---:|
| Dynamic Agent | Chuyển sang `client.probe`, ghi nhận mất gói 80% và trả `PARTIAL` | 7 |
| Core đối chứng | Dừng khi WAN probe timeout và báo chưa đủ bằng chứng | 6 |

Đổi **Chế độ chẩn đoán** rồi gửi lại cùng câu hỏi để đối chứng. Tab **Quy trình** hiển thị năm bước từ hiểu yêu cầu tới đánh giá kết quả. Tab **Bằng chứng** hiển thị quan sát và trạng thái xác minh. Tab **DAG** cho phép chọn từng kế hoạch và xem các cạnh phụ thuộc.

Chế độ **LangGraph ReAct** dùng `StateGraph`, `ToolNode` và mã định tuyến của mẫu chính thức. Node quyết định dùng policy Gateway hiện có và chỉ đưa một kế hoạch đã chọn cho tool. SkillDAG kiểm nhóm skill trước khi GraphRunner thực thi từng plan, kể cả plan sửa lỗi. GoS xếp hạng các bước đủ điều kiện chạy. [Mẫu ReAct tại commit đã ghim](https://github.com/langchain-ai/react-agent/tree/d3b771365dbe01e92bdd28286ee41610cd69302f)

Để bật ReAct trong môi trường mới, chạy `python -m pip install -r requirements-react.txt` với Python của pilot. Web tự chọn ReAct khi LangGraph và SkillDAG sẵn sàng. Có thể chạy từ CLI bằng `python -m gateway_pilot.workflow --react --fixture GLM-21-1 --request "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?" --trace`.

- **Graph of Skills** được chọn mặc định khi kernel đã ghim sẵn sàng. Nếu thiếu, web chọn BM25. **Skill context** dùng SkillDAG và chỉ bật được khi adapter đã sẵn sàng.
- **Runbook RAG** truy xuất tài liệu hướng dẫn. Kết luận chẩn đoán dựa trên evidence của lượt chạy.
- **LLM suy luận** bật mặc định trên giao diện ReAct với model Ollama local `qwen3:1.7b`. LLM hỗ trợ nhận diện yêu cầu khi luật chưa xác định được luồng. Khi có nhiều phép đo độc lập hoặc phép đo vừa lỗi, LLM có thể đề xuất bước tiếp theo và ghi giả thuyết kèm mã bằng chứng. Gateway kiểm đề xuất và tự đánh giá kết luận từ bằng chứng đo được.

Web giữ một phiên (`session_id`, trong bộ nhớ, hết hạn sau 15 phút): khi bị hỏi lại thiết bị, chỉ cần trả lời tên thiết bị; server chạy tiếp đúng Case đang chờ và dùng lại fact gateway còn hạn, không ghép chuỗi câu hỏi. Đổi tình huống thì bắt đầu Case mới. Replay đi qua `ReplayAdapter`; Function có probe hỏng không vào kế hoạch. Tab **Contracts** hiển thị Contract 0/A/B/C, lịch sử revision kèm toán tử repair và route (fastpath/resolver). Server chỉ nghe trên loopback và phục vụ replay chỉ đọc. Hai tình huống so sánh của web tạo từ fixture gốc trong bộ nhớ, giữ nguyên dữ liệu benchmark đã khóa.

`GET /api/config` trả danh sách fixture và trạng thái phụ thuộc. `POST /api/chat` nhận JSON, ví dụ:

```json
{"message":"Laptop An có Wi-Fi nhưng không vào Internet.","fixture_id":"WEB-WAN-TIMEOUT-1","policy":"dynamic","method":"gos","with_guide":true,"with_skill_context":true,"with_llm":false}
```

Chạy `python -m unittest discover -s tests/web -v` để kiểm tra adapter, đối chứng Dynamic/Core, phối hợp ReAct/GoS/SkillDAG và cổng chặn yêu cầu ghi.

## GoalInspector API (opt-in, replay only)

Server hỗ trợ `POST /api/goals` để đo **các output port đã khai báo** thông qua GoalAgent, độc lập với workflow ID cố định. Endpoint chỉ lấy dữ liệu từ fixture đã kiểm tra trong `data/cases.json`, không chấp nhận backend/permissions/world do client cung cấp. `source_mode=live` bị từ chối tại endpoint này; chế độ live hiện có vẫn dùng `/api/chat`.

Ví dụ PowerShell:

```powershell
$body = @{ message = "WAN and RAM status"; fixture_id = "GLM-04-0"; goals = @("wan.status", "system.resources"); method = "bm25"; source_mode = "replay" } | ConvertTo-Json
Invoke-RestMethod -Uri "http://127.0.0.1:8765/api/goals" -Method Post -ContentType "application/json" -Body $body
```

Trả về `goals`, `goal_facts`, `missing_goals`, `plans`, `ready_trace`, `contract_b`, `contract_c`. `status=RESOLVED` là **đã đo và xác minh mục tiêu**, không phải sửa xong sự cố; `diagnosis=NOT_EVALUATED` báo chưa có RCA.

Nếu muốn suy luận goal từ câu hỏi: gửi `registry="v01"` và bỏ trường `goals`. Chỉ khi Turn Router xác nhận workflow được hỗ trợ mới thực thi; yêu cầu không rõ trả `NEEDS_INPUT`/bị chặn.
