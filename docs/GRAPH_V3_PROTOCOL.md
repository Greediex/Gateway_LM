# Graph v3 — scope and evaluation lock

Implementation scope authorized 2026-11-07: correct the graph subsystem within the diagnostic replay pilot. Legacy modules, data and runs are preserved. This is not completion of all 101 UC/270 requirements, production firmware adapters, transactions, lifecycle or Cloud.

## Implemented graph contract

- `G_S`: typed consumer→prerequisite hard edges, soft composition/alternative edges, conflict constraints; dry-run propose, permission/version-checked apply, versioned rollback. This is a Gateway implementation of these semantics, not an import of SkillDAG's vector/evolution runtime.
- `G_SF`: explicit bidirectional membership indices used in retrieval and compiler skill preconditions.
- `H_F`: multi-input/multi-output contracts, conservative schema-subset checks, scope/provenance compatibility and compatible producer search. Unsupported schema constructs fail closed; this is not a complete general JSON Schema subsumption solver.
- `G_run`: invocation objects carrying target, input/evidence bindings, arguments, verifier, contract digest, node state; explicit DATA/STATE/ORDER edges, cycle checks, graph revision and per-node history.
- Planner enumerates admissible producer choices within `max_search/max_nodes/max_cost`, selecting the minimum declared summed `cost + latency_ms/1000` of completed plans if search finishes. Estimates are policy declarations, not measured board latency. Search exhaustion is an error, not an optimality claim.
- Read-only runner rechecks eligibility, binds argument values from evidence IDs, schedules only READY nodes, verifies output schema/source/scope/freshness/version, and records actual node transitions. Deadline checks are cooperative before/after the replay call; no preemptive real-device adapter is supplied.
- Bounded read retry and substitute/rewire/insert-prerequisite repair; preserve requested root obligations and unaffected verified evidence, invalidate DATA/STATE descendants, preserve monotonic plan revisions and audit diffs. The five GraSP repair operators/learned controller are not reproduced wholesale.

## Actual upstream reuse

Load `third_party/graph-of-skills/gos/core/retrieval.py` from commit `203f60a2c689da055ce1ac351eb3cb9912a3bca7`, SHA-256 `3c03db37774949b67d03e5da2852bbc694ae9a8d38593bdd7d17d6f7a03d072c`.

The runtime calls the original `build_transition_matrix`, `build_personalization`, `personalized_pagerank`; missing or changed kernel fails explicitly. Map hard dependencies into GoS producer→consumer direction; use upstream reverse weights and restart .2; no conflict diffusion. Matrix/PPR analytic and direct-kernel parity tests cover this adapter. This reuses the actual PPR kernel, not the entire GoS embedding/LLM seed/rerank/hydration pipeline; no SE-GoS training/evolution is claimed.

Core retrieves with current missing goals, verified values and recent errors. Filter capability/permission and completed outputs before top-k. The original GoS scores actually prioritize the eligible READY set; rank cannot bypass input, guard or policy checks. Skill soft relations only affect retrieval, never become mandatory execution steps.

## Test and measurement boundaries

1. New graph tests verify semantic invariants, upstream parity, cost alternatives including multi-output sharing, controlled graph edits, deadline/budget, real-clock expiry, scope/provenance, contract changes and repair regressions.
2. Structural evaluation runs the same 48 synthetic scenarios without model calls; null model-success fields mean not scored, not failed diagnosis. Four hand-constructed retrieval oracles (library size 4/16/64/128) isolate recovery of a lexically invisible prerequisite with k=2. This microbenchmark is not real-world or paper benchmark accuracy.
3. Optional model evaluation uses the same local `qwen3:1.7b` artifact (actual metadata count below 3B), CPU, native terminal tools, same labels/checklists/semantic FINISH validator as v2. Core/graph acquires evidence; model is analyst, not owner of graph edits or firmware execution. Up to three model verdict proposals; no citation repair or label correction.
4. A changed acquisition order changes evidence IDs/context, and new guards can block unnecessary probes. End-to-end differences versus v2 do not isolate PPR alone. The old synthetic templates have already been observed; new results are engineering follow-up, not a new blind holdout or an intrinsic model capability ceiling.
5. Single-target diagnostic case: Function ID is unique within the plan; invocation objects carry target/bindings/version separately. Arbitrary multi-target invocations in one case, durable crash recovery, real adapters and forwarding/NPU resource benchmarks remain outside this scoped runner.

Freeze graph source before the model evaluation. Every run uses a fresh output directory and records source snapshot/hashes, original data hashes, migrated registry, upstream provenance, package versions, plans/edges, selections, raw native calls and full outcomes. Do not overwrite or merge legacy results.
