# Local Linux client catalog — FND-04 conformance example

Catalog riêng cho identity/IPv4 của interface laptop do operator chọn, không tự nạp runtime. Hai Function `clients.resolve`, `client.ipv4` version 5.0.0; hai Port 3.0.0 với provenance `linux_client/`; hai Skill 2.0.0. Bump major vì đổi provenance/output references so với replay.

Dùng [policy](../../config/catalog_policy.laptop.example.json), [selection](../../config/catalog_selection.laptop.example.json) và [binding/conformance guide](../../docs/ADAPTER_BINDINGS_V02.md). Lifecycle IMPLEMENTED từ FND-06; [runtime bridge](../../docs/RUNTIME_V02.md) vẫn đòi operator pins, support probe và ACL/context, không tự quảng bá capability. Không có RSSI dBm trong provider hiện tại, không dùng signal % thay thế.

Không chứa IP, MAC, SSID, boot ID hay binding environment của laptop thật. Các giá trị live chỉ xuất hiện trong bộ nhớ provider; report đã redact chỉ ghi trạng thái/provenance/digest mẫu. v0.1 và seed replay catalog không đổi.
