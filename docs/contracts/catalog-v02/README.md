# Function Contract v0.2 — FND-01

Schema document version **0.2.0**, thực hiện ngày 13/11/2026. Đây là chuẩn metadata và bộ kiểm tra cục bộ cho Function, Port và version selection. Không có registry loader/builder, backend binding hay quyền thực thi mới trong FND-01.

- [Schema máy đọc được](contract.schema.json): JSON Schema Draft 2020-12; chỉ có `$ref` nội bộ trong schema do repo quản lý.
- [Ví dụ hợp lệ](examples.json): laptop READ, port, exact selection và gateway multi-output. Tất cả là metadata minh họa; chưa có Linux Wi-Fi Function được đăng ký/chạy từ các ví dụ này.
- [Thiết kế Foundation](../../superpowers/specs/2026-11-13-command-catalog-v02-design.md).
- [Tests](../../../tests/catalog/test_contract_schema.py), [compatibility tests](../../../tests/catalog/test_contract_compatibility.py).

## Sử dụng

Từ repo root, sau setup môi trường và pinned upstream:

```bash
.venv-graph/bin/python -m unittest discover -s tests/catalog -v
```

API hiện có:

```python
from gateway_pilot.command_catalog.contracts import validate_contract

validate_contract(document)  # dict đã parse; trả None hoặc raise PlanError
```

`validate_contract` không thay đổi document, Registry, permissions hoặc capability. Đây là API kiểm tra dành cho phát triển; schema được đọc từ đường dẫn cố định trong repo. Không dùng trực tiếp cho HTTP input. JSON file parser strict (duplicate keys), cross-catalog resolution, registry build và schema packaging cho runtime thuộc các gate sau.

## Quy tắc định danh và reference

- `schema_version` luôn là `0.2.0`; `kind` là `function`, `port`, `selection`; FND-02 bổ sung `skill` theo cùng chuẩn metadata.
- Function/Port ID gồm ít nhất hai segment chữ thường, phân cách dấu chấm; mỗi segment bắt đầu bằng chữ, phần sau có chữ/số/underscore; tối đa 100 ký tự. Không có `@version` trong ID.
- Version là SemVer chính xác `major.minor.patch`, có thể có prerelease/build metadata đúng cú pháp. Không nhận `latest`, `v1.0.0`, range hoặc numeric component có leading zero. Prerelease version hợp lệ về metadata không tự được chọn để triển khai.
- `skill_refs` là danh sách `{skill_id, version}`. Skill mới dùng ID namespaced; `SKxx` được giữ cho migration. Một Function không tham chiếu hai version cùng Skill ID.
- `inputs`/`outputs` là map **port ID → exact version**; ví dụ `{"client.identity":"1.0.0"}`. Schema được tìm qua cặp này; không dùng URL/remote schema ref. Các cặp khác version không mặc nhiên tương thích.
- `selection.functions`/`selection.ports` là map ID → exact version, mỗi ID có một giá trị. Document parser FND-03 phải từ chối JSON key trùng trước khi thành dict.
- Port ID và Function ID thuộc namespace logic khác nhau, được phép trùng chuỗi. Không suy ý nghĩa hay quyền từ tên.

## Nội dung contract

Function bắt buộc khai báo identity, description/domain, skill refs, lifecycle, inputs/outputs, scope, risk/permission, arguments schema/sources, preconditions, order/effects, budget, probe/verifier và unknown policy. Chỉ `tags` là tùy chọn. Không chèn default ngầm.

Port bắt buộc có ID/version/scope, payload schema, provenance prefix và `untrusted_text`. Prefix có dạng `linux_client/` hoặc `synthetic_replay/v1/`, không có URL/traversal. Prefix mới chỉ là yêu cầu dữ liệu; binding/probe/Verifier vẫn phải xác minh nguồn thật. Runtime Core hiện dùng một prefix cho mỗi resolved Port; nhiều backend dùng chung contract cần namespace provenance thống nhất hoặc thiết kế riêng ở gate binding, không được xóa kiểm tra provenance để ghép.

Function một trách nhiệm có thể có nhiều output. Schema cho phép tối đa 64 inputs/outputs; Verifier hiện có vẫn đòi đúng tập output, không thiếu/trùng/foreign IDs.

Arguments schema là object đóng. Mỗi `argument_sources` có dạng `argument: [input_port_id, field.path]`; argument phải tồn tại trong schema, nguồn phải là input đã khai báo. Mọi argument required cần source. Optional argument chưa có source vẫn chỉ là metadata; Core/binding sau này phải quy định nguồn tin cậy, không mặc định nhận nó từ chat/HTTP. Field path kiểm tra cú pháp ở đây; sự tồn tại/type của field trong port thật kiểm tra ở FND-03.

`preconditions` chỉ tham chiếu input của Function; phép so sánh số không nhận boolean. `order_after` không chứa chính Function; kiểm tra tồn tại/version/cycle xuyên catalog ở FND-03. `effects` phải là output đã khai báo; READ_ONLY/PROBE không khai báo effects trong profile pilot này.

## Risk, lifecycle và quyền

- Vocabulary risk: `READ_ONLY`, `PROBE`, `WRITE`. Không nhận legacy `READ` trực tiếp trong contract v0.2.
- Allowlist permission ban đầu: `network.read`, `system.read`, `network.write`. READ_ONLY/PROBE dùng permission READ; WRITE phải dùng `network.write`. Không thêm `system.write` hoặc arbitrary permissions qua manifest.
- WRITE chỉ được mô tả ở đây và buộc `retry.max_attempts=1`. PROBE/WRITE không được nạp executable trong pilot READ của FND-06. Schema hợp lệ không cho phép gọi tool.
- Lifecycle: `PROPOSED`, `IMPLEMENTED`, `VERIFIED`, `DEPRECATED`, `RETIRED`. Tách khỏi availability theo target; VERIFIED không tương đương `PROBE_OK`/`PROBED_OK`.
- Không nhận `status`, capability results, adapter/module path, source code, shell command hay `verified_on_hardware` trong contract. Approval, attestation, backend binding và consent nằm ngoài contract.
- Verifier hiện chỉ chấp nhận `schema_scope_provenance_freshness/v3`; `on_unknown` cố định `BLOCK_AND_REQUEST_EVIDENCE`.
- `capability_probe` là ID namespaced. Tên hợp cú pháp không chứng minh có implementation; đối chiếu trusted implementation/allowlist ở FND-03/04.

## Payload schema và các giới hạn

Payload/arguments root là object đóng: `type`, `properties`, `required`, `additionalProperties:false`. Nested schema dùng subset hiện có của Core: `type`, `title`, `description`, `properties`, `required`, `additionalProperties` (boolean), `enum`, `const`, `minimum`, `maximum`, `minLength`, `maxLength`, `items`, `minItems`, `maxItems`, `format`. Không có `$ref`, `$defs`, combinator, pattern hoặc remote resolution trong schema nhúng.

Mỗi object khai báo properties/required/additionalProperties; required phải tồn tại. Property/argument name là identifier đơn, field path dùng dấu chấm riêng. Array phải có item schema và maxItems. Range đảo và enum/const sai type/range/format bị từ chối. Format allowlist: `ipv4`, `ipv6`, `hostname`, `date-time`. Việc schema được nhận chưa chứng minh mọi quan hệ producer/consumer tương thích; FND-03 vẫn dùng kiểm chứng subset của Core.

| Giới hạn | Giá trị |
|---|---|
| Document Function/Port | 65.536 byte UTF-8 sau serialize kiểm tra |
| Selection document | 1.048.576 byte; tối đa 10.000 IDs mỗi map |
| Cây Python JSON đầu vào | Depth tối đa 20, 50.000 nodes kể cả keys, 1.048.576 ký tự tổng trước serialize |
| IDs / version / field path | 100 / 128 / 128 ký tự |
| Property name / domain | 64 ký tự |
| Description/title | 1–2.048 ký tự, phải có ký tự không phải whitespace |
| Inputs, outputs, properties, preconditions, order/effects | Tối đa 64 phần tử mỗi tập; outputs ít nhất 1 |
| Skill refs / tags | Tối đa 32; skill refs ít nhất 1 |
| Timeout | Số nguyên 1–60.000 ms |
| Retry | `max_attempts` số nguyên 1–4; WRITE luôn 1 |
| TTL | Hữu hạn, >0 và ≤86.400 giây |
| Cost / estimated latency | 0–1.000.000 / 0–60.000 ms, hữu hạn |
| Payload string bound / array bound | maxLength ≤65.536 / maxItems ≤1.024 |
| Enum | 1–64 giá trị, không trùng |

Đây là giới hạn metadata/schema profile pilot, không phải bộ đếm runtime hay lời hứa deadline end-to-end. Timeout transport, output byte cap và resource budget vẫn cần implementation/test ở adapter/Core. JSON Schema hiểu số nguyên theo giá trị (ví dụ `1.0` là integer); boolean không phải số. API từ chối NaN/Infinity, non-JSON Python types, keys không phải string, Unicode không encode được và dữ liệu vượt giới hạn trước validation tiếp theo.

## Ánh xạ sang Core và tương thích

Bảng này là hợp đồng bridge cho FND-06; FND-01 chưa viết mapper hoặc nạp v0.2 vào runtime.

| Contract v0.2 | Kiểu/trường Core đích | Quy tắc |
|---|---|---|
| function_id/version | `Function.id/version` | Exact selected version, không chọn lại khi call |
| skill_refs | `Function.skills` | Resolve exact version ở registry; Core dùng tuple IDs |
| inputs/outputs | `dict[str, Port]` | Resolve version/scope/schema/provenance trước compile |
| arguments_schema/sources | `arguments_schema`, `argument_sources` | Deep copy; nguồn facts đúng schema; list pair thành tuple |
| scope/permission | `scope`, `permission` | Không suy từ tên ID |
| risk | Explicit v0.2 policy | Không đổi thành legacy READ để đi vòng gate |
| preconditions/order_after/effects | `Predicate`, order/effects metadata | Giữ DATA/STATE/ORDER; effects không phải quyền WRITE |
| retry.max_attempts | `Function.retry_limit` | `max_attempts - 1`; giá trị 1 nghĩa là không retry |
| timeout_ms/cost/latency_ms | Các trường cùng tên | Giữ đơn vị, không override policy budget |
| ttl_seconds/verifier/on_unknown | TTL metadata/verifier/unknown policy | Không phụ thuộc ngầm TTL legacy; v0.2 bridge cần model rõ |
| lifecycle/capability_probe | Metadata và trusted capability gate | Không tự tạo runtime availability/status |
| domain/tags | Discovery index bên ngoài runtime Function | Không chèn vào digest v0.1 |

`Function.digest()` hiện hash cả đối tượng. FND-01 không đổi thuật toán hoặc lớp runtime hiện có. [Golden vector](../../../tests/catalog/fixtures/v01_contract_digests.json) được ghi trước implementation từ commit `3fd196f`: hash registry nguồn và toàn bộ 17 Function digests. Compatibility tests so trực tiếp với golden, đồng thời xác nhận đổi version/timeout sau compile bị Runner chặn trước khi nhận evidence.

Catalog/source/artifact digest là khái niệm riêng, chưa tạo ở gate này. Không dùng chúng thay runtime contract digest; không nâng evidence của version cũ sang version mới. Checkpoint/journal compatibility v0.2 thực tế được kiểm chứng khi có bridge FND-06.

## Kết quả và ranh giới nghiệm thu

FND-01 hoàn tất khi schema self-check, positive/negative vectors, compatibility digests và full regression qua môi trường chuẩn đều đạt. Các hợp đồng ví dụ không phải executable commands và không phải bộ catalog đã resolve.

Tiếp theo FND-02 chuyển tập READ nhỏ theo domain; FND-03 xử lý parser, dangling references, scope/type xuyên document, duplicate ID/version, dependency DAG, registry build và index. FND-04/06 bổ sung binding/capability/policy và runtime bridge. Không mở WRITE hay truy cập router để hoàn thành FND-01.

## Bổ sung FND-02: Skill metadata và catalog seed

[Catalog theo domain](../../../catalog/README.md) là tập READ seed độc lập với ví dụ FND-01. Kind `skill` có ID/version, name/description, `requires`, `produces`, `completion_ports` (port ID → exact version), `function_refs` (Function ID → exact version) và optional tags. Tối đa 64 refs mỗi map, produces/function_refs không rỗng; name 1–120 ký tự. Completion ports phải có cùng ID/version trong produces.

Skill không có permission, status, capability hoặc executable source. `validate_contract` kiểm shape và reference cục bộ của completion ports; seed tests kiểm tham chiếu xuyên các file đã đưa vào repo. Generic resolution/cycle validation và registry builder vẫn ở FND-03.

## Bổ sung FND-03: Catalog tooling

[Validator/Builder và CLI](../../CATALOG_V02.md) đã triển khai strict parsing, cross-reference/schema/scope/dependency checks, exact selection, deterministic artifact và verified metadata read. API `validate_contract` ở tài liệu này vẫn chỉ kiểm từng document. File build policy chứa probe-name vocabulary, không cấp capability. Profile build hiện READ_ONLY, scope-local, chưa có workflow/binding/runtime bridge. [Nghiệm thu](../../reports/FND03_CATALOG_BUILDER_20261113.md).
