# CLAUDE.md — Hướng dẫn cho AI agent làm việc trên Gateway LM

File này là điểm vào cho Claude Code và mọi AI agent. Quy tắc kỹ thuật đầy đủ nằm ở [AGENTS.md](AGENTS.md); kế hoạch/tiến độ chỉ ghi ở [TODO.md](TODO.md); thuật ngữ ở [CONTEXT.md](CONTEXT.md). Khi mâu thuẫn, thứ tự ưu tiên: **khối KHÓA dưới đây → AGENTS.md → TODO.md → phần còn lại của file này**.

## Dự án là gì

Pilot chẩn đoán mạng gateway dựa trên bằng chứng: người dùng hỏi tự nhiên → Router/LLM tra catalog → Resolver/Planner đề xuất Function DAG → Runner (`graph_v3.execution_kernel.execute_ready_once` + `GraphRunner.step`) thực thi qua adapter allowlist → Verifier/Claim Engine xác minh → câu trả lời chỉ dựa trên evidence đã xác minh. Nhánh làm việc: **`v2`**.

## Lệnh bắt buộc trước khi báo "xong"

```bash
python -m scripts.check_project
```

```bash
python -m unittest discover -s tests -v
```

Báo đúng số pass/fail/skip thực tế và URL CI; không báo xong khi chưa chạy.

<!-- LOCKED-CRITERIA:BEGIN -->
## KHÓA — Tiêu chí AI không được vượt qua

Khối này được khóa bằng SHA-256 trong `scripts/check_project.py` (`LOCKED_CRITERIA_SHA256`). Mọi chỉnh sửa khối làm `check_project` FAIL. Chỉ chủ dự án (người) được đổi khối này và hash cùng lúc, trong commit riêng có lý do. AI **không được** tự cập nhật hash, nới kiểm tra hay xóa marker để test xanh.

**L1 — Trung thực về số liệu.** Không tuyên bố vượt số đo thực: registry v0.1 có 8 skill / 17 Function; catalog có 120 Skill nhưng *catalog ≠ đã chạy*. Một Skill chỉ được tính "Simulation verified" khi có fixture ý nghĩa, đi qua Core/Verifier và có negative case. Không nhập số coverage bằng tay.

**L2 — Không tuyên bố phần cứng khi chưa đo.** Không nói chạy được trên OpenWrt/firmware/NPU, không đánh dấu `PROBE_OK` hay "Router verified" nếu thiếu hash phần cứng/firmware, output Ubus từ board thật và số đo CPU/RAM/NPU. Metric máy CI Ubuntu không tính.

**L3 — Read-only mặc định, WRITE bị chặn.** AI, LLM, GoalAgent, RCAAgent, Web không được gọi WRITE controller, không cấp quyền WRITE, không tự lặp lại hàng outbox `IN_FLIGHT`. Không thêm đường thực thi lệnh từ text người dùng/LLM; chỉ Function ID có kiểu + adapter allowlist.

**L4 — Không đường tắt quanh Core.** Mọi thực thi READY chẩn đoán đi qua `execute_ready_once` / `GraphRunner.step`. Không nới hoặc bỏ ACL, scope/target, schema, TTL, budget, kiểm tra SHA upstream để kết quả "đẹp". Điểm vector/LLM không bao giờ vượt qua eligibility hay xác minh evidence.

**L5 — Evidence ≠ giả thuyết.** Nhãn RCA/`RESOLVED` cần Claim được đánh giá TRUE với evidence ID đã xác minh, đúng scope, còn hạn. Giả thuyết (kể cả từ cloud/LLM) không bao giờ là bằng chứng. Không dùng nhãn gold/ground-truth trong prompt suy luận hoặc làm evidence.

**L6 — Không phá dữ liệu đóng băng và lịch sử.** Không sửa `data/frozen_manifest.json`, fixture frozen, protocol Graph v3/v4, báo cáo lịch sử. Đánh giá mới phải có version riêng. Không tune trên test set cuối. Không cập nhật approval/hash tự động để ép test pass.

**L7 — Test là ràng buộc, không phải chướng ngại.** Không xóa, skip, quarantine hoặc làm yếu test/assertion để đạt xanh. Interface mới phải có test negative-path (sai target, thiếu quyền, response hỏng, timeout, fact cũ).

**L8 — Git và bí mật.** Không push/merge vào `main` khi chưa có chấp thuận rõ ràng; không force-push nhánh của người khác. Không commit secret, định danh người dùng, capture mạng, model, `runs/`, virtualenv.

**L9 — Phạm vi thay đổi.** Thay đổi nhỏ, gắn kết; không rewrite-from-scratch, không di chuyển file hàng loạt, không tạo kiến trúc agent/executor thứ hai, không thêm điều kiện theo tên workflow trong Core. Kế hoạch chỉ cập nhật trong `TODO.md`.
<!-- LOCKED-CRITERIA:END -->

## Cách làm việc khuyến nghị

- Đọc `TODO.md` để biết task đang mở (P0: COV-01…04, DATA-01/02, FINALIZE-02, CHAT-01, UI-01) trước khi bắt đầu.
- Mở rộng qua registry/interface hiện có (`gateway_pilot/skill_expansion`, `gateway_pilot/graph_v3`, `gateway_pilot/application`), tái dùng ReadSession/GraphRunner/Verifier.
- Commit nhỏ lên `v2`; message mô tả rõ thay đổi và giới hạn còn lại.
- Khi không chắc một tuyên bố có được chứng minh không: ghi là *chưa xác minh*.

Chi tiết: [Developer Guide](docs/DEVELOPER_GUIDE.md) · [Docs index](docs/INDEX.md).
