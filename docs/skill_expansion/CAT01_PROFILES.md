# CAT-01 — Mapping 120 Skill và profile READ đầu tiên

**Ngày:** 16/11/2026. [Checklist](../../TODO.md), [acceptance](../reports/CAT01_PROFILES_20261116.md), [coverage/gaps JSON](../reports/CAT01_PROFILE_COVERAGE_20261116.json).

## Batch đã chọn

Profile [wifi_gateway_replay_v1](../../config/skill_profiles/wifi_gateway_replay_v1.json) chọn domain thiết kế **B / Wi-Fi**, scope **gateway**, backend descriptor synthetic `expansion.synthetic_replay` revision `0.2.0`.

| Skill | Runtime Skill / version | Function / version | Completion Port / version |
|---|---|---|---|
| B02 — Radio/SSID health | gateway.b02 / 1.0.0 | expansion.radio_health / 1.0.0 | expansion.radio_health / 1.0.0 |
| B03 — SSID configuration | gateway.b03 / 1.0.0 | expansion.ssid_config / 1.0.0 | expansion.ssid_config / 1.0.0 |
| B05 — Airtime usage | gateway.b05 / 1.0.0 | expansion.airtime_usage / 1.0.0 | expansion.airtime_usage / 1.0.0 |

Đây là ba observation cùng scope, chưa có Claim chẩn đoán hoặc backend router. Scope gateway biểu diễn thiết bị giả lập trong profile, không phải khả năng đo router thật. Domain B là phân nhóm thiết kế; contracts gốc vẫn nằm trong namespace/domain vật lý `skill_expansion`.

Profile pin exact Function/Port/Skill versions, **9 metadata contract hashes** và canonical digest của source bundle (design graph/mapping/proposal contracts/legacy registry). Target policy chỉ cho namespace `synthetic-` và đòi explicit trusted environment context tại runtime. Backend descriptor không phải binding hay probe approval.

Ba Function đang có zero inputs, không có ORDER constraints, vì vậy dependency witness xác nhận chúng độc lập về metadata. Profile không suy ra order/dependency chỉ vì chúng cùng domain. CAT-02 có trách nhiệm review deployment records, lifecycle, bindings và phiên thực thi; source PROPOSED không đổi ở CAT-01.

## Audit toàn bộ 120 mapping

| Phân loại | Số lượng | Gap cần giữ rõ |
|---|---:|---|
| Legacy references | 8 | Có Function references v0.1, cần mapping v0.2 tường minh trước khi chọn |
| Direct READ proposals | 72 | Contracts tham chiếu nhau hợp lệ, chưa có approved deployment binding |
| Composite/workflow | 40 | Chưa có direct Function; cần workflow/Claim definition |
| Client identity gap | 5 | Subset của 72: inputs chưa khai báo `client.identity`; bị chặn nếu chọn vào profile |
| Cross-scope composite | 9 | Subset của 40: cần thiết kế aggregation và isolation |

Năm client proposals: device_vendor, identity_consistency, client_association, wireless_signal, roaming_events. Smoke sandbox trước đây thêm identity tạm để kiểm Core; metadata source chưa có dependency đó. CAT-01 không dùng smoke helper làm deployed contract và không chèn raw evidence để vượt gate.

Mapping audit kiểm cardinality/duplicate/unknown IDs, reciprocal Function–Skill membership/completion, source scope/suggestions và legacy references. Thiết kế mapping hiện lưu Function IDs không có versions, nên nhiều version cùng ID là ambiguous và bị chặn cho tới khi mapping được chốt rõ; selection không tự chọn latest. Một Function có thể phục vụ nhiều Skill khi membership đã khai báo đầy đủ.

## Review graph

Toàn bộ **203 proposed edges** được xuất với `NOT_APPLIED`, `runtime_approved:false`; ba legacy reference edges không được tự cài vào registry profile. Typed witness được tìm từ exact output/input versions và scope; soft affinity không tạo dependency.

Cạnh đáng chú ý với batch đầu: **B05 → B06 / produces_for**. B05 sinh channel utilization; B06 có RF-environment output nhưng contract không khai báo input tiêu thụ airtime. Vì không có typed supplier–consumer witness và B06 chưa được chọn, cạnh này **không được dùng cho execution**. Tương quan nghiệp vụ có thể được xem xét ở NEXT-04; không đổi labels hoặc approval để ép vào DAG.

## Chạy kiểm tra / xuất report

Từ repo root với môi trường đã cài dependencies:

```bash
python -m scripts.skill_profiles > runs/cat01-coverage.json
# Artifact metadata mặc định: runs/skill-profiles/wifi_gateway_replay_v1.registry.json
python -m unittest tests.test_skill_profiles -v
```

Tạo thư mục `runs` trước khi shell redirect nếu clone mới chưa có. Có thể pin `--profile` và `--registry-output` từ CLI operator; không có endpoint HTTP nhận file/profile/commands. CLI không gọi backend/probe, không nạp runtime và không cấp quyền. Official validator/builder được tái sử dụng; artifact `execution_enabled:false` và lifecycle PROPOSED.

Coverage tách **declared=120**, **selected=3**, **runtime bindings=0**, **current profile replay-verified=0**, **live-verified=0**. Kết quả lịch sử 72 individual synthetic smokes nằm trong acceptance trước; chúng không attest profile mới hoặc quyền chạy live. Report không có timestamp để cùng source/profile sinh cùng nội dung.

Dữ liệu source và frozen baselines giữ nguyên. Khi source, mapping, version hoặc schema thay đổi, profile pin phải được review/update tường minh; công cụ không tự sửa pin để làm validation xanh. Runtime chung và CLI/API/Web launcher tiếp tục CAT-02/CAT-03.
