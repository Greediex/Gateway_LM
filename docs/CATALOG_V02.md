# Catalog v0.2 — Validator, Builder và CLI (FND-03)

FND-03 xử lý **READ metadata**, không khởi tạo `GraphRegistry`, không nạp adapter và không cấp capability. [Contract v0.2](contracts/catalog-v02/README.md) và [seed catalog](../catalog/README.md) là đầu vào.

## CLI dành cho developer/operator

Chạy từ repo root với môi trường Python 3.12 đã thiết lập:

```bash
.venv-graph/bin/python -m scripts.catalog validate --source catalog
.venv-graph/bin/python -m scripts.catalog validate --source catalog --selection config/catalog_selection.example.json
.venv-graph/bin/python -m scripts.catalog build --source catalog --selection config/catalog_selection.example.json --output runs/catalog-v02/registry.json
.venv-graph/bin/python -m scripts.catalog report --registry runs/catalog-v02/registry.json
```

Cả ba lệnh nhận `--policy /trusted/path/policy.json`; mặc định là [policy mẫu](../config/catalog_policy.example.json) trong repo. Đây là vocabulary probe IDs từ cấu hình operator, **không** là attestation/approval hay implementation registry. Tên có trong danh sách chỉ chứng minh reference được phép khai báo. Binding và probe thực ở FND-04; runtime policy ở FND-06.

Exit code 0 khi thành công; 2 khi CLI gặp lỗi validation/I/O. Kết quả là JSON; lỗi đi qua stderr, không xuất traceback/payload vào giao diện bình thường. `report` chỉ đọc artifact sau khi kiểm tra lại integrity, policy/schema version, refs và indexes. Báo cáo luôn ghi `execution_enabled:false`, `binding_count:0`, `target_verified_executable_count:0`.

Không truyền path, policy, selection hay output từ LLM/HTTP cho các API này. Chúng dành cho cấu hình local tin cậy, chưa có remote catalog installation.

## Source layout và strict parsing

Loader chỉ nhận:

```text
catalog/
  functions/<domain>/<function_id>.json
  functions/<domain>/<function_id>@<version>.json
  ports/<port_id>.json
  ports/<port_id>@<version>.json
  skills/<skill_id>.json
  skills/<skill_id>@<version>.json
```

Tên flat của FND-02 vẫn hợp lệ; khi giữ nhiều version cùng ID, dùng filename có `@version`. Không được có hai file khai báo cùng `(kind, ID, version)`, kể cả flat và versioned. Function domain phải khớp thư mục. `kind` phải khớp nhóm thư mục; schema bên trong vẫn là version `0.2.0`.

JSON bị từ chối khi có duplicate keys ở bất kỳ cấp nào, NaN/Infinity hoặc exponent tràn float, UTF-8/syntax lỗi, root không phải object hoặc vượt giới hạn. File/directory symlink trong source bị từ chối; lỗi duyệt thư mục không bị bỏ qua. Non-JSON docs được bỏ qua, không được import hoặc chạy. Workflow/binding JSON chưa có schema nên hiện bị từ chối khi đặt vào source; không âm thầm bỏ qua metadata không hiểu.

| Giới hạn | Giá trị |
|---|---|
| Source contract file | Tối đa 65.536 byte raw; sau parse vẫn qua giới hạn FND-01 |
| Policy / selection file | Tối đa 1 MiB |
| Tổng source JSON / artifact | Tối đa 32 MiB mỗi loại |
| Source JSON files / directory count | Tối đa 20.000 |
| Depth source directory | Tối đa hai cấp thư mục dưới root, ví dụ `functions/wifi` |
| Tổng document khi validate | Tối đa 20.000; mỗi nhóm Function/Port/Skill không rỗng |
| Tổng reference maps/lists được đếm | Tối đa 100.000: Function inputs/outputs/skill_refs/order_after, Skill requires/produces/function_refs |
| Probe-name vocabulary | 1–10.000 ID duy nhất đúng cú pháp |

Không có schema resolution qua network. Schema/size/depth/finite checks cục bộ được dùng lại từ FND-01.

## Validation chéo và selected context

`validate` kiểm toàn bộ versions trong source:

- ID/version duy nhất; exact refs tới Port/Skill/Function tồn tại.
- Profile hiện chỉ nhận `READ_ONLY`; không nhận PROBE/WRITE vào catalog build này dù schema standalone có thể mô tả chúng.
- Input/output Port scope phải trùng Function scope trong profile FND-03. Cross-scope calls cần target/context contract rõ trước khi mở rộng profile; Core legacy hỗ trợ một số context riêng và không bị thay đổi ở đây.
- Argument source field path tồn tại; required argument cần field required xuyên mọi cấp object; source schema chứng minh được là subset của argument schema. Bổ sung format check vì structural subset của Core không đủ chứng minh unrestricted string là IPv4/date-time.
- Numeric predicates chỉ so sánh numeric fields; equality value phù hợp field schema; ORDER references tồn tại.
- Skill membership phải có reference chính xác hai chiều. `requires` được member Function tiêu thụ, `produces` có member producer; completion ports khớp produces cả ID/version.
- Mỗi input có producer cùng exact Port version trong tập đang kiểm tra. Profile hiện là catalog đóng, chưa hỗ trợ input external facts không có producer declaration.

Khi `--selection` được cung cấp, hoặc khi build, validator kiểm thêm:

- Một version chính xác mỗi Function/Port ID, không range/latest/fallback.
- Skill versions được pin qua Function references; không chọn hai version một Skill ID.
- Phải chọn đủ ports, Skill members và dependency Functions. Builder không tự thêm Function hoặc trim một immutable Skill để làm selection pass.
- Không chọn Function DEPRECATED/RETIRED trong pilot này. Lifecycle VERIFIED vẫn không cấp capability.

Metadata source snapshot có record digests lúc load; sửa records trong RAM sau load bị build từ chối. Muốn sửa catalog, cập nhật file rồi load lại.

## Dependency witness và indexes

Input ports là điều kiện AND; các producer cho cùng exact port là lựa chọn OR; ORDER references là điều kiện AND. Thuật toán dùng hàng đợi/heap và event availability, không DFS đệ quy. Function không có input/ORDER tạo điểm bắt đầu; khi một producer khả thi tạo port, các consumer có thể đủ điều kiện. Không có điểm bắt đầu cho một nhóm cycle thì từ chối.

Không gộp tất cả producer alternatives thành hard edges: graph union có vòng vẫn có thể có một producer gốc giúp lập lịch. Tests có trường hợp root identity và refresh identity dựa trên IPv4 để bảo vệ semantics này. Với nhiều Function versions trong source, ORDER reference được kiểm trên ID; selected context được kiểm lại sau khi pin một version/ID, nên alternative ở version không chọn không thể cứu một selection sai.

Artifact indexes gồm `by_domain`, `by_skill`, `producers`, `consumers`, `dependencies`, `witness_order`. `dependencies` là một witness xác định, không phải toàn bộ kế hoạch runtime hoặc toàn bộ producer alternatives. `producers` vẫn giữ các alternatives để bước runtime sau này quyết định qua policy.

`discover(indexes, domain=..., skill=..., limit=10)` trả metadata candidates với limit 1–1.000. `dependency_closure(indexes, function_ids)` giữ witness dependencies **qua domain**, tối đa 10.000 đầu vào. Các API này chưa áp ACL/capability runtime và không thay thế Planner. Một lịch metadata khả thi không chứng minh preconditions/facts thực tế sẽ đạt hoặc phép đo thành công.

## Artifact và publication

Một artifact JSON tự chứa:

- Format `gateway-lm.catalog-registry`, schema `0.2.0`, `execution_enabled:false`.
- Exact selection, selected Functions/Ports/Skills được sort ổn định.
- Indexes/witness có thể tái tính và đối chiếu khi đọc.
- Manifest: builder version, schema/policy/selection digests, raw source-file hashes, canonical record digests và số lượng source contracts theo nhóm.
- `content_digest`: SHA-256 của canonical artifact bỏ riêng trường content_digest.

Canonical bytes dùng UTF-8, sorted object keys, separators cố định và newline cuối; không có timestamp, absolute source path hoặc random ID. Hai lần build từ cùng snapshot/selection/policy/schema/builder cho byte giống nhau, kể cả thứ tự đọc các document khác nhau. Source JSON format thay đổi sẽ đổi raw source hash, do đó artifact có thể đổi dù object tương đương.

Manifest/content hashes là **integrity checks, không phải chữ ký hay chứng minh operator đã phê duyệt**. Người có quyền sửa file có thể tính lại hash. FND-06 phải lấy path/digest/policy từ startup configuration tin cậy trước khi có runtime integration; không nhận artifact từ chat/HTTP.

Builder validate toàn bộ trước publish, ghi temp cùng filesystem, flush/fsync file rồi `os.replace`. Validation hoặc replace lỗi giữ nguyên artifact cũ và dọn temp. Manifest/index/records cùng một file nên không có bộ sidecar cập nhật dở. Đây là atomic publication cho READ metadata, không phải durable job journal hoặc cam kết chống mọi kiểu mất điện.

FND-03 chặn output trong source catalog, `data/` và `benchmarks/` để bảo vệ baseline. Developer output nên ở `runs/`. Nếu muốn lưu release artifact trong `data/registry_v02.json`, đó là bước publication được review riêng sau này, không ghi đè bằng CLI hiện tại. Không tạo registry_v02 file trong dữ liệu v0.1.

## Python APIs

```python
from gateway_pilot.command_catalog.loader import load_catalog, read_json
from gateway_pilot.command_catalog.validator import validate_catalog
from gateway_pilot.command_catalog.builder import build_registry, read_registry, report_registry

catalog = load_catalog("catalog")
policy = read_json("config/catalog_policy.example.json", max_bytes=1048576)
selection = read_json("config/catalog_selection.example.json", max_bytes=1048576)
validate_catalog(catalog, policy)
artifact = build_registry(catalog, selection, policy, "runs/catalog-v02/registry.json")
verified_metadata = read_registry("runs/catalog-v02/registry.json", policy)
summary = report_registry(verified_metadata)
```

Không dùng object artifact này như GraphRegistry. API `report_registry` chỉ nhận object đã qua `read_registry` hoặc `build_registry`; CLI luôn đi qua kiểm tra artifact. Registry-to-runtime bridge, adapter conformance, Feature Registry và execution eligibility vẫn theo FND-04/05/06.

## Benchmark synthetic

```bash
.venv-graph/bin/python -m scripts.analysis.benchmark_catalog --output runs/catalog-v02/scale.json
```

Mặc định 10/100/1.000 Functions, mỗi Function có một Port và một Skill để giữ contract reference limits. Chain dependency qua hai domain; subprocess mới cho mỗi size. Benchmark chạy Linux/macOS để lấy peak RSS bằng `resource.getrusage`; CLI catalog không phụ thuộc module này và vẫn dùng được trên Windows.

Đo source load, validate, build (gồm validation lặp và publication), verified read, bytes artifact và peak RSS. Discovery/closure đo 25 samples trong cùng process; OS/disk cache không được flush. Runtime compile và on-device CPU/NPU **không đo**. Dữ liệu là synthetic metadata, không phải 1.000 lệnh thực hoặc benchmark embedding độc lập.

Budget chốt trước lần chạy: validate/read ≤30 giây mỗi size, build ≤60 giây, peak RSS ≤512 MiB, closure p95 ≤100 ms; worker timeout 180 giây. Budget này chỉ là gate phát triển trên host, chưa phải SLA router. Report chứa host/Python, protocol `catalog-scale/v1`, số liệu và budgets_met; command exit 1 nếu vượt budget. Worker fail bất thường không được báo thành công.

## Bổ sung FND-04

[Trusted binding và conformance](ADAPTER_BINDINGS_V02.md) dùng declarations riêng, pin artifact digest để tránh circular hash, approval pins từ trusted startup và backend objects từ Python. Public `verify_registry(artifact, policy)` expose helper integrity cũ, không đổi format/digest. Catalog report vẫn metadata-only/binding_count=0 vì bindings không được auto-nạp vào runtime. [Catalog laptop riêng](../examples/catalog_laptop/README.md) giữ provenance live khác replay; FND-06 tiếp tục bridge.
