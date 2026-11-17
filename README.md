# Gateway LM v2 — Laptop Network Assistant

Nhánh phát triển: **[`v2`](https://github.com/Greediex/Gateway_LM/tree/v2)**. Pilot READ-only để kiểm tra mạng của laptop Linux, xem phép đo và evidence ngay trên Web UI. **FND-01 → FND-07 đã triển khai**: versioned catalog, trusted bindings, Feature Registry, runtime bridge và laptop dashboard.

Linux live đọc Wi-Fi hiện tại, IPv4/route, ping gateway/IP công cộng và DNS. Dữ liệu đi qua registered Functions → shared GraphRunner → Verifier → verified snapshot → rules/UI. Windows live và synthetic replay vẫn có chế độ riêng. Chưa nghiệm thu OpenWrt, WRITE hoặc NPU.

## Chạy trên Linux

Cần Python 3.12+, NetworkManager đang quản lý Wi-Fi, `nmcli`, `ip`, `ping`; DNS dùng `resolvectl`/systemd-resolved. Ubuntu thường cung cấp qua `network-manager`, `iproute2`, `iputils-ping`, `systemd-resolved`. Thiếu công cụ/quyền đọc sẽ báo thiếu phép đo, không tự cài hay đổi cấu hình mạng.

```bash
git clone --branch v2 --single-branch https://github.com/Greediex/Gateway_LM.git
cd Gateway_LM
python3 -m venv .venv-graph
source .venv-graph/bin/activate
python -m pip install -r requirements-react.txt
python setup_upstream.py
bash web_gateway/start_linux.sh
```

Mở **[http://127.0.0.1:8765](http://127.0.0.1:8765)**. Script Linux mặc định dùng **live**; chỉ lắng nghe localhost. `setup_upstream.py` tải và kiểm SHA-256 GoS/SkillDAG tại commits cố định. Không bỏ qua bước này khi clone mới.

Nếu repo đã có sẵn:

```bash
git switch v2
git pull --ff-only origin v2
bash web_gateway/start_linux.sh
```

Có thể dùng `--port 8766` nếu cổng mặc định đang bận. Chọn đúng URL/cổng vừa in ở terminal.

## Test ngay trên UI

Ở **Chọn Skill trên laptop**: bấm **Khởi tạo phiên** → lọc **Có thể chạy trong phiên** → chọn Skill → **Chạy Skill đã chọn**. Màn hình có 120 hàng thiết kế cùng lý do availability và 6 action laptop riêng. Profile live hiện hỗ trợ **SK01/A08 local + 6 action laptop**, không đồng nghĩa hoàn thành 120 Skill. Chọn nguồn riêng **Replay first batch** để thử B02/B03/B05 bằng fixture synthetic.

Phiên tối đa 5 phút, 24 tool calls, 64 plans; tái sử dụng evidence còn hạn qua cùng Core. Đổi mạng/context hoặc mất capability yêu cầu khởi tạo lại. Lịch sử trên UI chỉ là tham chiếu trong phiên, chưa lưu bền. [Hướng dẫn launcher và giới hạn](docs/LAPTOP_SKILL_LAUNCHER.md).


1. Giữ nguồn **Đo thật từ Linux**. Bấm **Làm mới** ở Tổng quan laptop để chạy các phép đo.
2. Xem Wi-Fi association, signal **%**, channel/frequency và tốc độ AP quảng bá khi đọc được; mở từng mục để xem evidence ID, nguồn và thời gian.
3. Xem interface route đang dùng. Nếu Wi-Fi và Ethernet/VPN cùng tồn tại, probe qua Ethernet/VPN **không** chứng minh Internet qua Wi-Fi.
4. Thử chat: **“Wi-Fi laptop có vấn đề gì?”**, **“Gateway hiện tại là gì?”**, **“Kiểm tra Internet của máy này”**, **“Kiểm tra DNS”**.
5. Snapshot có TTL 30 giây; khi hết hạn dashboard xóa số đo và yêu cầu **Làm mới**. Không tự chạy phép đo nền.

Chưa có required evidence thì hiện INCOMPLETE; chưa có backend thì UNAVAILABLE. MEASURED cho biết phép đo hoàn thành, không phải chẩn đoán nguyên nhân hay lời bảo đảm mạng khỏe. Không phản hồi ICMP có thể do lọc ping. IP/DNS phản hồi chưa chứng minh truy cập web. Signal % không chuyển thành RSSI dBm; tốc độ AP quảng bá không phải throughput Internet. Router CPU/RAM/health luôn unavailable ở profile laptop.

Chat Linux hiện mặc định bật **LLM → catalog 120 Skill → SkillLauncher/ReadSession → GraphRunner/Verifier → RCAAgent → LLM**. Model local tự chọn và phối hợp ID Skill được hỗ trợ; Core giữ quyền chạy và bằng chứng. RCA đánh giá trong cùng phiên, không tạo Runner khác. Hệ thống kiểm tra các phần được yêu cầu trong câu hỏi; hoàn tất một Skill không đồng nghĩa trả lời đủ cả câu. Khi thiếu dữ liệu, model có thể chọn tiếp trong budget; dữ liệu phụ thuộc giữ trong Trace, câu trả lời theo đúng phạm vi được hỏi. [Chi tiết và giới hạn](docs/LLM_SKILL_CHAT.md).

Mặc định mỗi lượt có tối đa 4 vòng lựa chọn và deadline 120 giây. Evidence hết hạn được đọc lại tối đa một đợt qua cùng Core/session/budget; không tăng TTL. Nếu vẫn thiếu dữ liệu, hệ thống trả lời phần đã xác minh và chỉ rõ phần còn thiếu. Phiên/model đang bận trả HTTP 409/429; không xếp hàng suy luận vô hạn. Tra catalog không làm các Skill chưa có backend trở thành chạy được.

Câu hỏi như “kiểm tra SSID” chỉ hiển thị SSID. Câu hỏi chẩn đoán có nhận định và giới hạn riêng; “Đã có số đo” không đồng nghĩa đã chẩn đoán hay khắc phục. Cùng model local có thể chọn field và cách diễn đạt bằng placeholder trong tối đa hai lượt bổ sung, với hậu kiểm evidence sau suy luận; lỗi/timeout/dữ liệu cũ dùng fallback từ facts còn hạn. Chi tiết kỹ thuật nằm trong “Chi tiết phép đo” và Trace.

Chat laptop mặc định dùng `qwen3:4b`. Cần Ollama đang chạy và tải model trước:

```bash
ollama serve
# Terminal khác:
ollama pull qwen3:4b
bash web_gateway/start_linux.sh
```

Model cấu hình ở server qua `GATEWAY_LM_CHAT_MODEL`, không nhận model/endpoint tùy ý từ HTTP. Model không sẵn sàng thì báo rõ và không âm thầm dùng rules. Tắt **LLM suy luận** để dùng chat rules cũ. Các thử nghiệm LLM/GoS/ReAct cũ vẫn có ở replay/Windows.

## Replay và Windows

Replay tách biệt với laptop thật:

```bash
bash web_gateway/start_linux.sh --source replay
# Hoặc chạy một câu hỏi synthetic từ CLI:
.venv-graph/bin/python -m gateway_pilot.assistant \
  --fixture GLM-21-1 --request 'Laptop An có wifi nhưng không vào Internet' --trace
```

Windows PowerShell:

```powershell
py -3.12 -m venv .venv-graph
.\.venv-graph\Scripts\python.exe -m pip install -r requirements-react.txt
.\.venv-graph\Scripts\python.exe setup_upstream.py
.\web_gateway\start_windows.ps1 --source live
```

Windows giữ route/ping/DNS cũ; dashboard Wi-Fi FND-07 dành cho Linux, không quảng bá phép đo chưa có trên Windows. [Hướng dẫn Web/API](docs/WEB_UI.md).

## Catalog mở rộng 120 Skill (opt-in)

Đã tích hợp pack **120 Skill thiết kế, 206 quan hệ và 72 READ contract PROPOSED**. Đây là metadata/replay để phát triển tiếp; không tự thêm capability cho laptop/router hoặc duyệt 203 cạnh đề xuất. [Hướng dẫn, dashboard offline và kiểm chứng](docs/skill_expansion/README.md).

```bash
.venv-graph/bin/python -m gateway_pilot.skill_expansion.cli validate
.venv-graph/bin/python -m gateway_pilot.skill_expansion.cli search 'wifi không có internet' --include-proposed
.venv-graph/bin/python -m scripts.core_replay_smoke_v2 --synthetic-only --all
```

CLI cùng luồng Core:

```bash
python -m scripts.skills list --mode live
python -m scripts.skills run laptop.network.inspect --mode live
python -m scripts.skills run A08 --mode live
python -m scripts.skills run B02 --mode replay
```

## Kiểm thử và kiến trúc

```bash
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m unittest discover -s tests -v
```

Tests không tự probe mạng thật. Windows-only tests skip trên Linux; live laptop acceptance được ghi riêng. CI cho commit `v2` chạy bằng workflow_dispatch; [workflow](.github/workflows/composite-adapter-regression.yml).

| Đường dẫn | Nội dung |
|---|---|
| `catalog/`, `gateway_pilot/command_catalog/` | Contract v0.2, validator/builder và trusted runtime bridge |
| `examples/catalog_laptop_network/`, `config/` | Profile laptop READ và approval pin đã review |
| `gateway_pilot/adapters/linux_wifi.py` | Linux READ, không rescan/đổi kết nối |
| `gateway_pilot/observability/`, `features/`, `application/` | Verified snapshot, rules và application service |
| `gateway_pilot/graph_v3/` | Shared Compiler, Runner, Verifier và các pilot trước |
| `web_gateway/` | Local HTTP API và dashboard/chat |
| `data/`, `benchmarks/` | Baseline v0.1 và bộ dữ liệu frozen, giữ nguyên |

- [FND-07 và cách nghiệm thu laptop](docs/LAPTOP_NETWORK_V2.md)
- [TODO hiện hành: hoàn thiện chat LLM–Skill–RCA](TODO.md) · [Trạng thái task](docs/TASK_STATUS.md) · [Docs index](docs/INDEX.md)
- [Function Contract v0.2](docs/contracts/catalog-v02/README.md) · [Catalog tooling](docs/CATALOG_V02.md)
- [Trusted runtime v0.2](docs/RUNTIME_V02.md) · [Feature Registry](docs/FEATURE_REGISTRY_V02.md)
- [Developer guide](docs/DEVELOPER_GUIDE.md) · [Coding rules](AGENTS.md)
- [Các thử nghiệm v0.1 và tài liệu cũ](docs/README_V01_DETAILS.md) · [TaskRuntime](docs/TASK_RUNTIME.md) · [Evidence RCA](docs/EVIDENCE_RCA.md)

Để thêm Function/backend: khai báo contract, pin version, review binding, probe và test qua Core. Không đưa command/quyền/target từ chat hoặc HTTP xuống hệ điều hành. Những danh mục yêu cầu cũ không phải số lượng lệnh đã được nghiệm thu trên thiết bị.
