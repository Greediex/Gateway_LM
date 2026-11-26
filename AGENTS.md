# AGENTS.md — Gateway LM coding rules

Applies to this repository. These are engineering rules, **not credentials or model prompts**.

## Task tracking

- For any plan, backlog, checklist or progress update, follow **[TODO.md — Quy tắc cập nhật](TODO.md#quy-tắc-cập-nhật)**. Update that root file in place, including when a skill suggests a separate plan artifact; create another tracking file only when the user explicitly requests it.

## Scope and honesty
- Working branch is `v2`. Codex tasks branch from it as `codex/<task-id>` in their own worktree. Never edit/merge `main` without explicit approval. (The old `refactor/gateway-lm-composite-adapter-pr01` branch is historical.)

## Codex task workflow

- Each task comes as a brief (`codex_tasks/<ID>.md` next to the repo, listed in [TODO.md](TODO.md)). Do only what the brief says; anything else goes in the report as a proposal.
- Start: `git worktree add ../wt-<id> -b codex/<id> v2`. Do not work in the main `Gateway_LM_v2` checkout; it may hold someone else's staged changes.
- Python is `.venv-graph/bin/python` (the bare `python` in the commands below means this interpreter).
- Finish: one commit `feat(<ID>): ...` on `codex/<id>`, no push, one progress line in TODO.md (checkbox unchanged), report at `../codex_tasks/reports/codex_<id>_report.md` with real numbers and commands run.
- Blocked or a gate fails: stop, commit nothing that weakens a check, and write the report saying what failed.

## Evaluation discipline (triage / LLM work)

- Tune only on `dev`. A locked `test` split is run **once per task, at the end**, aggregate numbers only; never print, read or copy per-case test text or labels.
- Never copy wording from any eval split into taxonomy, phrases, prompts or rules. Routing vocabulary must come from catalog text or the cited `sources` of a taxonomy group.
- Do not add refusal rules to raise precision; false refusals on test must not rise above baseline.
- A change that improves dev but not test is overfit: report it, do not ship it (see the TRIAGE-02 revert, `6d61d52`).
- Treat this as an evidence-driven **pilot**. Do not claim firmware/NPU deployment or arbitrary-task ability without actual measurements.
- Keep v1/v2 experiments, Graph v3/v4 protocols, frozen fixtures and historical reports intact; mark historical results as historical.

## Design boundaries
- The **Router** interprets requests; **Resolver/Planner** proposes eligible Function DAGs; **Runner** executes; **Verifier/Claim Engine** validates evidence and terminal claims.
- No user text or LLM text may execute commands directly. Use typed Function IDs and allowlisted adapters.
- Structured ToolResult must declare all outputs exactly once; reject partial, foreign and duplicate IDs before admitting evidence. Error results have no successful observations.
- A completed set of measurement ports is not by itself evidence for an RCA diagnosis. Do not label `GoalAgent` results as repaired incidents.
- Only the trusted Core may authorize `WRITE`; default is read-only. Preserve hard ACL, target/scope, schema, TTL and budget gates.
- A Function capability is `PROBE_OK` only after verification. Never assume OpenWrt backend support from a placeholder map.
- New Skill/Function/Workflow or retrieval algorithm should extend registries/interfaces instead of introducing workflow-name conditionals in Core.
- Declarative extension manifests may only describe preapproved READ metadata. No executable source, WRITE rights, remote schema references, auto-probe approval or auto-backend binding.
- Preserve typed DAG dependency semantics (DATA/STATE/ORDER), plan revisions, evidence provenance and local/global repair guards.
- No silent fallback on failed upstream SHA checks. Pinned GoS/SkillDAG source and license terms stay intact.
- Opt-in semantic retrieval must use a trusted local encoder, never user-provided model paths or remote requests. Vector scores must never bypass eligibility, ACL, scope or evidence verification.

## Code and data quality
- Prefer small, cohesive changes and explicit dependencies over broad file moves or rewrite-from-scratch.
- Use type hints at new module boundaries, meaningful names, small functions and structured errors. Don't swallow exceptions that affect safety decisions.
- Distinguish Observation, verified Fact, Hypothesis and Claim. A hypothesis is never sufficient proof for `RESOLVED`.
- Keep synthetic fixture data and production adapter logic separated. Do not leak ground-truth labels into inference prompts.
- Never commit secrets, user identifiers, network captures, models, `runs/`, or virtual environments.
- Signed checkpoints are trusted local READ-only evidence caches, not job journals or authorizations. Never accept checkpoint files/keys from HTTP or LLM input.
- Respect frozen benchmark manifests. Any new evaluation must have a distinct version and reproducible metadata.

## Required validation
```bash
python -m scripts.check_project
python -m unittest discover -s tests -v
```
- Add contract/negative-path tests for new interfaces; verify wrong targets, missing permissions, malformed responses, timeouts, and stale facts.
- Run end-to-end replay smoke tests when changing Router, Resolver, Runner or Answer Composer.
- Record the CI run URL and explain any skipped/unavailable checks before calling a change complete.

More detailed instructions: [Developer Guide](docs/DEVELOPER_GUIDE.md) and [Docs index](docs/INDEX.md).

- A model may nominate typed READ goals only via bounded, audited proposals. Never pass model-proposed arbitrary Functions, permissions, execution adapters or network targets to a tool.
- All diagnostic READY execution must go through `graph_v3.execution_kernel.execute_ready_once` and `GraphRunner.step`; no independent tool-call shortcut for Fastpath, Resolver or ReAct.

- RCA labels require a declared Claim evaluated TRUE with verified, scoped, fresh evidence IDs. An observation-only Claim or a measurement RESOLVED status is not causal root-cause proof.

- Cloud delegation defaults disabled. Share only verified aggregated gateway numeric telemetry with server-side consent and fixed budget; never elevate a cloud hypothesis into evidence or execute returned instructions.

- Optional signed READ-only job journals must fail closed on integrity/binding/append errors; do not classify an unaudited execution as a durable success. WRITE and exactly-once remote effects are explicitly outside this pilot.

- The isolated WRITE transaction controller is disabled by default and must never be called by LLM, GoalAgent, RCAAgent or Web. An approved, separately probed firmware driver and explicit operator consent are mandatory; no synthetic WRITE may claim router support.

- Device acceptance must be substantiated by OpenWrt hardware/firmware hash, board-backed Ubus outputs and measured CPU/RAM/NPU; GitHub Ubuntu host metrics do not count.
- Do not claim 22 executable skills or 270 Functions: actual v0.1 registry contains 8 skills and 17 Functions. Use the traceability audit for per-requirement progress.
- LLM and embedding quality must use independent dev/test splits; no tuning on the final test set or relabeling illustrative data as holdout.

- A write outbox `IN_FLIGHT` row represents an in-doubt hardware side effect. Never auto-repeat a WRITE; reconciliation must use independent readback and correct operator/firmware binding.
- HTTPS Cloud service endpoints and bearer tokens must be configured by a trusted operator; deny redirects, arbitrary domains and raw client/log payload. A hypothesis is never proof.
- `TaskRuntime` is a read-only route/phase abstraction; avoid claiming all legacy business policy state machines have been replaced.
