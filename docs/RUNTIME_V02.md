# Catalog v0.2 → Core READ runtime — FND-06

FND-06 nối selected catalog metadata vào Compiler, GraphRunner, InvocationExecutor và EvidenceVerifier hiện có. `GraphRunner` không đổi và không có nhánh theo Function ID. [Thiết kế Foundation](superpowers/specs/2026-11-13-command-catalog-v02-design.md), [plan](superpowers/plans/2026-11-13-fnd-06-runtime-migration.md).

## Composition root tin cậy

API trong [compatibility.py](../gateway_pilot/command_catalog/compatibility.py) và [runtime.py](../gateway_pilot/command_catalog/runtime.py):

```python
from gateway_pilot.command_catalog.compatibility import load_runtime_registry
from gateway_pilot.command_catalog.runtime import ReadRuntime

# Tất cả tham số dưới đây đến từ operator startup đã review, không từ request.
registry = load_runtime_registry(
    trusted_artifact_path, contract_format="v0.2", policy=trusted_catalog_policy,
    approved_digest=operator_approved_registry_digest,
)
# registry ở đây chưa có runtime/capabilities; không thể chạy chỉ nhờ load metadata.
runtime = ReadRuntime(
    artifact, trusted_catalog_policy,
    approved_digest=operator_approved_registry_digest,
    selection=trusted_binding_selection, context=trusted_target_context,
    permissions=effective_permissions, policy_context_id=principal_acl_revision_digest,
)
support_snapshot = runtime.probe()
runner, plan = runtime.execute(["client.ipv4"])
verified_ipv4 = runner.state.fact("client.ipv4")
```

`artifact` đọc bằng `command_catalog.builder.read_registry`; `BindingSelection` tạo theo [trusted binding guide](ADAPTER_BINDINGS_V02.md). Approved catalog digest và binding digests phải có từ operator review. Tính lại hash của dữ liệu không tự tạo approval. Không có API upload catalog/binding/snapshot, dynamic import hoặc LLM-provided backend. Muốn thay principal, ACL revision, registry, target hay environment thì tạo composition root mới; không sửa configuration giữa chừng.

`load_runtime_registry` dispatch tường minh `v0.1` hoặc `v0.2`, format khác raise `PlanError`. v0.1 dùng loader cũ; v0.2 verify artifact đầy đủ và exact approved content digest. Không fallback khi parse/validate thất bại.

## Migration và policy

- Compile READ_ONLY và lifecycle IMPLEMENTED/VERIFIED; PROPOSED/DEPRECATED/RETIRED, PROBE/WRITE hoặc risk lạ không executable. Builder vẫn quản lý metadata riêng.
- Ba replay seed Functions và hai Linux Functions chuyển PROPOSED → IMPLEMENTED vì đã có provider đã review. Không dùng lifecycle VERIFIED để ám chỉ nghiệm thu mọi thiết bị. [Replay declarations](../examples/binding_selection.replay.json) cập nhật exact pins theo artifact mới. v0.1/data/benchmarks không đổi.
- `CompatibilityView` expose selected Skills/Functions, typed requires/produces và TTL cho API còn cần `registry.legacy`; risk vẫn READ_ONLY. Không tạo workflows, claims, fact assertions hoặc requirement counts giả.
- Mapping giữ exact Function/Port versions, schema, provenance, scope, permission, predicates/ORDER, arguments, timeout, TTL và `retry_limit=max_attempts-1`. Core duplicate/call/cost/deadline limits vẫn có thể chặn sớm hơn retry ceiling.
- FunctionV02 digest gồm contract fields, metadata digest, exact Port versions và selected registry digest. Metadata catalog digest, metadata Function digest và runtime Function digest là ba binding khác nhau. FunctionV01 và thuật toán digest cũ giữ nguyên.

## Support, availability và evidence

`ReadRuntime.probe()` gọi implementation `supports(fid, context)` của backend đã bind/approve. Kiểm return bool, backend revision/source/probe pins và elapsed deadline; lease 30 giây gắn runtime context/effective ACL. Chưa probe là UNVERIFIED; thiếu quyền là PERMISSION_DENIED, backend trả false là UNSUPPORTED, lỗi/timeout là TEMPORARILY_UNAVAILABLE. Probe không sample và không admit facts; kết quả conformance FND-04 không được dùng để tạo lease.

Snapshot typed sinh từ Core có thể đưa vào `AvailabilityService.evaluate`. READY chỉ có nghĩa data requirements có producer hiện hỗ trợ và đúng quyền/dependency; không có nghĩa mạng khỏe hay evidence đã thu. Metadata CLI `scripts.features` vẫn không nối runtime và không cấp capabilities; preview đó tiếp tục UNAVAILABLE.

Execution đi qua `execute_ready_once → GraphRunner.step → InvocationExecutor → runtime adapter → EvidenceVerifier`. Trước/sau sample kiểm scope/target/environment, permissions, lease, supports và immutable binding pins. Result phải đủ exact outputs, đúng schema/version/metadata digest/source, timestamp/freshness và timeout; lỗi không admit evidence. Adapter không nhận arbitrary arguments từ chat; arguments do Runner lấy qua verified input bindings. Thiếu adapter v0.2 bị chặn, không chuyển sang `world`/legacy replay.

Backend phải tự bound blocking I/O. Elapsed check loại late results, không preempt Python/kernel syscall đang kẹt. Linux provider chỉ đọc identity/IPv4 bằng kernel APIs, không shell/network; chưa RSSI dBm. Boot/netns/interface incarnation pin không thay thế route/IP-change monitoring của FND-07.

CaseState v0.2 đòi runtime digest, Function version, metadata digest, environment và TTL đúng contract trước khi dùng observation. Tuổi dữ liệu từ timestamp được giữ khi Core đóng dấu monotonic receipt time; không làm mới observation cũ bằng receipt time. Claim evaluation vẫn là bước riêng, không kết luận từ READY hay tool success.

## Checkpoint và rollback compatibility

Checkpoint v0.2 giữ runtime/metadata/version/environment bindings và ký HMAC như cơ chế cũ. Fingerprint bao gồm runtime contracts/Ports; additional binding pin registry, approved bindings, principal/ACL identity và environment. Khác contract, selected registry, principal, target, environment hoặc ACL trả 0 restored; không relabel evidence sang version mới. Validate pending v0.2 records trên candidate state trước khi mutate state thật.

Shape/body và digests v0.1 không đổi. Checkpoint vẫn chỉ là trusted local READ fact cache, không cấp capabilities, không job resume/WRITE.

## Reproduce

```bash
.venv-graph/bin/python -m unittest tests.catalog.test_runtime_v02 -v
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m unittest discover -s tests -v
```

Focused tests chạy replay thật qua Core, negative gates, generic renamed Function + backend multi-output không sửa Runner, Feature availability và checkpoint same/changed registry. Laptop acceptance chỉ identity/IPv4, chưa Connectivity/Wi-Fi verified snapshot/UI FND-07. [Báo cáo local](reports/FND06_RUNTIME_MIGRATION_20261113.md).
