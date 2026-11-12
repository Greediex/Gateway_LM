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
| Free-form semantic task decomposition | PARTIAL (bounded LLM proposal opt-in) | Model may nominate registered READ goals via quoted spans; no generalized planning, calibration or WRITE |
| Resolver, Fastpath, ReAct shared execution | DONE (shared READY dispatch) / POLICY UNIFICATION PARTIAL | All diagnostic paths select and invoke via `execute_ready_once` or `run_plan` + GraphRunner; workflow policy state machines remain distinct |
| Dynamic graph replanning + bounded repair | DONE (pilot) | Existing graph v4 tests; no crash recovery |
| Evidence-led RCA / claim engine | DONE (adaptive read-only replay pilot) / REAL VALIDATION PENDING | `RCAAgent` and localhost `POST /api/rca`; selects missing Claim evidence, replans under budgets; no hardware/causal proof |
| 22 Skills / 270 requirements | DESIGN / PARTIAL | Catalog presence does not mean 270 executable Functions |
| Versioned declarative read-only Function/Skill overlay | DONE (bounded pilot) | JSON manifest adds gateway zero-input single-output READ contracts transactionally; v0.1 starts unverified, no firmware claim |
| Semantic vector + lexical + graph retrieval | DONE (opt-in integration, mock-tested) / MODEL EVAL PENDING | Local embedding adapter, cosine threshold, BM25/GoS fusion, strict gates; no measured encoder accuracy, latency or NPU |
| Offline retrieval benchmark protocol | DONE (harness, illustrative data only) | JSONL split/group evaluator; Recall@K, Precision@K, MRR@K, host latency; independent held-out/model evaluation still pending |
| HMAC-authenticated evidence checkpoint | DONE (read-only pilot) | `checkpoint.py`, `test_checkpoint` — fresh facts only, not running jobs/WRITE actions |
| Full durable DAG/job recovery | NOT YET | Requires persistence of job receipts, idempotency and crash-safe external side effects |
| OpenWrt read-only Adapter interface | DONE (mock-only) | `ubus_read.py`, `test_ubus_read` — injectable trusted firmware-specific transport, no guessed mapping |
| OpenWrt firmware probes and verified adapters | BLOCKED ON HARDWARE | No firmware access or board-backed probe pass |
| Edge–Cloud policy and privacy/budget gate | DONE (mock-only policy) / REAL INTEGRATION PENDING | Disabled by default; explicit consent, aggregate-only telemetry, bounded requests/estimated USD; no provider/NPU measurements |
| Hardware latency / CPU / RAM / NPU test | BLOCKED ON HARDWARE | Must test target device |
| WRITE approvals and transactional rollback | NOT YET | Explicitly disabled in read-only pilot |

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
