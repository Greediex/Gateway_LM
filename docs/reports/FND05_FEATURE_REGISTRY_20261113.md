# FND-05 — Feature Registry/availability: nghiệm thu local

Ngày 13/11/2026; nhánh `v2`; base `4373f716d23a6aaf0afc2aa96aee290a3843913d`.

## Kết quả

[Feature Registry guide](../FEATURE_REGISTRY_V02.md): strict READ manifest schema, exact Catalog port versions/scopes, unique Feature IDs, trusted flags ngoài manifest; default missing flags disabled. Registry copy snapshot và không đăng ký/cấp quyền Function mới.

Application availability tính DISABLED/UNAVAILABLE/DEGRADED/READY từ metadata và typed capability snapshot của trusted Core service. Snapshot pin registry, Function version/metadata digest, target/environment, exact permissions, server principal/ACL policy context và monotonic TTL tối đa 60s. Unknown/expired/wrong-context snapshots bị chặn; FND-04 conformance dictionary không được dùng thay capability.

Dependency/ORDER và alternative producers được kiểm bằng partial dependency witness; default strict helper của FND-03 không đổi. Không gọi backend, probe hoặc admit evidence. Mọi report `authorizes_execution:false`, `health_evaluated:false`.

## Kiểm chứng

| Check | Kết quả |
|---|---|
| Tests trước implementation | Fail vì chưa có Feature Registry/application module; red log đã ghi |
| Feature tests cuối | 16 pass |
| Full regression cuối | 578 tests: 573 pass, 5 Windows-only skip, 0 fail/error |
| 5 skip | Windows live tests yêu cầu Windows; host hiện tại Linux |
| Metadata preview replay | 2 enabled Features: UNAVAILABLE / RUNTIME_NOT_CONNECTED |
| Metadata preview laptop | 1 enabled Feature: UNAVAILABLE / RUNTIME_NOT_CONNECTED |
| Compatibility | 19 tracked data/benchmark file hashes khớp; golden registry và 17 v0.1 Function digests vẫn pass |
| Review riêng | Không có finding correctness/security cần chặn; kiểm thêm ORDER/alternative reachability cũng đạt |

READY/DEGRADED positives trong tests dùng **synthetic trusted Core snapshots**, không phải proof runtime v0.2 đã nối hoặc device Feature đã được nghiệm thu. Trạng thái preview thực vẫn unavailable đúng thiết kế vì producer Core snapshot thuộc FND-06. Conformance laptop ở FND-04 không bị nâng thành availability/runtime permission.

Negative cases: manifest tự cấp WRITE/capability/backend/enabled/status, refs sai/unknown/overlap/scope, duplicate ID, invalid flags, permission thiếu, target/environment/policy/registry khác, Function version/digest sai, snapshot hết hạn/tương lai/trùng IDs/TTL vượt giới hạn, indirect permission và ORDER bị chặn. Tests alternative producer chứng minh một producer UNSUPPORTED không phủ định producer hợp lệ khác. Cùng service chuyển target không reuse trạng thái READY từ target cũ.

Commands:

```bash
.venv-graph/bin/python -m unittest tests.features.test_registry -v
.venv-graph/bin/python -m unittest discover -s tests -v
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m scripts.features --registry runs/fnd-05/replay-registry.json
```

Log/preview local trong `runs/fnd-05/` bị Git ignore. Chưa có kết quả hosted CI tại thời điểm lập báo cáo local; URL/kết quả GitHub CI sau push được báo riêng. Không thay Router/Resolver/Runner/Answer, không mở WRITE, không có hardware/NPU acceptance mới. FND-06/07 vẫn pending.
