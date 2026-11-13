# Gateway LM — implementation task status (2026-11-12)

This is the **live roadmap**, not a claim that passing synthetic tests means
the product is complete. The reference for each task is the current branch
`refactor/gateway-lm-composite-adapter-pr01`; historical Graph v4 results
remain snapshots, not refreshed production measurements.

| Task | Status | Evidence / acceptance boundary |
| --- | --- | --- |
| Repository hygiene, CI, Developer Guide | DONE (pilot) | `scripts.check_project`, CI |
| Contract Registry, Skill relations, dependency DAG | DONE (pilot) | `test_registry_v01`, `test_compiler_v01` |
| Router / Planner / Executor / Verifier stages | DONE (pilot) | `test_runtime_stages` |
| Multi-output `ToolResult` and error isolation | DONE (pilot) | `test_tool_result` |
| Composite Function Adapter and probe gate | DONE (pilot) | `test_composite_adapter` |
| Unified READY-node selection interface | DONE (pilot) | `selection.py`, `test_task_decomposer` |
| Multi-clause goal decomposition, bilingual aliases | DONE (bounded) | `task_decomposer.py`, `goal_aliases_v01.json`; unknown/unsafe => zero calls |
| Free-form semantic task decomposition | PARTIAL (real local-model adapter + offline calibration harness) | `OllamaGoalModel` and dev/test goal metrics implemented; real Ollama heldout NOT RUN; unknown Functions still blocked |
| Resolver, Fastpath, ReAct shared execution | DONE (common READY dispatch + typed TaskRuntime pilot) / POLICY UNIFICATION PARTIAL | `TaskRuntime` gives one read-only MEASURE/DIAGNOSE state path; legacy workflow-specific terminal policies remain distinct |
| Dynamic graph replanning + bounded repair | DONE (pilot) | Existing graph v4 tests; no crash recovery |
| Evidence-led RCA / claim engine | DONE (adaptive read-only replay pilot) / REAL VALIDATION PENDING | `RCAAgent` and localhost `POST /api/rca`; selects missing Claim evidence, replans under budgets; no hardware/causal proof |
| 22 Skills / 270 requirements | DESIGN / PARTIAL (8 Skills, 17 Functions, 10/270 mapped) | Traceability audit is reproducible; 260 requirements unmapped; firmware-supported count is 0 |
| Versioned declarative read-only Function/Skill overlay | DONE (bounded pilot) | JSON manifest adds gateway zero-input single-output READ contracts transactionally; v0.1 starts unverified, no firmware claim |
| Semantic vector + lexical + graph retrieval | DONE (opt-in integration, mock-tested) / MODEL EVAL PENDING | Local embedding adapter, cosine threshold, BM25/GoS fusion, strict gates; no measured encoder accuracy, latency or NPU |
| Offline retrieval benchmark protocol | DONE (harness, illustrative data only) | JSONL split/group evaluator; Recall@K, Precision@K, MRR@K, host latency; independent held-out/model evaluation still pending |
| HMAC-authenticated evidence checkpoint | DONE (read-only pilot) | `checkpoint.py`, `test_checkpoint` — fresh facts only, not running jobs/WRITE actions |
| Signed read-only DAG step journal | DONE (local pilot) | HMAC chain, atomic bounded audit, context/ACL verification; combined with EvidenceCheckpoint for safe READ replanning |
| Full durable DAG/job recovery | PARTIAL (durable WRITE outbox pilot) | `DurableWriteOutbox` records in-doubt WRITE and reconciles via readback, NEVER blindly retries; no firmware idempotency proof / exactly-once |
| OpenWrt read-only Adapter interface | DONE (mock-only) | `ubus_read.py`, `test_ubus_read` — injectable trusted firmware-specific transport, no guessed mapping |
| OpenWrt firmware probes and verified adapters | INTEGRATION IMPLEMENTED / BLOCKED ON HARDWARE | `UbusCliReadTransport` uses bounded subprocess calls and method discovery; no board-backed probe pass or schema captures |
| Edge–Cloud policy and privacy/budget gate | DONE (opt-in HTTPS transport + mock tests) / LIVE PROVIDER PENDING | `HTTPSHypothesisBackend` has approved HTTPS host, no redirects, strict payload/response; no credentials/provider benchmark in CI |
| Hardware latency / CPU / RAM / NPU test | INSTRUMENTATION DONE / BLOCKED ON HARDWARE | `measure_gateway.py` + `summarize_inference.py` report authentic CPU/RAM/NPU & TTFT/p95; CI host results never count |
| WRITE approval and rollback state machine | DONE (disabled-by-default mock + durable in-doubt outbox) / FIRMWARE PENDING | One-time signed approval, persistent PREPARED/IN_FLIGHT receipt and readback-only reconciliation; no real router rollback |

## Decomposition contract

```text
Vietnamese / English compound request
  -> conservative clause splitter
  -> aliases in data/goal_aliases_v01.json
  -> each clause must uniquely identify a registered read-only output port
  -> unknown/ambiguous clause: NEEDS_INPUT, zero calls
  -> write clause: BLOCKED, zero calls
  -> typed Compiler: producer selection + dependencies + budgets
  -> common READY selector -> GraphRunner -> Adapter -> EvidenceVerifier
  -> Goal evidence only (no automatic diagnosis)
```

A single request continues to use calibrated `route_turn` and its
existing uncertainty gates. A compound request may map multiple named ports,
but this is deliberately **not** a semantic generalist that can infer arbitrary
unknown actions or execute catalog-only requirements.

### Definition of DONE

One feature is marked done **at pilot level** only when a test demonstrates its
positive and negative contracts and the full CI passes. Real network and
hardware claims require board-backed evidence, not generic simulations.

## Nine-workstream acceptance protocol

See [ACCEPTANCE_9_TASKS.md](ACCEPTANCE_9_TASKS.md) for model/calibration, 270-requirement traceability, OpenWrt Ubus, on-device metrics, Cloud and WRITE sign-off gates. A green CI does not complete board-backed tasks.

## Foundation update — 2026-11-13

FND-01 **DONE (metadata/local validation only)**: [Function/Port/exact-selection schema v0.2](contracts/catalog-v02/README.md), bounded standalone validator, 17 contract/compatibility tests. Full local regression: 519 tests, 514 pass, 5 Windows-only skips; v0.1 registry/digests unchanged. [Acceptance report](reports/FND01_CONTRACT_V02_20261113.md). No v0.2 runtime loader/builder or new executable capability; later Foundation gates remain pending. No new GitHub CI URL or device acceptance.

FND-02 **DONE (seed metadata only)**: [3-domain READ catalog](../catalog/README.md), 3 Functions/3 Ports/2 Skills, shared identity and connectivity Skill, exact version selection. New major contract versions document the narrowed schemas; v0.1 is unchanged. [Acceptance report](reports/FND02_READ_SEED_CATALOG_20261113.md): 24 catalog tests pass; full local regression 526 tests, 521 pass, 5 Windows-only skips. No runtime catalog loader/builder or live-device capability added.

FND-03 **DONE (READ metadata tooling)**: [strict catalog validator/builder and CLI](CATALOG_V02.md), deterministic self-contained artifacts, integrity revalidation and indexes/dependency witness. [Local acceptance](reports/FND03_CATALOG_BUILDER_20261113.md): 43 catalog tests pass; full regression 545 tests, 540 pass, 5 Windows-only skips; synthetic 10/100/1,000 scale budgets pass. v0.1 data/digests unchanged. No v0.2 runtime integration, adapter capability or device acceptance claimed.

FND-04 **DONE (binding selection + READ conformance)**: [guide](ADAPTER_BINDINGS_V02.md), exact approvals/contract/backend/probe/target/environment pins, replay and Linux kernel READ providers. [Local acceptance](reports/FND04_BINDINGS_CONFORMANCE_20261113.md): 17 adapter tests pass, full regression 562 tests (557 pass, 5 Windows-only skips); 3 replay samples and 2 live laptop identity/IPv4 checks conformant. No RSSI dBm support in current Linux provider, no Core evidence admission/runtime capability, no firmware/WRITE acceptance. FND-06 remains responsible for runtime bridge.

FND-05 **DONE (metadata + advisory availability)**: [Feature Registry](FEATURE_REGISTRY_V02.md), READ manifests, external flags, target/context/permission/TTL-bound Core snapshot interface, required/optional and dependency/alternative semantics. [Local acceptance](reports/FND05_FEATURE_REGISTRY_20261113.md): 16 feature tests pass; full regression 578 tests, 573 pass, 5 Windows-only skips. READY cases use synthetic Core snapshots only; real metadata preview remains UNAVAILABLE until FND-06. No capability issuance/evidence/health claim.

FND-06 **DONE (trusted READ runtime migration)**: [guide](RUNTIME_V02.md), explicit v0.1/v0.2 loader, exact pinned FunctionV02/compatibility view, Core support leases + Feature snapshot producer, shared execution kernel/Verifier và checkpoint registry/binding/principal gates. [Local acceptance](reports/FND06_RUNTIME_MIGRATION_20261113.md). UI và full laptop connectivity/Wi-Fi vẫn thuộc FND-07; không firmware/WRITE acceptance.

FND-07 **DONE (Linux laptop demo)**: [guide](LAPTOP_NETWORK_V2.md), 7 registered local READ Functions qua shared Core, immutable freshness/environment-checked snapshots, Connectivity/Wi-Fi rules và local dashboard/chat. README ưu tiên v2 và cách test. Windows/replay giữ regression; router health UNAVAILABLE. [Local acceptance](reports/FND07_LAPTOP_NETWORK_20261113.md).
