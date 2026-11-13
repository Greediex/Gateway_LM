# FND-05 — Feature Registry và advisory availability

Feature mô tả nhu cầu người dùng bằng READ ports, không phải một tool hoặc Agent có quyền riêng. [Schema manifest](contracts/catalog-v02/feature.schema.json) pin Feature ID/version, scope, required/optional port versions và permission READ. Cấm executable source, backend paths, capability/status, WRITE hoặc enabled flag trong manifest.

## Registry và flags

`FeatureRegistry(artifact, policy, manifests, flags)` revalidate và copy Catalog snapshot. Mỗi Feature ID chỉ có một version. Port references phải có đúng ID/version/scope trong selected registry; unknown refs, duplicate Feature IDs, required/optional trùng nhau hoặc manifest lỗi làm registration fail atomic. Đây là lỗi cấu hình; runtime unsupported được thể hiện qua availability, không bằng cách bỏ qua refs sai.

`read_feature_manifests(path)` và `read_feature_flags(path)` dùng strict bounded JSON reader, từ chối duplicate keys/unknown fields. Bundle manifests gồm `schema_version:0.2.0` và `features`; flags gồm `schema_version:0.2.0` và `enabled` map. Flags chỉ nhận boolean thật; flag thiếu mặc định disabled, flag ID không tồn tại bị từ chối. Registry/flags là snapshot; operator thay config thì tạo instance mới, không mutate bản đang phục vụ.

Giới hạn: tối đa 128 Features/flags, 16 KiB mỗi manifest, file bundle/flags 1 MiB; tối đa 64 required và 64 optional ports mỗi Feature, required không rỗng. IDs/version/description dùng chuẩn v0.2. Permission Feature là điều kiện bổ sung; không thay thế quyền Function hoặc Core ACL.

Ví dụ:

- [Replay manifests](../examples/features.replay.json), [flags](../config/feature_flags.example.json): thông tin kết nối client và Wi-Fi theo Port 2.0.0.
- [Laptop manifests](../examples/features.laptop.json), [flags](../config/feature_flags.laptop.example.json): identity/IPv4 local theo Port 3.0.0. Không gắn RSSI replay vào laptop live.

Các Feature này mô tả dữ liệu có thể yêu cầu, chưa có business diagnostics/UI mới ở FND-05. Một backend mới có cùng hợp đồng không cần sửa Feature; hợp đồng khác version/scope/provenance cần manifest profile tương ứng.

## Nguồn authority

Availability không gọi Adapter, probe, conformance harness, GraphRunner hay network. Nó chỉ đọc metadata và typed `CapabilitySnapshot` do trusted Core integration cung cấp.

Snapshot được pin registry digest, target/environment (`TargetContext`), exact permission set, `policy_context_id` và monotonic checked/expires times. `policy_context_id` là server identity/fingerprint của principal và ACL/policy revision hiện tại; không lấy nó từ request hoặc dùng một hằng số chung cho mọi user trong runtime.

Mỗi `FunctionCapability` có Function ID/exact version, metadata Function digest và một trong AVAILABLE/UNSUPPORTED/UNVERIFIED/PERMISSION_DENIED/TEMPORARILY_UNAVAILABLE. Không nhận report `CONFORMANT` làm capability. Snapshot immutable, tối đa 10.000 Function entries duy nhất, TTL >0 và ≤60 giây, timestamps hữu hạn và không quá 1e12 seconds. Snapshot chưa đến hiệu lực/hết hạn, sai version/digest/registry/context/permissions/policy hoặc có Function lạ đều fail closed.

Đây là in-process advisory input, không phải bearer token hay JSON credential. Không có API deserialize capabilities từ file/HTTP/LLM. Tạo được Python object không phải proof đã probe thiết bị: caller phải là Core service tin cậy, tự kiểm effective ACL/capability. FND-06 mới cung cấp producer nối runtime thật. FND-04 conformance samples không được tự chuyển thành AVAILABLE.

## Bốn trạng thái

| Status | Điều kiện |
|---|---|
| DISABLED | Feature flag tắt hoặc không được cấu hình |
| UNAVAILABLE | Sai target scope/quyền/context; chưa có runtime snapshot hợp lệ; hoặc ít nhất một required port không khả dụng |
| DEGRADED | Tất cả required ports khả dụng nhưng ít nhất một optional port không khả dụng |
| READY | Required và optional ports đều khả dụng theo current Core view |

Port khả dụng khi có **ít nhất một producer** được Core view cho phép, đúng scope/quyền và có dependency/ORDER khả thi. Missing capability entry là UNVERIFIED. Producer trực tiếp AVAILABLE nhưng dependency bị chặn là DEPENDENCY_UNAVAILABLE. Alternative producer được giữ, không dùng một witness bị chặn để kết luận cả port unavailable.

Tái sử dụng `dependency_witness(..., allow_partial=True)` trên tập Function đang đủ quyền/capability để lấy phần reachable. Mặc định helper vẫn strict như FND-03; build artifact và metadata digests không đổi. Không cache availability toàn cục giữa target; mỗi evaluate kiểm context/snapshot/TTL lại.

Kết quả có reason và required/optional port details; luôn `authorizes_execution:false`, `health_evaluated:false`. READY cho biết khả năng cung cấp dữ liệu theo advisory view, không là mạng khỏe, Fact, RCA, repair hoặc quyền thực thi. Core phải kiểm lại target/ACL/capability/preconditions/freshness/budget trước actual execution.

## API

```python
from gateway_pilot.features.registry import FeatureRegistry
from gateway_pilot.application.feature_availability import AvailabilityService

registry = FeatureRegistry(artifact, policy, manifests, trusted_flags)
service = AvailabilityService(registry)
report = service.evaluate(feature_id, context=current_target,
    permissions=current_permissions, policy_context_id=current_policy_identity,
    capabilities=core_snapshot)
```

Các biến current/core phải lấy từ server/Core, không user JSON. Nếu `core_snapshot=None`, enabled Feature đúng scope/quyền trả `UNAVAILABLE / RUNTIME_NOT_CONNECTED`. Bất kỳ FND-04 conformance dictionary nào cũng bị từ chối với INVALID_CAPABILITY_SNAPSHOT.

## CLI metadata preview

Sau khi build registry theo [Catalog guide](CATALOG_V02.md):

```bash
.venv-graph/bin/python -m scripts.features --registry runs/fnd-05/replay-registry.json
.venv-graph/bin/python -m scripts.features --registry runs/fnd-05/laptop-registry.json --policy config/catalog_policy.laptop.example.json --manifests examples/features.laptop.json --flags config/feature_flags.laptop.example.json
```

Preview dùng synthetic target/policy context để xem metadata; `runtime_connected:false`, không có option cấp/inject capabilities. Enabled entries mặc định UNAVAILABLE vì chưa nối FND-06, disabled entries vẫn DISABLED. CLI không đọc interface hoặc probe mạng.

[Báo cáo nghiệm thu](reports/FND05_FEATURE_REGISTRY_20261113.md) phân biệt tests dùng synthetic Core snapshots với trạng thái chưa nối runtime hiện tại.
