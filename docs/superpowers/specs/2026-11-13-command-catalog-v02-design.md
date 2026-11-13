# Gateway LM v2 — Foundation: Versioned Function Catalog

**Trạng thái:** FND-01 đã triển khai theo yêu cầu trực tiếp ngày 13/11/2026; [chuẩn schema 0.2.0 và mapping](../../contracts/catalog-v02/README.md) là tài liệu chi tiết cho gate này. FND-02 đến FND-06 đã triển khai theo yêu cầu tiếp nối; [runtime READ v0.2](../../RUNTIME_V02.md) pin catalog/bindings và dùng Core hiện có. [FND-07 laptop snapshot/UI](../../LAPTOP_NETWORK_V2.md) đã triển khai qua trusted Core; router acceptance tiếp tục là giai đoạn sau. **Ngày:** 13/11/2026. **Checkout đối chiếu:** `3fd196f`, nhánh `refactor/gateway-lm-composite-adapter-pr01`.

**Yêu cầu mới:** Xây nền quản lý hàng trăm/hàng nghìn Function trước khi tiếp tục mở rộng tính năng. Nguồn người dùng: `/home/nangtuan/.codex/attachments/04a396f1-4c76-498a-afde-1caae47917b9/Pasted text.txt`.

**Mục tiêu:** Thêm Function và backend qua contract/binding/test; giữ GraphRunner dùng chung. Sau Foundation, dùng Wi-Fi laptop Linux làm ca kiểm chứng đầu tiên, rồi mới OpenWrt. Tạm giữ phạm vi tính năng mới; sửa lỗi và kiểm thử thiết yếu vẫn tiếp tục.

## 1. Lựa chọn kiến trúc

| Phương án | Lợi ích | Chi phí / giới hạn |
|---|---|---|
| Chia JSON v0.1 rồi ghép nguyên dạng | Ít thay đổi ban đầu | Vẫn phụ thuộc catalog baseline, chưa tách lifecycle/binding hay version selection |
| **Catalog v0.2 → validator/builder → registry snapshot → Core hiện có** | Review theo domain, kiểm tra trước runtime, migration có kiểm soát | Cần loader mới, compatibility view và kiểm tra policy một lần |
| Thay Core bằng nền tảng plugin/service mới | Nhiều tự do thiết kế | Mất lợi thế kiểm chứng hiện có, tăng vận hành và rủi ro migration |

Đề xuất phương án thứ hai. Catalog là metadata tin cậy; không có dynamic plugin Python/shell. Không tạo hàng nghìn Function chỉ để đạt số lượng.

## 2. Từ vựng và quan hệ

- **Feature:** khả năng người dùng nhìn thấy, tham chiếu nhu cầu dữ liệu/goal.
- **Workflow:** quy trình/goal và các claim cần đánh giá cho một nhu cầu; không bắt buộc mọi yêu cầu phải có workflow cố định.
- **Skill:** nhóm năng lực nghiệp vụ, liên hệ nhiều Function và các port cần/sinh ra.
- **Function:** phép đo/thao tác có contract; có thể phục vụ nhiều Skill/Feature.
- **Port:** loại dữ liệu có schema, scope, version và chính sách provenance; không phải câu lệnh thực thi.
- **Binding:** triển khai một Function version trên backend cụ thể với normalization đã review.
- **Catalog:** nguồn khai báo theo domain, có thể chứa nhiều version/lifecycle và binding ứng viên.
- **Registry snapshot:** tập contract/version đã chọn, được validate và cố định cho một runtime context.
- **Capability attestation:** bằng chứng backend/thiết bị thực sự hỗ trợ binding trong ngữ cảnh xác định; tách khỏi lifecycle trong catalog.

Function ID và port ID là hai namespace khác nhau dù v0.1 có tên trùng nhau, ví dụ `wan.status`. Một Function có thể có nhiều output; vẫn giữ kiểm tra exact output set của ToolResult. Function một trách nhiệm không đồng nghĩa chỉ một output.

Laptop connectivity không tương đương WAN router: khác scope/ý nghĩa thì dùng contract khác. Backend khác chỉ dùng chung Function khi cùng ngữ nghĩa input/output, target và bằng chứng.

## 3. Phát hiện từ mã nguồn đang sở hữu hành vi

| Mã hiện tại | Điều đã có | Điều phải làm cho v0.2 |
|---|---|---|
| `graph_v3/contracts.py`: `Function`, `Port`, `Function.digest()` | Version, args schema, typed inputs/outputs, timeout/retry, digest | Tái sử dụng mô hình; không thay digest v0.1 trong migration |
| `registry_v01.py`: `load_registry` | Validate schema/reference, FunctionV01 và replay view | Loader v0.2 độc lập; v0.1 gắn với 22 skills, 101 workflows và 270 requirements cố định |
| `extension_loader.py`: `install_extension` | Overlay transactional, metadata READ | Hiện chỉ gateway, zero-input/single-output, provenance Ubus; không phù hợp nguyên trạng cho laptop client |
| `planner.py`: `Invocation` | Function ID và contract digest; chưa có trường version riêng | Version được khóa qua runtime Function và digest; thêm version vào export/audit nếu cần, không tự chọn version lúc call |
| `runner.py`: `ready` | Tra registry theo ID, từ chối contract đổi sau compile | Chỉ một selected version/ID trong registry là cách tương thích ban đầu |
| `verification.py` | Ghi contract digest vào evidence, validate output set | Dùng digest runtime thật; không dùng catalog hash thay contract digest |
| `graphs.py`: `contract_allowed`; `state.py`: `allowed` | Gate đặc thù v0.1; nhánh khác dùng risk `READ`, cần legacy view | Hỗ trợ v0.2 tường minh, fail closed cho format lạ và risk chưa hỗ trợ; không tận dụng nhánh legacy để đi vòng gate |
| `adapters/composite.py` | Mỗi ID gán đúng một backend, probe lại | Binding theo context tin cậy; không fallback tự động sang replay/backend khác |

Bất biến “thêm Function không sửa GraphRunner” áp dụng sau khi có hỗ trợ format v0.2 chung. Có thể cần chỉnh hạ tầng registry/policy/compatibility một lần; không thêm nhánh theo ID của từng Function trong Core.

## 4. Contract v0.2: định danh và trường dữ liệu

Phân biệt **schema version** của catalog/registry (đề xuất `0.2.0`) và **contract version** của mỗi Function/Port (SemVer). Không đặt mọi Function thành version 2 chỉ vì nền tảng gọi Gateway LM v2.

Quy ước ID mới đề xuất: chữ thường, phân đoạn bằng dấu chấm, pattern `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$`, tối đa 100 ký tự. ID cũ giữ nguyên trong compatibility; Skill/Workflow lịch sử `SKxx`/`WF-xxx` không bị đổi tên. Namespace mới không tự mang quyền.

| Nhóm | Trường bắt buộc / ý nghĩa |
|---|---|
| Identity | `function_id`, `version`, `description`, `domain`, `skill_refs` (ID + exact version) |
| Typed data | `inputs`, `outputs`: ánh xạ port ID → exact port version/schema ref; output không rỗng |
| Arguments | `arguments_schema` là object schema đóng, `argument_sources` từ input facts; không nhúng command |
| Target/policy | `scope` (`gateway`/`client`), `permission` từ allowlist Core, `risk` (`READ_ONLY`/`PROBE`/`WRITE`) |
| Preconditions/effects | `preconditions`, `order_after`, `effects` tường minh, tham chiếu tồn tại |
| Budget | `timeout_ms` hữu hạn và >0, `retry.max_attempts` số nguyên ≥1, cost/latency hữu hạn ≥0 |
| Evidence | Verifier ID được Core biết, TTL hữu hạn >0, quy tắc scope/target/provenance/freshness và `on_unknown=BLOCK_AND_REQUEST_EVIDENCE` |
| Capability | `capability_probe` là ID từ cấu hình/implementation tin cậy; không phải code, không phải probe result |
| Discovery | `tags`, mô tả nhu cầu và aliases tùy chọn; không tạo quyền hay tự mở target |

Port contract gồm ID/version/schema, scope, provenance policy và `untrusted_text`; phân biệt payload schema với metadata envelope. Builder kiểm schema thuộc subset mà Core có thể chứng minh compatibility; schema JSON hợp lệ nhưng nằm ngoài subset đó không mặc nhiên dùng làm producer thay thế được.

Retry: `max_attempts=1` nghĩa là không retry; bridge sang `Function.retry_limit = max_attempts - 1`. Trong pilot v0.2 READ, chỉ chọn contract READ_ONLY. PROBE/WRITE có thể nằm ở catalog để thiết kế nhưng không trở thành executable vì catalog có khai báo; PROBE cần policy riêng, WRITE vẫn ngoài Agent/Web và tắt mặc định.

**FND-01 đã cụ thể hóa:** dùng [schema và test vectors](../../contracts/catalog-v02/README.md) với field names, ranges/size limits và mapping chi tiết. Bảng ở đây mô tả kiến trúc; schema 0.2.0 là chuẩn kiểm tra cho FND-01. JSON minh họa trong tài liệu ban đầu không được đưa trực tiếp vào v0.1.

## 5. Version, snapshot và digest

1. Catalog cho phép nhiều `(function_id, version)`; trùng cặp bị từ chối. Port, Skill và Workflow cũng cần version/ref rõ trong phần dùng để build.
2. Deployment selection pin chính xác một version mỗi ID và port trong một registry snapshot. Không dùng “latest”, không chọn theo LLM. Nếu cần đồng thời hai major version trong một runtime, phải có thiết kế bổ sung trước; chưa hỗ trợ trong mốc đầu.
3. Binding tham chiếu đúng version/digest. Phiên bản không tương thích bị từ chối trước compile.
4. Snapshot tạo runtime Function cố định và `Function.digest()` như cơ chế Core. Không thay thuật toán hash của v0.1; so sánh migration bằng vector digest trước/sau.
5. Build manifest có source digests và registry artifact digest riêng. Chúng kiểm tra tính toàn vẹn của catalog/build, không thay thế digest của runtime contract.
6. `Function.digest()` hiện hash toàn bộ trường của đối tượng. Vì vậy mô tả/metadata được đưa vào Function cũng có thể đổi digest; tags/retrieval metadata mới nên giữ bên ngoài runtime Function. Nếu muốn đổi thuật toán digest, phải version hóa riêng và xử lý checkpoints/journals/plans cũ.
7. Evidence cũ chỉ dùng khi qua policy scope/target/TTL và contract binding hiện có; evidence không được gắn nhãn lại để dùng cho contract khác. Test riêng contract change sau compile và checkpoint resume với snapshot khác.

## 6. Lifecycle và khả dụng theo target

Lifecycle thiết kế: `PROPOSED → IMPLEMENTED → VERIFIED → DEPRECATED → RETIRED`. Giữ lịch sử chuyển trạng thái; VERIFIED phải tham chiếu phạm vi backend đã kiểm chứng, không hàm ý mọi thiết bị hỗ trợ.

Runtime availability theo `(target identity, binding, contract version/digest, environment revision)`:

- `AVAILABLE`: policy/quyền cho phép, attestation phù hợp và capability probe hiện hợp lệ.
- `UNSUPPORTED`: có bằng chứng backend không hỗ trợ.
- `UNVERIFIED`: chưa có bằng chứng hỗ trợ hợp lệ cho target.
- `PERMISSION_DENIED`: principal/target/scope bị chặn.
- `TEMPORARILY_UNAVAILABLE`: backend lỗi, mất kết nối hoặc probe không còn hiệu lực.

`IMPLEMENTED` không cấp execution. JSON lifecycle `VERIFIED` không tự cấp capability. RETIRED không được chọn mới; DEPRECATED chỉ dùng khi deployment pin tường minh và policy cho phép. Runtime kiểm lại gate trước call, không chỉ khi UI tải danh sách. Feature availability là phép tổng hợp khác với các trạng thái Function này.

## 7. Catalog, builder và loader

Cấu trúc đích: `catalog/{functions/<domain>,ports,skills,workflows,bindings/<backend>}`; backend laptop có namespace riêng, OpenWrt đến sau. Source giữ metadata; approval/attestation và runtime secrets không nằm trong source manifests.

Luồng build:

```text
Trusted catalog files + exact version selection
  → parse strict JSON (size/count/depth bounded, reject duplicate JSON keys/NaN)
  → validate schemas, IDs, version refs, policy vocabulary
  → validate graphs and port compatibility
  → stable sort + canonical JSON serialization
  → registry_v02 artifact + build manifest + report
  → explicit trusted startup selection → immutable registry context
```

Validator phải từ chối ID/version trùng, reference thiếu, unsupported schema keywords, remote schema resolution, dependency cycle trái semantics, scope mismatch, permission/verifier/probe ID lạ, binding không tương thích và khai báo executable không hợp lệ. Không reject mọi cycle trong graph retrieval: quan hệ tương tự/two-way vốn có thể có cycle; chỉ DAG dependency phải acyclic.

Builder không import module từ manifest, không gọi adapter/probe và không tự tạo quyền. Parse/build lỗi không publish artifact một phần. Cùng input/selection/version builder phải ra cùng byte/digest; timestamp báo cáo để ngoài phần canonical. Artifact thay thế bằng cơ chế atomic; runtime đang chạy giữ snapshot cũ đến lượt cấu hình mới được chấp nhận.

`data/registry_v02.json` là đầu ra dự kiến, không sửa tay. Trong phát triển ghi vào `runs/catalog-v02/`; chỉ commit bản phát hành đã review nếu repo quyết định lưu generated artifact, kèm cơ chế rebuild/check drift. `data/registry_v01.json` và frozen manifests không đổi.

Loader chỉ đọc artifact đã validate từ cấu hình startup tin cậy; không quét catalog mỗi request. Hỗ trợ v0.1/v0.2 tường minh; format không biết bị từ chối. Compatibility view phục vụ API còn phụ thuộc `registry.legacy`, nhưng không được tạo số liệu, khả năng thực thi hoặc waiver quyền giả.

CLI dự kiến, chưa tồn tại:

```text
python -m scripts.catalog validate --source catalog
python -m scripts.catalog build --source catalog --selection config/catalog_selection.example.json --output runs/catalog-v02/registry.json
python -m scripts.catalog report --registry runs/catalog-v02/registry.json
```

`report` phân biệt requirement, Function khai báo, version selected, binding implemented và target-verified executable count; không cộng chúng thành một số “lệnh chạy được”.

## 8. Retrieval và khả năng mở rộng

Dùng metadata indexes/domain filter + BM25/GoS hiện có trước. Filter không làm mất producer dependency ngoài domain; planner vẫn lấy đủ dependency đã được cấp quyền. LLM chỉ nhận candidate có giới hạn, không toàn catalog. Chỉ thêm vector/hybrid khi benchmark cho thấy lợi ích.

Benchmark catalog 10/100/1.000 Function được sinh riêng và gắn nhãn synthetic: đo validate/build/load time, peak RSS, artifact size, retrieve/compile latency và correctness của dependency closure. Không phát lệnh lên thiết bị trong benchmark này. Thử thêm một Function và một backend chuẩn mà không đổi GraphRunner hoặc feature; đó là test mở rộng kiến trúc, không phải bằng chứng có 1.000 backend commands thật.

Trước tối ưu phải ghi host/Python, corpus, warm/cold và baseline; ngưỡng tài nguyên cụ thể chốt theo môi trường laptop ở Foundation 03. Không thêm database/plugin framework/index dependency chỉ vì dự kiến có 1.000 lệnh.

## 9. Foundation roadmap và cổng nghiệm thu

GLM-01 (môi trường/upstream/baseline) vẫn là prerequisite để kết luận regression.

| Mã | Công việc / file đích dự kiến | Nghiệm thu cụ thể |
|---|---|---|
| FND-01 | Chốt contract/schema v0.2, ID/version/ref và bridge; `docs/contracts/catalog-v02/`, `tests/catalog/test_contract_schema.py` | Positive/negative vectors cho fields, retry, scope, unknown risk/permission, size limits; chưa viết loader trước khi schema được review |
| FND-02 | Chuyển một tập READ nhỏ sang `catalog/` theo domain; giữ baseline | Có ít nhất hai domain và shared port/Skill, source không trùng ID/version; chưa bulk migrate hàng trăm mục |
| FND-03 | `command_catalog/{loader,validator,builder,indexes}.py`, `scripts/catalog.py`, `tests/catalog/` | Validate toàn bộ refs/DAG/schema; deterministic build, atomic failure; CLI validate/build/report và scale report 10/100/1.000 synthetic |
| FND-04 | Trusted binding selection + conformance harness trong `adapters/`, `tests/adapters/` | Replay trước, laptop sau; sai version/target, probe fail, unapproved binding và backend errors đều không cấp execution; một selected backend/ID/context |
| FND-05 | Feature Registry dùng catalog: GLM-04 | Metadata không nâng quyền; READY/DEGRADED/UNAVAILABLE/DISABLED đúng target và required/optional ports |
| FND-06 | `command_catalog/compatibility.py`, loader/runtime bridge và policy gates, tests migration | Full v0.1 suite và frozen checks giữ nguyên; v0.2 READ chạy qua Core, risk/format lạ bị chặn, contract digest và checkpoint mismatch bị chặn; không ID-specific branches trong Runner |
| FND-07 | Luồng laptop Connectivity/Wi-Fi + snapshot + UI: GLM-03/05/06/07 | Linux live evidence đúng client/interface/freshness; Windows cũ giữ hoạt động; router metrics unavailable; acceptance end-to-end + replay smoke |

Thứ tự logic: `GLM-01 → FND-01 → FND-02 → FND-03 → FND-04 → FND-05 → FND-06 → FND-07`. Tests migration được viết từ FND-01, không đợi FND-06 mới phát hiện bridge không khả thi. Snapshot boundary GLM-03 có thể thiết kế sớm, nhưng mở rộng feature mới chờ gate Foundation.

FND-04 chỉ cần chứng minh conformance interface với replay và laptop; firmware/OpenWrt acceptance vẫn là GLM-06R sau đó. Ubus I/O hardening thuộc GLM-02 trước mốc router; Composite error isolation cần kiểm tra khi làm trusted bindings.

## 10. Bàn giao FND-01 và review trước các gate runtime

Đề xuất để review cùng nhau: schema catalog `0.2.0` tách contract SemVer; mỗi snapshot pin một version/ID; catalog metadata và runtime capability độc lập; digest v0.1 giữ nguyên; mốc đầu chỉ executable READ với laptop là target thật. Người dùng đã yêu cầu thực hiện FND-01; chuẩn metadata đã được triển khai và kiểm thử. Lựa chọn runtime/binding ở các gate sau vẫn cần được kiểm chứng khi triển khai.

FND-01: xem [báo cáo nghiệm thu](../../reports/FND01_CONTRACT_V02_20261113.md). Bước tiếp theo là FND-02 (catalog READ nhỏ); chưa thêm hàng loạt Function hoặc tạo loader runtime trong FND-01.
