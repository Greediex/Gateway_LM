# 120-Skill expansion pack — reviewed v2 integration

Gói người dùng cung cấp đã được kiểm tra và tích hợp **opt-in** vào repository. Có **120 Skill thiết kế / 15 domain / 206 edges**, gồm 8 Skill references v0.1 và 112 proposals. 72 READ Function/Port/Skill contract pairs vẫn **PROPOSED**; 40 Skill khác chưa có direct READ Function, không được lấp bằng backend giả. [Nguồn ZIP và thay đổi khi import](SOURCE_IMPORT.json).

Đây không phải 120 Skill thực thi được hoặc 72 lệnh chạy trên router. Profile Linux live hiện có giữ nguyên, không tự nạp catalog này. 203 cạnh đề xuất chưa được duyệt ngữ nghĩa; 3 cạnh còn lại chỉ là references đối chiếu v0.1. Không gọi catalog preview là production GoS/SkillDAG hay benchmark chất lượng model.

## Dùng thử từ repo root

```bash
.venv-graph/bin/python -m gateway_pilot.skill_expansion.cli validate
.venv-graph/bin/python -m gateway_pilot.skill_expansion.cli search 'wifi không có internet' --include-proposed
.venv-graph/bin/python -m gateway_pilot.skill_expansion.cli review-diff --output runs/skill-expansion/edge-review.json
.venv-graph/bin/python -m scripts.validate_overlay_v2
.venv-graph/bin/python -m scripts.core_replay_smoke_v2 --synthetic-only --all
.venv-graph/bin/python -m scripts.audit_skill_upgrade --repo . --output runs/skill-expansion/audit.json
```

CLI search chỉ preview metadata, không cấp quyền và không gọi tool. Nếu không thêm `--include-proposed`, retrieval chỉ xét các reference Skill v0.1. Dashboard [HTML standalone](dashboard_skills.html) có thể mở trực tiếp trên máy; không phải màn hình live của Web/API. [Sơ đồ SVG](graph_120_proposal.svg), [206 edges](GRAPH_206.md), [120 Skill](SKILLS_120.md), [mapping](SKILL_FUNCTION_MAPPING_120.md), [workbook nguồn](source/GatewayLM_120_Skills_Graph_Proposal.xlsx).

## Ranh giới runtime

`RuntimeSkillBridge` chỉ lấy membership/completion ports từ registry v0.2 đã load và snapshot capability đúng registry/context/ACL/lease. Khi gọi execute, nó vào `ReadRuntime.execute → Compiler → shared execution kernel → GraphRunner → Verifier`; không có Runner khác và không sửa Core. Core vẫn kiểm lại capability, permissions, bindings và runtime contracts trước call; preview plan không phải authorization.

Synthetic smoke tạo catalog IMPLEMENTED trong TemporaryDirectory và binding approval test cho synthetic target; source proposals không đổi lifecycle. Năm Function client cần thêm verified `client.identity` dependency trong sandbox, được đo bởi Core trước output client; không inject raw initial_evidence và không nới target gate. Schema arguments đã thêm `required: []` theo schema thật của repo.

Conformance/mock/replay không phải firmware acceptance. Muốn chạy thiết bị thật phải có provider tương đương, exact approved artifact/binding, capability verification và ACL/context/freshness phù hợp. Cạnh `composes_with` hoặc điểm retrieval không thay typed dependency hay Claim. Các phần RCA/LLM/Devices/DHCP/History còn theo [NEXT roadmap](../NEXT_ROADMAP_V2.md); import pack không đánh dấu hoàn thành các task đó.

## Kiểm thử

```bash
.venv-graph/bin/python -m unittest tests.test_skill_expansion tests.test_skill_expansion_v2 tests.test_skill_expansion_core_v2 -v
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m unittest discover -s tests -v
```

[Acceptance trong checkout v2](../reports/SKILL_EXPANSION_INTEGRATION_20261113.md) tách kết quả thực đo ở repo khỏi báo cáo offline đi kèm ZIP. Không chạy installer/generator của tài liệu đính kèm; chỉ code đã review được import, dữ liệu baseline/frozen giữ nguyên.

## CAT-01 đã chốt

[Profile Wi-Fi gateway replay](CAT01_PROFILES.md) chọn B02/B03/B05 và xuất coverage/gaps cho đủ 120 mapping. `python -m scripts.skill_profiles` kiểm pinned metadata và tạo artifact/report; chưa tạo runtime binding hay launcher (CAT-02/03).
