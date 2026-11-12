# Đối chiếu implementation với HTML Gateway LM v0.1

Ghi chú phiên bản: đây là audit baseline `core.py`/`run.py` v1/v2 trước khi sửa. Graph v3 nằm riêng trong `gateway_pilot/graph_v3`, xem `reports/GRAPH_V3_RESULT_VI.md`. Các kết luận thiếu thành phần dưới đây được giữ như hồ sơ của baseline; v3 chưa đồng nghĩa hoàn thiện toàn bộ HTML.

Đối chiếu ngày 07/11/2026 với tài liệu kiến trúc Gateway LM v0.1, phần 03, 06 và Architecture Deep Dive; đọc trực tiếp `gateway_pilot/core.py`, `run.py`, `native_run.py`, `prepare_data.py` và registry hiện tại.

**Kết luận: chưa thực hiện đầy đủ HTML; chưa tái lập thuật toán paper; chưa có bằng chứng tối ưu graph.** Các kết quả đã chạy là của một baseline mô phỏng do pilot tự triển khai. Tài liệu này bổ sung ranh giới diễn giải, không thay đổi số liệu hoặc các run đã khóa.

## Bốn graph trong HTML

| Thiết kế HTML | Thực trạng code | Đánh giá |
|---|---|---|
| G_S: Skill Relation Graph có cạnh kiểu hóa | `skills[].depends_on` và `relations` tồn tại trong metadata. Runtime không duyệt các cạnh này; `retrieve()` chỉ đưa metadata vào text để BM25 và dùng danh sách membership cho affinity | Chưa có Skill Graph runtime đúng thiết kế |
| G_SF: Skill–Function nhiều–nhiều | `functions[].skills` có membership; điểm Function cộng heuristic `0.20 * skill_score` | Có ánh xạ cơ bản, chưa có cơ chế truy xuất graph hai phía đầy đủ |
| H_F: Tool–Schema Hypergraph | `producers[port]` và `requires`/`produces` nối bằng tên port giống hệt. `port_fields` kiểm một số trường primitive ở output | Có dependency theo port; thiếu schema subsumption, effect predicates, scope/provenance compatibility trong compiler, nhiều producer theo chất lượng/chi phí |
| G_run: DAG các invocation đã bind | `closure()` trả danh sách Function ID theo thứ tự DFS; `compiled_plan` lưu list. Bind/check diễn ra khi execute | Chưa có node invocation và cạnh DATA/STATE/ORDER tường minh như HTML |

Nguồn code: `core.py:32–127`; `run.py:123–229`; `prepare_data.py:35–69`.

## Các khoảng trống ảnh hưởng trực tiếp kết quả

1. **Reretrieval chưa dùng đầy đủ trạng thái mới.** `core.py:108` luôn gọi `retrieve(case['request'], k)`. State ảnh hưởng missing goal ports và closure, nhưng câu truy xuất BM25 không được cập nhật bằng outstanding goals, facts hoặc hypothesis mới.
2. **Lọc sau top-k.** Cùng dòng 108 lấy top-k trước rồi loại Function không thuộc `allowed`; các hit write/unsupported có thể chiếm slot mà không được bù lại. Đây là yếu tố làm thiếu candidate, không thể quy hết cho model.
3. **Chọn producer theo tên.** `core.py:88` và `run.py:138` dùng `sorted(producers)[0]`; chưa tối ưu cost/latency/risk hoặc đánh giá adapter thay thế.
4. **Chưa loại hết bước đã hoàn thành.** Closure tái sử dụng fact cho prerequisite, nhưng vẫn thêm Function được yêu cầu dù output đang có fact hợp lệ. Seeds cũng có thể expose lại Function đã đọc; chống lặp chủ yếu bằng giới hạn hai lần/tool.
5. **Thiếu local repair/state machine đầy đủ.** Chưa có plan revision, typed node states, REBIND/SUBSTITUTE/REWIRE/BYPASS hoặc invalidation theo hậu duệ. Vòng lặp gọi lại model với lỗi gần nhất chưa tương đương bộ repair trong HTML.
6. **Verifier chưa là contract tổng quát.** Kiểm output primitive và `support()` gắn cứng nhãn chẩn đoán với điều kiện trong code. Chưa có verifier registry theo từng invocation và claim–evidence contract đầy đủ.
7. **Model interface còn hạn chế.** V1 là JSON text; native follow-up đã có tools/tool_calls nhưng vẫn dựng lại hai message từ state text, chưa có đầy đủ assistant/tool history. Native adapter yêu cầu đúng một call; nhiều call bị từ chối.
8. **Bộ test chưa độc lập theo họ lỗi.** 24 template dùng chung giữa dev/test; workflow/checklist cho sẵn, tool trả replay, chưa có distractor library tương đương paper hoặc firmware capture. Kết quả luật cao phù hợp với bộ fixture đã biết, không chứng minh khái quát.

## Phạm vi nghiệp vụ và runtime

| Hạng mục | Trạng thái thực tế |
|---|---|
| 22 Skill / 101 UC-WF / 270 hạng mục | Pilot mới có 8 Skill records, 16 Function records; 4 workflow chẩn đoán chính và 2 nhóm mô phỏng mở rộng. Không có coverage đầy đủ 101/270 |
| Intent/target intake | Workflow và target được fixture cấp sẵn; chưa đánh giá intent routing hoặc nhận diện target từ dữ liệu firmware |
| Policy/schema gate | Có allowlist/capability/read-only/argument/target/budget checks cơ bản; chưa ACL actor, consent, transaction/version/lock đầy đủ |
| Evidence/Case State | Có record, status, scope, freshness giả lập, cập nhật trong RAM và FINISH checks; thiếu state store/journal phục hồi, boot/config invalidation và phân tách hypothesis có kiểu |
| OpenWrt adapters | Tất cả là `synthetic_replay/v1`; chưa ubus/UCI/netifd/iwinfo/netlink/procfs thực và capability probe trên board |
| Graph runner | Tuần tự trên list, budget cơ bản; thiếu READY scheduling, per-node deadline/retry/recovery/concurrency đầy đủ |
| Transaction / Scheduler / Monitor | Chưa triển khai runtime tương ứng; fixture write-denied chỉ kiểm việc từ chối |
| Lifecycle / Worker / Cloud | Chưa triển khai; đây là các nhánh/phạm vi mở rộng trong HTML, Cloud và training có thể là tùy chọn |
| NPU/board/resource/forwarding | Chưa kiểm chứng; số liệu inference hiện tại là CPU/Ollama trên host |

## Đối chiếu pha P0–P7

| Pha HTML | Đánh giá |
|---|---|
| P0: capability inventory và baseline trên target | Chưa hoàn tất; chỉ kiểm model/runtime host và tạo fixture |
| P1: nền chung, adapters, state/checkpoint, policy/audit | Một phần mô phỏng; chưa nghiệm thu runtime/board |
| P2: workflow/graph chẩn đoán | Có thử nghiệm mô phỏng phạm vi hẹp; chưa nghiệm thu theo P0 trên firmware |
| P3: transaction và lịch | Chưa triển khai |
| P4: monitor/inference theo nhu cầu | Chưa triển khai pipeline vận hành |
| P5: artifact/lifecycle triển khai | Chưa triển khai |
| P6: worker/data/Cloud tùy chọn | Có hồ sơ thí nghiệm local; chưa có các module runtime tương ứng |
| P7: tích hợp, IT-01–IT-10, ma trận nghiệm thu | Chưa thực hiện |

Không có cơ sở gắn nhãn đã nghiệm thu toàn bộ bất kỳ pha nào theo điều kiện HTML chỉ từ các test synthetic hiện tại.

## Đừng đồng nhất hai mục tiêu

HTML cho phép bắt đầu nhẹ bằng BM25, registry và dependency closure; PPR, GNN, học/evolve graph và tối ưu information gain là các hướng nghiên cứu, không phải mọi thứ đều bắt buộc cho MVP. Vì vậy thiếu GNN/PPR tự nó không chứng minh MVP sai.

Tuy nhiên, pilot hiện tại cũng chưa có đủ các ràng buộc và cấu trúc runtime cốt lõi đã mô tả trong HTML. Và khi mục tiêu là so sánh với paper, phải tích hợp hoặc tái lập đúng thuật toán đó trước, không gắn tên paper lên DFS rồi dùng kết quả như reproduction.

## Những việc cần hoàn thiện trước một kết luận mới

1. Chọn một baseline paper có code, nối thuật toán upstream với adapter Gateway, xác minh hướng cạnh và unit/reference outputs của upstream; giữ DFS cũ làm baseline riêng.
2. Triển khai tách G_S/G_SF/H_F/G_run; compiler tạo invocation DAG có typed edges, schema/predicate binding, verifier, node state và plan revision.
3. Lọc capability/permission trước cắt top-k; reretrieve theo missing facts/goal/state; loại bước đã đủ evidence; xử lý alternative/cost và repair có giới hạn.
4. Chấm riêng skill/function recall, prerequisite/bundle completeness, binding và plan validity, execution, diagnosis và citation. Tách phần model làm đúng khỏi trợ giúp của Core.
5. Dùng bộ test mới theo fault family, nhiều client/interface, thiếu/xung đột dữ liệu, distractor và trace thực; chỉ đưa dữ liệu target vào test khi đã có inventory/adapter và quyền phù hợp.

Đây là các việc còn thiếu, không phải tuyên bố đã được triển khai trong lần audit này. Xem `PAPER_FIDELITY_AUDIT.md` để đối chiếu trực tiếp với source paper.
