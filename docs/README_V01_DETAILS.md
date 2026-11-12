> **Bản lưu đầy đủ README trước đợt dọn dẹp.** Các lệnh root script trong nội dung cũ đã được chuyển vào `scripts/`; xem [bảng lệnh mới](../scripts/README.md). Các số liệu v1–v4 trong tài liệu này là kết quả tại thời điểm chạy, không phải trạng thái CI mới nhất. Thư mục `runs/` được gitignore nên các link tới báo cáo trong `runs/` chỉ có tác dụng nếu dữ liệu đã có trên máy.

# Gateway LM v0.1 — small-model / Skill Graph pilot

Pilot nghiên cứu Gateway LM v0.1 với Skill Graph, chẩn đoán theo bằng chứng và Ollama local tùy chọn. Có dữ liệu replay và chế độ đo kết nối từ máy Windows.

## Cài đặt và chạy web

```powershell
python -m venv .venv-graph
.\.venv-graph\Scripts\python.exe -m pip install -r requirements-react.txt
.\.venv-graph\Scripts\python.exe setup_upstream.py
.\web_gateway\start_windows.ps1
```

`setup_upstream.py` tải GoS và SkillDAG theo commit đã ghim. Hướng dẫn chạy và cấu hình nguồn đo nằm trong [README Web](../README_WEB.md).

## MVP v0.1 — graph v4 (hiện trạng)

Điểm vào hội thoại: `gateway_pilot.assistant` (Turn Router → Resolver → Compiler → Runner có repair → evidence/claim →
Answer Composer). Mọi lượt trả về `Turn` có `grounding`, `evidence_ids`, `case_status` và Contract 0/A/C. Đối chiếu
Xem [kết quả G1–G23](GRAPH_V4_RESULT_VI.md) và [trang kiến trúc](architecture/gateway-lm-v0.1-kien-truc.html).

```powershell
.\.venv-graph\Scripts\python.exe -m gateway_pilot.assistant --fixture GLM-21-1 --request "laptop-an có wifi mà không vào được mạng" --trace
.\.venv-graph\Scripts\python.exe run_function_selection.py --run function_selection_<tên-mới>     # benchmark A–E (T9)
.\.venv-graph\Scripts\python.exe run_conversation_benchmark.py --run conversation_<tên-mới>      # hội thoại (C5)
.\.venv-graph\Scripts\python.exe docs/contracts/golden/build_golden.py --check                    # golden cho bản C++
```

Hai benchmark kiểm SHA-256 của bộ ca với manifest trước khi chạy và không ghi đè thư mục `runs/` đã có. Golden fixture
(`docs/contracts/golden/`) ghi đầu vào → Contract 0 → Contract A → sự kiện → Contract B → Contract C → kết luận cho 6 ca.
Adapter OpenWrt mới là khung (`gateway_pilot/adapters`): chưa có Function nào probe trên firmware.

## Ma trận HTML và replay nghiệp vụ

`audit_html.py --html <gateway-lm.html> --output <thư-mục-mới>` trích danh mục UC, workflow, skill, hạng mục F, pha và test tích hợp. Thêm `--graphify` trong môi trường có Graphify để nối ID của HTML với symbol mã nguồn trong pilot và xuất bản đồ tương tác.

```powershell
.\.venv-graph\Scripts\python.exe run_operations_replay.py --output runs/my_operations_replay
.\.venv-graph\Scripts\python.exe -m unittest discover -s tests_graph_v3 -p test_operations.py -v
```

Replay nghiệp vụ minh họa QoS có duyệt và hậu kiểm (WF-031), lịch truy cập một lần qua khởi động lại (WF-063), cảnh báo ngưỡng theo cửa sổ (WF-054) và preflight artifact (WF-047/WF-081). QoS và lịch chỉ thay đổi SQLite local. Preflight demo kiểm chữ ký bằng verifier và khóa fixture.

```powershell
.\.venv-graph\Scripts\python.exe run_html_benchmark.py --output runs/my_html_benchmark --repeat 3
```

Benchmark dùng 36 ca trong `benchmarks/html_workflows_v1.json` cho WF-018, WF-031, WF-047, WF-054, WF-063 và WF-081. Điểm kết quả, bằng chứng và tác động lên trạng thái được ghi riêng trong `episodes.jsonl`. `REPORT.md` tổng hợp số ca pass và độ trễ replay trên host.

## Retrieval và RAG local

```powershell
.\.venv-graph\Scripts\python.exe -m gateway_pilot.workflow --fixture GLM-21-1 --request "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?" --guide --context-bytes 1800 --trace
.\.venv-graph\Scripts\python.exe -m gateway_pilot.rag --request "DNS SERVFAIL" --product gateway-lm-pilot --firmware synthetic-replay-v1
.\.venv-graph\Scripts\python.exe run_rag_benchmark.py --output runs/my_rag_benchmark
```

`--guide` thêm WF-069, với ID tài liệu và SHA-256 catalog tách riêng khỏi evidence đo. Corpus mặc định viết cho profile replay. Retriever dùng BM25 lấy tài liệu chính rồi bổ sung tiền đề đã khai báo. Có thể dùng `--method gos` ở CLI `gateway_pilot.rag` để thử PPR trên nhóm tiền đề. `--context-bytes` thêm WF-067, hiển thị các bundle function được compiler kiểm quyền và bổ sung tiền đề. Mã gốc SkillDAG kiểm closure và xung đột trước khi đóng gói. Budget được đo bằng byte UTF-8 của JSON, không phải token tokenizer của model.

## Chẩn đoán từ câu hỏi người dùng

`gateway_pilot.workflow` dùng FastPath theo luật để chọn workflow từ câu hỏi, đối chiếu tên thiết bị với inventory của adapter và lập kế hoạch Graph v3 theo từng nhóm bằng chứng. Core kết luận từ phép đo đã kiểm chứng, hỏi lại khi thiếu định danh, hoặc trả về `INCOMPLETE` khi chưa đủ dữ liệu.

Policy động là mặc định cho Internet từ client, WAN, DNS, DHCP và sức khỏe hệ thống. Dùng `--core` để chạy luồng cố định đối chứng. Xem [cơ chế và benchmark](DYNAMIC_AGENT_VI.md).

```powershell
# Chạy từ thư mục Gateway_LM
.\.venv-graph\Scripts\python.exe -m gateway_pilot.workflow --fixture GLM-21-1 --request "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?"
```

`--fixture` chọn môi trường replay và inventory. Thêm `--trace` để xem các nhánh, tool và evidence ID. Trường `workflow_id` dùng ID của HTML cho các ca đã ánh xạ, gồm `WF-018` cho chẩn đoán Internet từ client. Trường `workflow` giữ khóa pilot để đối chiếu bộ replay cũ. `case_status` phân biệt `RESOLVED`, `PARTIAL`, `INCONCLUSIVE`, `BLOCKED` và ca cần hỏi lại `NEEDS_INPUT`.

`--model qwen3:1.7b` bật cố vấn SK10 cục bộ. Model chỉ xếp thứ tự phép đo đã qua kiểm quyền và biên dịch DAG. Core giữ thứ tự mặc định khi model lỗi hoặc đề xuất ngoài danh sách. Capability `client.dns` mở phép đo DNS từ client sau khi đã kiểm đường IP từ client và DNS từ router. Chẩn đoán DNS phía client cần bằng chứng cùng tên miền. Các phép đo vẫn dùng replay.

```powershell
.\.venv-graph\Scripts\python.exe -m gateway_pilot.workflow_eval --output runs/my_html_workflow_run --model qwen3:1.7b
```

Bộ chạy ghi kết quả Core trên 72 ca replay cũ. Khi có `--model`, nó chấm thứ tự phép đo của model trên sáu ca dựng riêng và ghi riêng kết luận của Core.

## Graph v3 — implementation hiện tại

[Báo cáo v3 và lệnh chạy](../GRAPH_V3_RESULT_VI.md): đã tích hợp kernel PPR GoS gốc, tách G_S/G_SF/H_F/G_run, typed invocation DAG, schema/guard/evidence binding, chọn producer theo chi phí trong ngân sách, READY scheduler và bounded repair. 50 test v3 + 34 test legacy pass; 48 ca cấu trúc và 48 ca model hoàn tất. Model vẫn đạt 27/48, không coi graph đúng cấu trúc là bằng chứng reasoning tăng.

```powershell
# Chạy từ thư mục Gateway_LM
.\.venv-graph\Scripts\python.exe -m unittest discover -s tests_graph_v3 -v
.\.venv-graph\Scripts\python.exe -m gateway_pilot.graph_v3.evaluate --output runs/my_new_graph_run
```

Dependency của v3 dùng venv riêng và [requirements-graph-v3.lock](../requirements-graph-v3.lock). Xem [protocol/phạm vi](GRAPH_V3_PROTOCOL.md). Chưa tái lập toàn pipeline GoS embedding/evolution hoặc full sản phẩm HTML.

**V1/v2 giữ làm baseline lịch sử:** BM25 + evidence-goal expansion + DFS; Skill `depends_on`/`relations` chưa được runtime cũ duyệt. Các audit dưới đây mô tả baseline đó, trước khi sửa v3: [audit paper](PAPER_FIDELITY_AUDIT.md), [audit độ phủ HTML](HTML_COVERAGE_AUDIT.md).

## Kết quả v1/v2 đã chạy

[Đọc báo cáo tổng hợp và kết luận](../EXPERIMENT_OVERVIEW_VI.md): 240 episode primary (48 ca × 5 arm), thêm 48 episode native exploratory trên cùng ca. Qwen3 `qwen3:1.7b`, actual artifact count 2.032B, Q4_K_M, CPU. Graph tự điều phối đạt 9/48; Core chuẩn bị evidence rồi native model kết luận đạt 27/48; baseline luật đạt 48/48 trên fixture đơn giản này. Chưa chứng minh khả năng trên router thật hoặc trần năng lực mọi model <3B.

34 kiểm thử Core/adapter pass. Commit và giấy phép của các repo tham chiếu được ghi trong [PAPER_SOURCES.md](PAPER_SOURCES.md).

## Chạy lại v1/v2 (baseline)

```powershell
# Chạy từ thư mục Gateway_LM
python -m unittest discover -s tests -v
# Chọn model đã cài; runner xác minh actual parameter_count < 3B.
python -u -m gateway_pilot.run --model qwen3:1.7b --split test --output runs/my_fresh_run
```

Mỗi lần chạy phải dùng đường dẫn output mới. Không cần cài pip package. Ollama phải chạy ở `http://127.0.0.1:11434`; runner từ chối endpoint không phải localhost. Model API dùng `think=false`, `temperature=0`, `seed=42`, context 8192 và JSON syntax mode; budget mặc định 10 quyết định và 12 replay tool calls/ca.

```powershell
# Smoke/dev, không dùng test để chỉnh prompt:
python -u -m gateway_pilot.run --model qwen3:1.7b --split dev --case-ids GLM-01-0 GLM-06-0 GLM-10-0 GLM-15-0 --output runs/my_dev_run
# Thử riêng arm hoặc đổi mức thu hẹp lexical retrieval:
python -u -m gateway_pilot.run --model qwen3:1.7b --arms graph --candidate-k 4 --split test --output runs/my_graph_run
```

`prepare_data.py` tái sinh registry/fixture xác định. **Không chạy lại để đổi dữ liệu sau khi xem test rồi gộp kết quả vào run cũ.** `data/frozen_manifest.json` kiểm SHA-256 trước mỗi run; metadata giữ cả hash mã nguồn và model digest.

## Năm arm

| Arm | Cơ chế |
|---|---|
| rules | Workflow và luật chẩn đoán xác định, không gọi model |
| flat | Model thấy mọi read Function, tự chọn từng bước |
| retrieval | Cùng model, joint Skill/Function BM25 top-4, không tự bổ sung prerequisite |
| graph | Cùng seeds, thêm producer cho missing workflow evidence goals, typed dependency closure và automatic prerequisite execution |
| graph_batch | Core thu thập gói evidence bằng graph trước, model chỉ chọn kết luận; không đo model tự chọn bước |

Mọi arm dùng chung gate/validator. Graph là một gói goal contracts + retrieval + compiler, chưa phải ablation tách từng loại cạnh. Xem [PROJECT_ALIGNMENT.md](PROJECT_ALIGNMENT.md).

## Dữ liệu và đầu ra

- `data/registry.json`: 8 Skill / 16 Function Contract, typed ports và workflow evidence contracts.
- `data/cases.json`: 72 kịch bản, 24 dev / 48 test; gồm WAN, DNS, DHCP, sức khỏe hệ thống, client path và write denied.
- `runs/<name>/episodes.jsonl`: raw model JSON, latency/token counts, graph plan, từng observation, đề xuất bị chặn, kết quả và nhãn gold.
- `runs/<name>/metadata.json`: cấu hình, phiên bản Ollama, model digest/count/quantization, hash dữ liệu/mã và trạng thái runtime.
- `runs/<name>/REPORT_VI.md`, `summary.json`: kết quả ghép cặp, chỉ số đúng/tự dừng, forced stop, số tool và độ trễ.
- [PAPER_SOURCES.md](PAPER_SOURCES.md): repo tác giả được clone, commit/license và trạng thái các paper còn lại.
- [MODEL_INTERFACE_NOTES.md](MODEL_INTERFACE_NOTES.md): đối chiếu interface hiện tại với tài liệu Qwen/Ollama chính thức.

Adapter native tiếp nối (chạy riêng sau v1, không gộp số liệu):

```powershell
python -u -m gateway_pilot.native_run --model qwen3:1.7b --arms graph graph_batch --split dev --case-ids GLM-01-0 GLM-06-0 GLM-10-0 GLM-15-0 --output runs/my_native_dev
```

Xem [NATIVE_PROTOCOL.md](NATIVE_PROTOCOL.md); đây là kiểm tra interface exploratory sau khi quan sát v1, chưa phải một holdout mù mới.

Metric chính `autonomous_success` yêu cầu đúng cả action và nhãn kết luận, tự kết thúc trong budget, không lỗi runtime. `outcome_match` có thể bao gồm Core buộc INCOMPLETE nên phải xem riêng. Không tính Core chặn lỗi thành năng lực của model. `write_effects=0` vì không có write executor.

Repo paper nằm trong `third_party`, được clone để đọc/đối chiếu; không tự cài dependency, tải dataset hoặc chạy benchmark upstream. Arm pilot là triển khai riêng, chưa phải reproduction paper.
