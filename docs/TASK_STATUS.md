# Gateway LM v2 — Trạng thái hiện tại

Cập nhật **16/11/2026**, baseline code **`f7389fb`**, nhánh **v2**. Công việc còn lại nằm trong [TODO chính](../TODO.md).

| Thành phần | Đã triển khai | Giới hạn |
|---|---|---|
| Catalog/contract v0.2 | Validator/builder, version/approval pins, mapping 120 Skill | Có tên trong catalog chưa phải capability |
| Laptop live | 8 READ Functions; SK01/A08 local + 6 action laptop | 118 Skill thiết kế chưa có live runtime; chưa nghiệm thu router |
| Session/Core | ReadSession chia sẻ facts và budget, GraphRunner/shared execution kernel, Verifier | TTL/context/ACL thay đổi có thể yêu cầu đo/khởi tạo lại |
| LLM chat | Model local tra catalog, chọn/phối hợp Skill, chọn tiếp hoặc trả lời bằng verified findings | Chất lượng chọn Skill/bao phủ ý định và latency cần đánh giá độc lập |
| RCA | RCAAgent đánh giá declared Claims trên cùng state/session, đưa candidate goals trở lại model | Predicate đã xác minh không phải causal proof hay sự cố đã khôi phục |
| Web/CLI/API | Chat/Trace, launcher chọn Skill thủ công, evidence/source/scope/time/TTL | History hiện tại trong bộ nhớ; chưa phải monitoring liên tục |
| Replay | Profile B02/B03/B05 và smoke của source proposals | Synthetic, không thay nghiệm thu live/hardware |

## Bằng chứng gần nhất

- Full regression tại baseline: **734 tests — 729 pass, 5 Windows-only skips**; project check và review độc lập đạt. [CI đúng commit](https://github.com/Greediex/Gateway_LM/actions/runs/43822807667).
- Qwen thật trên laptop: DNS chọn 1 Skill/3 calls; Wi-Fi + gateway phối hợp 2 Skill/4 calls và dùng lại route; yêu cầu SNR báo PARTIAL/thiếu B04. [Biên bản đã bỏ định danh mạng](reports/LLM_SKILL_CHAT_ACCEPTANCE_20261116.json).
- Các ví dụ local trên không phải holdout benchmark. Khi CPU bận, inference có thể kéo dài quá TTL; evidence cũ bị từ chối, cần đo lại.

## Ranh giới dữ liệu

120 Skill thiết kế gồm 8 legacy references và 112 proposals. Source pack có 72 READ contract proposals và 203 cạnh chưa duyệt; chúng vẫn không tự cấp quyền thực thi. 270 là requirements, không phải 270 Skill/Functions đã nghiệm thu. Frozen data/benchmark và lịch sử contracts v0.1 được giữ nguyên.

[Luồng LLM–Skill–RCA](LLM_SKILL_CHAT.md) · [Launcher/session](LAPTOP_SKILL_LAUNCHER.md) · [Guide catalog](skill_expansion/README.md)

Các checklist/trạng thái cũ đã được bỏ khỏi trang hiện hành; báo cáo nghiệm thu theo từng mốc vẫn nằm trong `docs/reports/` và lịch sử Git để đối chiếu.
