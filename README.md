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

1. Giữ nguồn **Đo thật từ Linux**. Bấm **Làm mới** ở Tổng quan laptop để chạy các phép đo.
2. Xem Wi-Fi association, signal **%**, channel/frequency và tốc độ AP quảng bá khi đọc được; mở từng mục để xem evidence ID, nguồn và thời gian.
3. Xem interface route đang dùng. Nếu Wi-Fi và Ethernet/VPN cùng tồn tại, probe qua Ethernet/VPN **không** chứng minh Internet qua Wi-Fi.
4. Thử chat: **“Wi-Fi laptop có vấn đề gì?”**, **“Gateway hiện tại là gì?”**, **“Kiểm tra Internet của máy này”**, **“Kiểm tra DNS”**.
5. Snapshot có TTL 30 giây; khi hết hạn dashboard xóa số đo và yêu cầu **Làm mới**. Không tự chạy phép đo nền.

Chưa có required evidence thì hiện INCOMPLETE; chưa có backend thì UNAVAILABLE. MEASURED cho biết phép đo hoàn thành, không phải chẩn đoán nguyên nhân hay lời bảo đảm mạng khỏe. Không phản hồi ICMP có thể do lọc ping. IP/DNS phản hồi chưa chứng minh truy cập web. Signal % không chuyển thành RSSI dBm; tốc độ AP quảng bá không phải throughput Internet. Router CPU/RAM/health luôn unavailable ở profile laptop.

Linux live hiện dùng Core READ v0.2 với mục tiêu hữu hạn; UI tắt lựa chọn LLM/ReAct ở nguồn này. Các thử nghiệm LLM/GoS/ReAct cũ vẫn có ở replay/Windows theo khả năng backend.

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
- [Todo list](TODO.md) · [Trạng thái task](docs/TASK_STATUS.md) · [Docs index](docs/INDEX.md)
- [Function Contract v0.2](docs/contracts/catalog-v02/README.md) · [Catalog tooling](docs/CATALOG_V02.md)
- [Trusted runtime v0.2](docs/RUNTIME_V02.md) · [Feature Registry](docs/FEATURE_REGISTRY_V02.md)
- [Developer guide](docs/DEVELOPER_GUIDE.md) · [Coding rules](AGENTS.md)
- [Các thử nghiệm v0.1 và tài liệu cũ](docs/README_V01_DETAILS.md) · [TaskRuntime](docs/TASK_RUNTIME.md) · [Evidence RCA](docs/EVIDENCE_RCA.md)

Để thêm Function/backend: khai báo contract, pin version, review binding, probe và test qua Core. Không đưa command/quyền/target từ chat hoặc HTTP xuống hệ điều hành. Những danh mục yêu cầu cũ không phải số lượng lệnh đã được nghiệm thu trên thiết bị.
