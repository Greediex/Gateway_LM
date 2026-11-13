# FND-06 — Local runtime migration acceptance, 13/11/2026

**Base:** `5e0a50fa2112d31e963bd54200cb9f59cd21da45`, branch `v2`. [Plan](../superpowers/plans/2026-11-13-fnd-06-runtime-migration.md), [runtime guide](../RUNTIME_V02.md), [Foundation requirements](../superpowers/specs/2026-11-13-command-catalog-v02-design.md).

## Delivered

- Explicit v0.1/v0.2 loader dispatch; v0.2 requires approved exact artifact digest and complete revalidation. Unknown format/risk rejected.
- FunctionV02/Port mapping into existing GraphRegistry with READ_ONLY compatibility metadata. Runtime digest binds selected registry and exact versions; v0.1 class/hash unchanged.
- Operator-owned BindingSelection + scoped READ runtime, support probes/30-second leases, per-call rechecks, typed output/age validation before Core evidence admission. No conformance promotion or legacy world fallback.
- Shared `execute_ready_once → GraphRunner.step → InvocationExecutor → EvidenceVerifier` execution; no GraphRunner edits or Function-ID branches. READ-only policy, typed input arguments, ACL and environment pins.
- Trusted Core CapabilitySnapshot producer for FND-05 availability. Support READY is distinct from verified measurement and network health.
- Checkpoints pin runtime contract/registry, selected bindings, principal/ACL identity and environment. Same snapshot restores; changed contract/registry/principal/binding rejected. v0.2 restore validates pending records before mutating real state.
- Seed replay (3) and Linux (2) Function lifecycles PROPOSED → IMPLEMENTED, matching reviewed FND-04 providers; replay declaration pins updated. IMPLEMENTED is not a device capability or firmware acceptance.

## Verification

| Check | Result |
|---|---|
| New FND-06 focused suite | 16 tests pass in final full regression |
| Full unittest discovery | **594 total: 589 pass, 5 skip, 0 failures/errors**, 59.703 seconds |
| Repository structure/docs/artifact check | PASS |
| v0.1 golden runtime Function digests | 17/17 unchanged |
| Tracked data/benchmark SHA-256 checks against base | 19/19 unchanged |
| Legacy assistant replay smoke | GLM-04-0 WAN and GLM-21-1 client commands exit 0 with valid JSON |
| Generic extension test | New renamed Function + registered multi-output backend runs through unchanged Runner |
| Independent code review | No blocking findings; reviewer independently ran then-current 15 focused tests successfully; final additional changed-registry checkpoint test passed in full suite |

Commands:

```bash
.venv-graph/bin/python -m unittest tests.catalog.test_runtime_v02 -v
.venv-graph/bin/python -m scripts.check_project
.venv-graph/bin/python -m unittest discover -s tests -v
.venv-graph/bin/python -m gateway_pilot.assistant --fixture GLM-04-0 --request 'Check WAN' --trace
.venv-graph/bin/python -m gateway_pilot.assistant --fixture GLM-21-1 --request 'Laptop An có wifi nhưng không vào internet' --trace
```

Negative tests cover no probe, denied ACL, wrong target/boot/config, expired lease, mutated Function contracts, adapter absence, injected legacy world, unapproved artifact, unknown format/risk, PROPOSED lifecycle, lost supports/backend revision, malformed/duplicate/foreign outputs, incorrect source/metadata/version, stale/future time, NaN age, timeout and changed checkpoint bindings.

The initial full run caught one old seed assertion requiring PROPOSED after the intentional lifecycle migration. It was updated to require IMPLEMENTED while still prohibiting status/adapter approval in metadata. The complete suite above was rerun afterward.

## Linux local READ acceptance

Two reviewed Linux kernel-only bindings were explicitly selected for the existing laptop interface, with environment/target and artifact/binding digest pins. `ReadRuntime.probe()` returned **2 AVAILABLE support results**, then shared Core executed **2 calls**, verified **2 outputs** (identity and IPv4), and all plan nodes SUCCEEDED. Only redacted counts are recorded here; local payloads and identifiers are not committed.

This proves the v0.2 bridge can admit those two laptop measurements. It does **not** prove RSSI, Wi-Fi quality, Internet health, OpenWrt/firmware, NPU or WRITE. Full laptop Connectivity/Wi-Fi snapshot, route-change invalidation and UI remain FND-07.

## Limits and evidence

The 5 skips are Windows live tests on the Linux host. No Windows hardware acceptance was attempted. Backend blocking I/O remains the provider's responsibility; elapsed checks reject late results but cannot cancel a stuck syscall. Snapshot availability is advisory support and does not replace verified facts or Claim evaluation. Metadata CLI remains unavailable without explicit Core integration.

Local ignored artifacts: `runs/fnd-06/regression-final.log`, `focused.log`, `wan-smoke.json`, `client-smoke.json`, generated registry artifacts and `laptop-summary.json`. Hosted CI is run against the pushed commit; its exact URL/result is reported separately after push.
