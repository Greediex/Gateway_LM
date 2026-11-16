# Gateway LM v2 — TODO chạy catalog 120 Skill

Cập nhật **16/11/2026**, nhánh **`v2`**, dựa trên integration pack đã tích hợp tại `46ba358`. Đây là backlog hiện hành thay cho danh sách Foundation/GLM cũ. [Dependency và nghiệm thu chi tiết](docs/NEXT_ROADMAP_V2.md).

## Nền tảng đã có

- [x] Core READ v0.2, trusted binding/capability gates, Verifier và verified snapshot.
- [x] Linux laptop live + Web UI; profile riêng có 7 READ Functions.
- [x] Import và kiểm tra gói: 120 Skill thiết kế, 206 edges, 72 PROPOSED READ contracts; 72/72 synthetic Core smokes pass.

120 Skill gồm 8 legacy references +112 proposals; 40 Skill đề xuất chưa có direct READ Function. 203 cạnh chưa duyệt ngữ nghĩa. Con số 270 là requirements. [Guide của gói mới](docs/skill_expansion/README.md) · [Acceptance](docs/reports/SKILL_EXPANSION_INTEGRATION_20261113.md).

## P0 — Đưa gói mới vào luồng chạy

- [x] **CAT-01 — Chốt profile và mapping chạy:** phân loại đủ 120 Skill; chọn tập READ đầu tiên theo domain/scope; resolve Function/Port/version/completion và dependency; chỉ đưa cạnh đã review vào execution policy.
- [x] **CAT-02 — Registry và replay runtime dùng chung:** tạo deployment selection/policy và reviewed replay artifact/bindings; chạy tập đã chọn qua `RuntimeSkillBridge → ReadRuntime → GraphRunner → Verifier` trong cùng phiên, thay vì chỉ smoke từng Function trong TemporaryDirectory. Source PROPOSED và profile live giữ riêng.
- [x] **CAT-03 — Cho người dùng chọn và chạy Skill:** thêm CLI/API và màn hình catalog trong Web hiện có; tìm/lọc theo domain, hiển thị availability/reason, chọn Skill đã được runtime cấp READ; trả evidence, target/source/time/TTL và missing data. Replay phải có nhãn rõ; chưa có backend thì UNAVAILABLE.

**Mốc chạy đầu tiên:** chọn một Skill trong UI → đúng registry/binding/context → Core → verified evidence/snapshot → kết quả có thể kiểm tra. Không bật đồng loạt 120 Skill chỉ nhờ metadata.

## P0 — Chẩn đoán và mở rộng theo gói mới

- [ ] **NEXT-01:** Nối RCAAgent/Claim Engine vào Core READ v0.2 và kết quả chạy Skill từ CAT-02/03.
- [ ] **NEXT-02:** Chọn phép đo thích ứng từ Claim/evidence còn thiếu; giữ budget, repair và điều kiện dừng.
- [ ] **NEXT-03:** Nối LLM Goal Proposal có kiểm soát, chỉ đề xuất registered READ goals trong profile đang được cấp quyền.
- [ ] **NEXT-04:** Hoàn thiện semantic contracts Wi-Fi, Devices, DHCP từ 72 proposals; định nghĩa workflow/Claim cho các Skill composite trong nhóm 40 còn thiếu, không tạo Function giả để đủ số lượng.
- [ ] **NEXT-05:** Nối các contract đã review vào UbusRead/CompositeAdapter bằng replay/mock; exact mapping, normalization và capability gates.
- [ ] **NEXT-10:** Chốt baseline/dataset/labels/dev-test split trước khi tune; đánh giá Skill/Function selection, RCA, LLM, abstention, tool calls và latency p50/p95.

**Tiến độ nối luồng laptop:** NEXT-01/02/03 đã có chat LLM tra toàn catalog, chọn nhiều Skill, dùng shared ReadSession và RCAAgent đánh giá/đề xuất evidence tiếp theo. Declared Claims hiện chỉ cho phép đo laptop, không chứng minh causal RCA hay hỗ trợ router. Các task NEXT vẫn giữ unchecked cho phạm vi mở rộng. [Luồng tích hợp](docs/LLM_SKILL_CHAT.md).

## P1 — Thiết bị, dữ liệu dài hạn và vận hành

- [ ] **NEXT-06:** Resolve target và quan hệ Client–AP–Router bằng evidence; không trộn dữ liệu khác thiết bị/scope.
- [ ] **NEXT-07:** History có quota/retention, version/context pins; evidence lịch sử không tự thành fact hiện tại.
- [ ] **NEXT-08:** Monitoring/Alerts/Incident dựa trên verified evidence; dedup/debounce, UNKNOWN và recovery rõ ràng.
- [ ] **NEXT-09:** Mở rộng UI cho RCA, Devices, History và Alerts theo application API đã hoàn thành; tái sử dụng catalog launcher CAT-03.
- [ ] **NEXT-11:** Giới hạn tài nguyên/output bytes, timeout/cancellation và lỗi Ubus; phần cần cho mock acceptance đi trước NEXT-05.

## Để sau

- [ ] **NEXT-12:** Nghiệm thu READ trên OpenWrt firmware thật khi có thiết bị, mapping/profile và phạm vi vận hành rõ; mock/CI không thay hardware acceptance.

**Thứ tự bắt đầu:** `CAT-01 → CAT-02 → CAT-03 → NEXT-01 → NEXT-02 → NEXT-03`. NEXT-10 chuẩn bị baseline từ CAT-01; NEXT-04 làm theo domain và song song với RCA, NEXT-11 hỗ trợ NEXT-05. Các task chưa thực hiện đều giữ unchecked.

**Gate mỗi task:** kiểm metadata và negative paths, project check, regression phù hợp, không đổi frozen data/digests v0.1; kết quả thực thi phải qua shared Core và Verifier. WRITE không thuộc backlog chạy gói này.

**CAT-01 đã chốt:** [profile và review](docs/skill_expansion/CAT01_PROFILES.md), [coverage JSON](docs/reports/CAT01_PROFILE_COVERAGE_20261116.json). Batch B02/B03/B05, 3 Function/3 Port. CAT-02/CAT-03 đã có reviewed replay deployment, shared Core session và launcher CLI/API/Web. Nghiệm thu laptop-first: SK01/A08 scope local + 6 action laptop; 118 Skill thiết kế còn UNAVAILABLE trong live. [Hướng dẫn và giới hạn](docs/LAPTOP_SKILL_LAUNCHER.md).
