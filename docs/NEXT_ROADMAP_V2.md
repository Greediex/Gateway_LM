# Gateway LM v2 — Roadmap sau Foundation

Ngày chốt backlog: **13/11/2026**. Nguồn: bảng NEXT-01…12 người dùng gửi sau FND-07. Đây là công việc dự kiến, không phải các khả năng đã nghiệm thu.

Baseline: FND-01…07 đã hoàn tất; Linux live profile có 7 selected READ Functions qua Core và verified snapshot/UI. RCAAgent, Claim Engine, bounded LLM proposal, Ubus adapter, checkpoint và journal đã tồn tại nhưng chưa đồng nghĩa chúng đã tích hợp vào profile laptop v0.2. [Trạng thái hiện có](TASK_STATUS.md), [laptop guide](LAPTOP_NETWORK_V2.md).

## Backlog và dependency

| Task | Ưu tiên | Công việc | Tận dụng | Phụ thuộc chính |
|---|---|---|---|---|
| NEXT-01 | P0 | Tích hợp RCA Agent với Core READ v0.2 và VerifiedSnapshot | RCAAgent, GraphRunner, Verifier, Claim Engine | FND-06/07 |
| NEXT-02 | P0 | Chẩn đoán thích ứng theo evidence và mục tiêu còn thiếu | Planner, Repair, Claim Engine | NEXT-01 |
| NEXT-03 | P0 | Tích hợp LLM Goal Proposal có kiểm soát | OllamaGoalModel, BoundedGoalProposer, Registry, Policy | NEXT-01/02; baseline NEXT-10 |
| NEXT-04 | P0 | Hoàn thiện catalog Wi-Fi, Devices, DHCP theo READ contracts | Catalog v0.2, Feature Registry | FND-03…07; làm độc lập với RCA |
| NEXT-05 | P0 | Mở rộng OpenWrt READ adapter qua replay/mock | UbusReadAdapter, CompositeAdapter | NEXT-04; phần I/O tối thiểu NEXT-11 |
| NEXT-06 | P1 | Chẩn đoán từng thiết bị và quan hệ Client–AP–Router | Graph, Client Scope, RCA | NEXT-01/04/05 |
| NEXT-07 | P1 | History và chuỗi Verified Evidence có giới hạn | Snapshot, EvidenceCheckpoint, ReadOnlyJobJournal | FND-06/07; thêm RCA history sau NEXT-01 |
| NEXT-08 | P1 | Monitoring, Alerts và Incident lifecycle | History, diagnostic rules, RCA | NEXT-07; NEXT-02 cho RCA thích ứng |
| NEXT-09 | P1 | Web UI cho RCA, Devices, History và Alerts | Web UI hiện có | Mở từng phần theo NEXT-01/06/07/08 |
| NEXT-10 | P0 | Đánh giá độc lập LLM, selection, RCA và latency | Benchmark framework | Bắt đầu từ baseline FND-07; mở rộng cùng NEXT-01/02/03 |
| NEXT-11 | P1 | Resource limits, timeout và xử lý lỗi Ubus | CompositeAdapter, UbusCliReadTransport | Làm phần cần thiết trước acceptance NEXT-05/12 |
| NEXT-12 | Để sau | Nghiệm thu OpenWrt trên firmware thật | OpenWrt adapter và firmware profile | NEXT-05/06/10/11; có thiết bị và scope rõ |

## Điều kiện nghiệm thu từng task

- **NEXT-01:** Đăng ký Claim/workflow phù hợp v0.2 và nối RCAAgent vào trusted runtime hiện có. RCA đánh giá trên CaseState/verified facts; VerifiedSnapshot là view xuất kết quả, không deserialize JSON thành quyền/evidence. Mọi measurement qua shared execution kernel. Kết luận cần Claim TRUE và evidence đúng target, contract, freshness; thiếu evidence trả INCONCLUSIVE. Có replay/mock và regression v0.1/laptop.
- **NEXT-02:** Sau mỗi measurement, đánh giá lại Claim và chọn evidence deficit tiếp theo. Test timeout, unsupported producer, alternative, expired facts, no-progress và hết budget. Không đo toàn bộ catalog mặc định; không lặp vô hạn hoặc tự nâng quyền khi repair.
- **NEXT-03:** Opt-in local model chỉ đề xuất registered READ goals từ tập đã được policy lọc, qua BoundedGoalProposer. Không nhận Function IDs, commands, permissions hoặc targets do model tự tạo. Test malformed/hallucinated goals, prompt injection, WRITE lẫn READ, timeout và fallback/clarification; đo riêng hiệu quả model so với baseline.
- **NEXT-04:** Chốt semantic/scope/version/provenance cho Wi-Fi, client inventory/association và DHCP leases/pool/service. Phân biệt dữ liệu laptop với AP/router; unknown không thành giá trị giả. Builder, approved bindings, capability gates và positive/negative tests đầy đủ; counts tách metadata/mock/live verified.
- **NEXT-05:** Reviewed mapping/normalization cho contract mới, typed complete outputs và exact binding/context pins. Replay/mock kiểm unsupported methods, bad schema, foreign/duplicate output, mất hỗ trợ và lỗi transport; không fallback sang synthetic data trong live path. Kết quả chỉ được ghi nhận mock/replay acceptance, chưa có firmware support.
- **NEXT-06:** Target resolver dựa trên inventory evidence, quan hệ Client–AP–Router có provenance/TTL. Thiếu hoặc mơ hồ identity phải hỏi thêm; test nhiều client, sai AP/router, stale mapping và isolation. Không đo máy khác rồi gắn nhãn cho thiết bị được hỏi.
- **NEXT-07:** Bounded retention/quota và versioned records giữ evidence ID/source/target/time/contract. Query lịch sử không làm mới TTL; historical observation không tự thành fact hiện tại. Test restart/integrity, contract/ACL/context mismatch và hết quota; tách raw payload khỏi journal audit.
- **NEXT-08:** Chu kỳ đo có quota/deadline, dedup/debounce và incident transitions dựa trên evidence. Thiếu/stale data là UNKNOWN/measurement failure, không tự đóng incident thành resolved. Test repeated faults, recovery, mất backend, scheduler overlap và resource exhaustion.
- **NEXT-09:** Từng màn hình chỉ mở khi application API tương ứng có thật; RCA có Claim/evidence, Devices có scope, History có thời điểm lịch sử, Alerts có incident state. Test loading/error/missing/stale, HTTP isolation và UI trực quan; không thêm quyền thực thi qua request.
- **NEXT-10:** Chốt dataset/labels, dev/test split và metric trước khi tune. Báo selection correctness, Claim-backed RCA correctness, abstention/false-positive, tool calls/repair, model-invalid rate, latency p50/p95 và host resources. Giữ frozen baselines; dùng corpus/report version mới, không tune trên test hay gọi illustrative data là holdout. Không coi host/replay latency là router/NPU proof.
- **NEXT-11:** Giới hạn output bytes tại transport, timeout/cancellation/process cleanup và bounded retries/resources. Backend lỗi không kéo hỏng các backend khác hoặc làm mất audit; không leak payload qua exception. Test quá kích thước, treo, partial JSON, nonzero exit và support loss trước khi chạy trên firmware.
- **NEXT-12:** Chỉ triển khai khi có thiết bị và quyền READ được xác định. Ghi board/firmware hash, mapping Ubus thực, capability probes và trace qua Core; đo CPU/RAM/NPU nếu có yêu cầu tương ứng. Có phạm vi vận hành/recovery rõ, không suy hardware acceptance từ mock/CI; WRITE không nằm trong task này.

## Thứ tự triển khai

1. Chuẩn bị **NEXT-10 baseline/harness** và thực hiện **NEXT-01** trên profile nhỏ hiện có.
2. **NEXT-02 → NEXT-03**, đánh giá bằng cùng protocol NEXT-10 đã khóa trước.
3. **NEXT-04 → NEXT-05**, đưa phần NEXT-11 cần cho transport vào trước mock acceptance; đây là nhánh công việc có thể tiến hành cùng RCA.
4. Mở **NEXT-06/07 → NEXT-08**; **NEXT-09** phát triển theo từng API đã được nghiệm thu.
5. **NEXT-12** để sau; chỉ bắt đầu khi prerequisites và thiết bị thật đã sẵn sàng.

Không xây RCA/LLM/Ubus framework mới khi thành phần hiện tại đã đáp ứng. Foundation và legacy regression tiếp tục là gate cho từng task; danh sách này không tự cho phép thao tác router hoặc bật WRITE.

## Input mới: 120-Skill integration pack

[Pack đã review](skill_expansion/README.md) cung cấp catalog thiết kế, 72 READ proposals và synthetic Core smoke làm đầu vào cho NEXT-04/05/10. Chưa hoàn thiện semantic domain contracts, RCA/LLM/Devices/History hoặc firmware support; giữ toàn bộ NEXT task pending. 203 proposed edges cần typed/semantic review trước production graph integration.
