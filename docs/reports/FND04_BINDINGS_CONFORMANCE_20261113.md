# FND-04 — Trusted binding/conformance: nghiệm thu local

Ngày 13/11/2026; nhánh `v2`; base `422be26116935869e89b02fb67e4e66bd3baab92`.

## Kết quả

[Binding/conformance guide](../ADAPTER_BINDINGS_V02.md): exact registry/Function/backend/probe/target/environment pins, approval digests riêng, một backend/Function/context, không fallback; strict ToolResult/schema/provenance/freshness. Backend exceptions được sanitize; Function/arguments snapshot không bị provider sửa.

Thêm Replay READ provider và Linux kernel READ provider cho identity/IPv4, không subprocess/network/WRITE. [Catalog laptop riêng](../../examples/catalog_laptop/README.md) đổi provenance bằng major versions mới. Builder chỉ expose `verify_registry` từ helper cũ, giữ nguyên logic artifact verification; không có runtime bridge v0.2.

[JSON conformance đã redact](FND04_READ_CONFORMANCE_20261113.json):

- Replay synthetic: 3/3 phép kiểm CONFORMANT (identity, IPv4, Wi-Fi fixture).
- Laptop Linux thật, interface Wi-Fi được chọn: 2/2 phép đọc CONFORMANT (identity/IPv4). Dữ liệu thực đọc bằng kernel API, không replay fallback.
- Provider chưa hỗ trợ RSSI dBm; `wifi_station_supported:false`. Không khẳng định chất lượng Wi-Fi/Internet.
- Mọi report đều `execution_enabled:false`, `evidence_admitted:false`; không có verified Fact/Claim/runtime capability được tạo. Không công bố IP/MAC/SSID/raw boot ID hoặc environment binding của máy thật.

## Kiểm thử

17 tests adapter/conformance kiểm cả positive và negative: thiếu approval, approval trong JSON, registry/version/digest sai, duplicate ownership, backend/probe chưa đăng ký, quyền thiếu, target/environment/args sai, mất support, backend lỗi/timeout, malformed/foreign/duplicate output, schema/source/scope/freshness sai, oversized source age, provider mutation và exception leakage. Catalog/example binding schema được self-check; replay declarations pin đúng artifact hiện tại. Linux ioctl được unit-test với payload giả và các lỗi no-address/missing-device.

Full local regression cuối: 562 tests, 557 pass, 5 Windows-only skip, 0 fail/error. Các golden compatibility tests vẫn giữ nguyên registry hash và 17 Function digests v0.1; 19 baseline data/benchmark file hashes khớp trước/sau.

Review riêng không còn finding có thể tái hiện qua API hợp lệ. Đường scalar output được kiểm tra lại: Port root schema v0.2 bắt buộc object và registry được revalidate, nên scalar sample bị reject trước khi xử lý identity. Checkpoint/journal/Runtime gates không bị thay đổi.

Commands:

```bash
.venv-graph/bin/python -m unittest discover -s tests/adapters -v
.venv-graph/bin/python -m unittest discover -s tests -v
.venv-graph/bin/python -m scripts.check_project
```

Log/capture local nằm trong `runs/fnd-04/` (Git ignore); không commit raw observation hoặc binding pins của laptop thật. Chưa có kết quả hosted CI tại lúc lập báo cáo local; URL/kết quả GitHub CI sau push được báo riêng. Không có OpenWrt/firmware/NPU acceptance và không bật WRITE. FND-05/06/07 vẫn là các task tiếp theo.
