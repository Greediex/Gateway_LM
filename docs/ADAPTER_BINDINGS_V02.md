# FND-04 — Trusted READ Adapter Binding và Conformance

Binding declarations được kiểm theo [schema](contracts/catalog-v02/binding.schema.json), tách khỏi registry artifact để tránh circular hash. Đây là cấu hình startup dành cho developer/operator; không nhận từ HTTP/LLM và không tự nạp plugin.

## Binding và quyền duyệt

Mỗi binding pin exact registry content digest, metadata Function digest/version, backend ID/revision/source, scope, target và environment fingerprint. `function_digest` ở đây là SHA-256 của metadata Function document, **khác** runtime `Function.digest()`; runtime bridge ở FND-06.

`declare_binding(...)` chỉ tạo declaration, không approve hoặc gọi backend. `read_binding_declarations(path)` đọc JSON bounded, từ chối duplicate keys, unknown fields và approval nằm trong file. [Replay example](../examples/binding_selection.replay.json) chứa declaration synthetic, không có quyền chạy.

`BindingSelection` yêu cầu `approved_digests: frozenset[str]` riêng và `backends: dict` chứa service objects do startup Python cung cấp. Không có default approvals, import path, shell command hay fallback backend. Approval pins phải được operator review/pin ngoài declarations; không tự tính rồi tin chúng từ đầu vào chưa được duyệt.

Constructor kiểm registry bằng `verify_registry`, copy snapshot, kiểm approvals/pins/probe implementation/provenance và uniqueness trước probe/sample. Một Function chỉ được gán một backend trong context; Function chưa gán không tự lấy backend khác. Backend implementation thay đổi phải bump revision và được review lại. Backend objects là trusted code, không phải sandbox cho Python bên thứ ba.

## Context và conformance

`TargetContext(scope, target_id, environment_id)` là immutable server context. Harness nhận context/quyền do caller tin cậy cung cấp, không phải token tạo từ request. Trước mỗi lượt, kiểm lại target/environment, quyền READ, arguments, backend revision/source/probe IDs, rồi probe → sample → probe lại.

Mẫu phải là `ToolResult` thành công, có đúng tập output một lần, IDs duy nhất, schema/provenance, metadata version/digest, scope/target/environment khớp. Argument client_id và output client_id khi có phải là target đã chọn. Timestamp phải có timezone, không ở tương lai; reported source age cộng wall age không vượt contract TTL. Backend không tự tăng TTL.

Lỗi backend được chuẩn hóa, không đưa exception payload vào report. Function/arguments đưa cho provider là bản copy. Timeout result bị từ chối; không retry hoặc fallback.

Report luôn `execution_enabled:false`, `evidence_admitted:false`. `CONFORMANT` là kết quả kiểm giao diện/mẫu READ tại lúc đó; không phải capability `PROBE_OK`, không tạo CaseState Fact/Claim và không được cache như quyền thực thi. Diagnostic READY calls vẫn phải qua Core/shared kernel/Verifier khi có FND-06. `BindingSelection` không tự tạo CompositeAdapter/runtime route.

Các backend phải tự bound I/O. Harness kiểm elapsed probe/sample, không thể preempt arbitrary Python hoặc stuck kernel syscall; không có claim deadline end-to-end cho backend tùy ý. Provider Linux hiện chỉ dùng local kernel APIs, không có subprocess/network query.

## Hai provider

- `ReplayReadBackend`: fixture tách biệt, source `synthetic_replay/binding_v1`, environment digest gắn fixture và logical client. [Values](../examples/binding_replay_values.json) chỉ là dữ liệu synthetic.
- `LinuxClientReadBackend`: source `linux_client/binding_v1`, đọc local identity/IPv4 qua socket + ioctl SIOCGIFADDR. Interface do operator chọn, tên được giới hạn. Environment fingerprint ràng buộc boot, kernel, network namespace và interface index; không in raw boot ID. Provider không dùng shell, không ping hay đổi cấu hình.

Provider Linux chưa hỗ trợ `wifi.station` vì seed contract cần RSSI dBm. Không đổi `nmcli` signal % thành dBm. Không có IPv4 trả `configured:false,address:""`; điều này không chứng minh mất Internet hoặc không có IPv6. Wi-Fi association/quality/route/DNS/UI vẫn theo FND-07.

## Catalog laptop riêng

[Example catalog Linux](../examples/catalog_laptop/README.md) có hai Functions 5.0.0, hai Ports 3.0.0 và hai Skills 2.0.0. Provenance Linux khác replay nên dùng major versions mới; seed/v0.1 giữ nguyên. Function lifecycle vẫn PROPOSED dù đã có conformance sample.

```bash
.venv-graph/bin/python -m scripts.catalog validate --source examples/catalog_laptop --selection config/catalog_selection.laptop.example.json --policy config/catalog_policy.laptop.example.json
.venv-graph/bin/python -m scripts.catalog build --source examples/catalog_laptop --selection config/catalog_selection.laptop.example.json --policy config/catalog_policy.laptop.example.json --output runs/catalog-laptop/registry.json
.venv-graph/bin/python -m unittest discover -s tests/adapters -v
```

## API startup

```python
from gateway_pilot.adapters.bindings import BindingSelection
from gateway_pilot.adapters.conformance import ConformanceHarness

# artifact/policy/context/backends và approved_pins do startup operator cung cấp;
# declarations chỉ là metadata đã đọc và review, không chứa approval.
selection = BindingSelection(artifact, policy, declarations,
    approved_digests=approved_pins, backends=backends, context=context)
harness = ConformanceHarness(selection)
report = harness.check(binding_id, arguments, context, permissions)
```

Không gọi API này như một route chẩn đoán ngoài execution core. Việc operator cho phép chạy conformance READ không cấp quyền runtime hoặc WRITE. Approval pins của artifact/contract/target/environment cũ không dùng lại được sau khi pins thay đổi; không auto-renew/auto-approve.

[Nghiệm thu](reports/FND04_BINDINGS_CONFORMANCE_20261113.md) ghi rõ replay, laptop live và các giới hạn. Firmware/OpenWrt và WRITE chưa được nghiệm thu.
