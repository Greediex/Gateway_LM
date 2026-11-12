# Nine remaining workstreams — evidence-based acceptance (2026-11-12)

The codebase can be extended and tested on GitHub Actions; real device,
firmware, NPU, vendor credentials and independent, labeled traffic incidents
are **not available to the CI runner**. A green mock/synthetic CI is never
a substitute for evidence from the target router.

| Workstream | Implemented and testable now | Still required to accept |
| --- | --- | --- |
| General Task Decomposition | Optional `OllamaGoalModel`, bounded output-port proposal, dev-only threshold selection and labeled test protocol | Local Ollama model installed/running; independent Vietnamese/English/OOD holdout; calibrated safety+coverage; no arbitrary unknown Function execution |
| 22 Skill / 270 requirements | `audit_requirement_traceability.py` exact requirement→Function→Skill mapping, unmapped backlog, firmware-probe count | Product owners define 14 more Skill contracts; implement/verify real adapter Functions for prioritized requirements; never auto-synthesize 270 tools |
| Hybrid Retrieval | Local sentence-transformers adapter, BM25/GoS baseline, held-out JSONL evaluator | Fully downloaded local embedding model, unseen-issue holdout, memory/latency measurement and quality thresholds |
| Unified Agent | Common READY selector and GraphRunner; GoalAgent and RCAAgent share typed executable gates | Single orchestrator contract/policy transitions for all Fastpath/Resolver/ReAct branches and adversarial session tests; remaining legacy policy state machines |
| Full Job Recovery | Signed fact checkpoint + HMAC read-only step journal; one-time SQLite WRITE approvals | Idempotency-key acknowledgement on firmware, crash injection at before/after APPLY and READBACK, external durable outbox and reconciliation of in-doubt changes |
| OpenWrt | `UbusCliReadTransport` using `ubus -v list` and `ubus -S call`, subprocess with shell disabled, bounded timeout; UbusReadAdapter schema/permission gates | On-device mapping+method discovery; real JSON schema/provenance captures; firmware boot/config rev and negative tests |
| Edge–Cloud | Edge-first privacy/consent/budget gate; hypothesis-only backend contract | Trusted provider adapter/config/credentials; privacy review, real billing/rate limits, network egress, audit and user consent UX |
| WRITE | Signed target/revision/operator approval, durable nonce, snapshot/preview/readback/rollback state machine (default disabled) | Certified board firmware driver, independent auth/rollback, crash/power tests and manual reconciliation; no unattended hardware WRITE |
| Hardware benchmark | `measure_gateway.py` reads /proc CPU/RAM/RSS and optional firmware NPU sysfs utilization; stamps platform evidence | Run on target IPQ device with chosen firmware, actual NPU counter, QNN model inference log, latencies/p95 and RAM peak under real workload |

## Reproducible acceptance commands

```bash
# A. Requirements — actionable backlog (no Function execution)
python -m scripts.analysis.audit_requirement_traceability \
  --output runs/requirement_traceability.json

# B. Real LLM goal proposal evaluation. The input JSONL is created
# independently with dev and test splits and labels; use a local Ollama model.
python -m scripts.analysis.evaluate_goal_proposals \
  --model qwen3:0.6b --input /trusted/labeled_goal_holdout.jsonl \
  --output runs/goal_model_eval.json

# C. Real embedding evaluation on a separate held-out Function suite.
python -m scripts.analysis.evaluate_retrieval \
  --methods bm25 gos hybrid --registry v01 \
  --semantic-model-dir /trusted/embedding_model \
  --input /trusted/labeled_function_holdout.jsonl \
  --output runs/embedding_holdout.json

# D. On router only. Missing NPU sysfs counter is NOT a 0% measurement.
python -m scripts.hardware.measure_gateway --samples 60 --interval 1 \
  --pid YOUR_GATEWAY_AGENT_PID \
  --npu-counter /sys/YOUR_VENDOR_VERIFIED_NPU_PERCENT_COUNTER \
  --output runs/gateway_hardware.json --require-device

# E. All negative and regression tests on the host.
python -m unittest discover -s tests -v
```

`YOUR_GATEWAY_AGENT_PID` and the NPU path must be replaced by **observed**
on-device values; do not invent a sysfs counter name. On standard GitHub CI,
`measure_gateway --samples 2 --interval 0` is only a host smoke check, and
`--require-device` will fail.

## Objective exit gates

- **Safety**: zero unauthorized WRITE, unknown tool calls, prompt-injection
  executions and false verified diagnoses on the frozen adversarial holdout.
- **Functional**: each supported Function passes on-device probe, output
  JSON Schema, TTL, provenance and target validation; catalog-only remains
  unavailable until real implementation exists.
- **Quality**: report recall@K, MRR@K, proposal precision/coverage and
  abstention on a *held-out* split created independently of development.
  Report per-language and per-fault-category slices.
- **Device**: capture p50/p95 end-to-end latency, memory peak, CPU busy,
  NPU utilization (only when an actual counter is available), model context
  and firmware revision. The IPQ 1 GB RAM target must retain enough headroom
  for the router/OS; a simulated host number is not an acceptance number.
- **Durability**: crash/power fault injection in each WRITE transaction phase,
  idempotent firmware request ID and independent readback reconciliation.
- **Privacy/cloud**: explicit authenticated consent, approved egress and
  per-request cost limits, with Cloud hypotheses independently verified Edge-side.

Do not mark any hardware/model/provider row as PASS until its artifact
contains source, command, environment and measured outcome. The 270-item
requirements list is a product taxonomy, **not** a 270-Function executor.
