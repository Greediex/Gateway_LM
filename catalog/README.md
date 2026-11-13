# Gateway LM — READ seed catalog (FND-02)

Catalog metadata schema **0.2.0**, bổ sung ngày 13/11/2026 trên nhánh `v2`. Đây là tập READ nhỏ để kiểm chứng cách tổ chức theo domain và exact references. Không được runtime tự quét/nạp, chưa có executable binding hoặc capability mới.

## Danh mục

| Domain / Function | Function version | Input port | Output port | Skill |
|---|---|---|---|---|
| `clients` / `clients.resolve` | 4.0.0 | Không | `client.identity` 2.0.0 | `client.identity.inspect` 1.0.0 |
| `wifi` / `wifi.station` | 4.0.0 | `client.identity` 2.0.0 | `wifi.station` 2.0.0 | `client.connectivity.inspect` 1.0.0 |
| `lan` / `client.ipv4` | 4.0.0 | `client.identity` 2.0.0 | `client.ipv4` 2.0.0 | `client.connectivity.inspect` 1.0.0 |

Các file nằm trong `functions/<domain>/`, `ports/`, `skills/`; một file cho mỗi contract. Filename dùng ID, version nằm trong nội dung; khi cần nhiều version cùng ID, dùng `<id>@<version>.json` theo [layout FND-03](../docs/CATALOG_V02.md). Domain là metadata tổ chức/tìm kiếm, không phải quyền. Không tạo thư mục workflow/binding rỗng khi chưa có tài liệu phù hợp để đưa vào.

Hai Function Wi-Fi/IPv4 dùng chung **một port identity** và **một Skill connectivity**. Identity có đúng một producer trong seed. Không nhân bản schema identity trong các domain hoặc tạo adapter riêng cho từng feature.

[Exact selection mẫu](../config/catalog_selection.example.json) pin đúng 3 Function/3 Port ở trên. Skill versions được pin qua `skill_refs`; Skill `function_refs` cũng tham chiếu chính xác ngược lại. Selection được Builder FND-03 sử dụng để tạo artifact metadata, không phải cấu hình bật runtime hiện tại.

## Chuyển từ v0.1 và quản lý thay đổi

Nguồn tham khảo là `data/registry_v01.json` ở base commit `d0983fa`. File đó và toàn bộ dữ liệu/benchmark cũ giữ nguyên; catalog không thay thế v0.1 loader. [Golden v0.1 tests](../tests/catalog/test_contract_compatibility.py) tiếp tục kiểm hash registry và toàn bộ 17 runtime Function digests.

| Nội dung | v0.1 giữ nguyên | Catalog mới |
|---|---|---|
| Function versions | 3.0.0 | 4.0.0, major mới vì input/output contracts và args bị thu hẹp |
| Port references | `client.identity/v1`, `wifi.station/v1`, `client.ipv4/v1` | Port ID + exact SemVer 2.0.0 |
| Port payload | `additionalProperties:true` | Object đóng; string có length bounds; client ID không rỗng |
| Arguments | Có các optional fields dùng chung cho nhiều Function | Resolver zero-argument; Wi-Fi/IPv4 chỉ nhận `client_id` từ identity fact |
| Skills | `SK01`, `SK02`, `SK03` 0.1.0 trong baseline | Hai Skill mới namespaced version 1.0.0, không đổi tên/ghi đè Skill baseline |
| Runtime status | Các Function mẫu v0.1 là `REPLAY_ONLY` | Lifecycle `PROPOSED`; không copy `status` hoặc adapter approval |
| Provenance | `synthetic_replay/` | Vẫn `synthetic_replay/`, không được gắn nhãn laptop/router live |

Field schema của seed dựa trên các port cũ, nhưng không được công bố là drop-in compatible. Dữ liệu cũ có extra properties hoặc client ID rỗng có thể không đạt schema mới. Không upgrade evidence/digest cũ sang version mới. Các metadata probe IDs được giữ để trace về thiết kế replay; chúng chưa được resolve/approve cho v0.2.

Port `wifi.station` giữ **RSSI dBm**. Giá trị signal % của `nmcli` không thỏa hợp đồng này; không đổi phần trăm thành dBm. Khi làm laptop live, cần backend thực cung cấp dBm hoặc một contract riêng biểu diễn signal %/metric chưa hỗ trợ. `client.ipv4.address` cho phép empty string để biểu diễn trạng thái chưa có địa chỉ, giữ field `configured` riêng; schema không phải kết luận Internet hoạt động.

## Skill metadata

FND-02 bổ sung kind `skill` vào [schema Contract 0.2.0](../docs/contracts/catalog-v02/contract.schema.json), theo cách thêm loại document; các Function/Port/selection hợp lệ ở FND-01 không đổi.

Skill gồm `skill_id`, exact `version`, `name`, `description`, các map `requires`/`produces`/`completion_ports` (port ID → version) và `function_refs` (Function ID → version); `tags` tùy chọn. `produces` và `function_refs` không rỗng. Completion ports phải là tập con **đúng version** của produces. Không có permission, executable source, WRITE set, probe result hoặc runtime capability trong Skill metadata.

API `validate_contract` kiểm shape và completion-port consistency của từng Skill. Nó vẫn không resolve toàn catalog. [Seed tests](../tests/catalog/test_seed_catalog.py) kiểm tĩnh tập đã đưa vào repo: uniqueness, domain, exact refs, scope, argument field type, chia sẻ port/Skill, version migration và selection coverage. Đây là tests tĩnh của seed. [Tooling FND-03](../docs/CATALOG_V02.md) bổ sung strict loader, cross-reference/dependency checks, deterministic build và report với profile READ scope-local.

## Kiểm tra

```bash
.venv-graph/bin/python -m unittest tests.catalog.test_seed_catalog -v
.venv-graph/bin/python -m unittest discover -s tests/catalog -v
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m unittest discover -s tests -v
```

Số lượng: **3 Function contracts, 3 Port contracts, 2 Skill contracts**; đây không phải 3 lệnh được phép thực thi trên laptop/router. Không sửa GraphRunner, policy hoặc Function catalog v0.1 trong FND-02.

## Tooling FND-03

[CLI validate/build/report](../docs/CATALOG_V02.md) đã có. Vocabulary probe IDs nằm ở [policy mẫu](../config/catalog_policy.example.json), không phải probe approval. Builder output ở `runs/`, luôn `execution_enabled:false`; không auto-bind/nạp vào Core và không thay thế registry v0.1. [Scale report synthetic](../docs/reports/FND03_CATALOG_BUILDER_20261113.md) không phải on-device acceptance.
