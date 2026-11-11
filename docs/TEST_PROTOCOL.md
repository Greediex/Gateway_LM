# Locked test protocol — Gateway LM pilot v1

Locked before the first test-split model run on 2026-11-07. Development-only traces are in `runs/dev_*`; several exploratory runs were interrupted deliberately. They are not part of the primary result.

- Model: `qwen3:1.7b`, GGUF Q4_K_M downloaded through local Ollama. Ollama reports `general.parameter_count=2031739904` (2.032B, strictly below 3B); marketing tag and actual artifact count are both recorded. Model family, digest and runtime metadata are saved with the run.
- Why this model: a readily available sub-3B Qwen model with local inference. Existing Qwen2.5-1.5B was tried on dev and showed poor action/citation compliance. Model choice is engineering exploration, not an exhaustive best-model search.
- No fine-tuning, no cloud advisor, no remote router access. Existing command-mapper code is unchanged.
- Dataset: 72 hand-authored synthetic replay cases, 24 templates × 3 variants. Variant 0 is dev. Variants 1/2 are 48 test cases. Template and underlying fault families are shared, so this is not an independent real-world holdout. Workflow IDs are supplied, not predicted.
- Five arms: rules, flat, retrieval, graph, graph_batch. Same scenarios and paired scoring. Rotate arm execution order by case to spread warm-up bias.
- Primary endpoint: exact `(action, diagnosis)` matches adjudication, with agent self-termination within budget and no runtime error. Core-forced INCOMPLETE is not counted as autonomous success, even when terminal labels match.
- Secondary endpoints: raw proposal rejections, unsupported FINISH, exact outcome match including forced stops, tool/decision counts, prompt/output tokens, end-to-end and per-call latency; per-workflow errors. There is no subjective prose-grading model.
- Inference: `think=false`, temperature 0, seed 42, 8192 context, max 180 generated tokens/call; JSON syntax mode. No label/action enum constraints, no automatic correction to a gold answer.
- Limits: 10 model/rule decisions, 12 simulated function calls; each tool at most twice; three identical rejected proposals stop the case. Request timeout 120 seconds.
- Baseline retrieval: joint Skill/Function BM25 top-4, soft membership affinity. Graph arm adds explicit missing goal evidence ports and backward dependency closure, and auto-executes prerequisites for the selected Function. No learned GNN/PPR/evolution is claimed.
- All arms share capability/argument/scope gates and evidence/FINISH validator. Graph batch has a different analyst prompt because Core has already collected its evidence bundle; it measures division of responsibility, not a pure retrieval ablation.
- Scorer reads gold after the episode. Model prompt construction whitelists request, workflow/checklist, target, normalized observations and exposed contracts. Canary tests verify no world/gold/ID/template leakage.
- Run output is a fresh directory, with per-episode raw JSONL, source snapshot, source/data hashes, metadata, generated summary and Vietnamese report. Do not change prompt/fixtures/Core based on test results and silently combine runs.
- Statistics: paired success deltas, bootstrap confidence intervals clustered by template (4000 resamples, fixed seed); case-level exact McNemar p-values are exploratory because test variants share templates. No generalization or SOTA claims.

The test is expected to reveal failures. Poor model behavior is a result, not a reason to discard a test case or replace a failed verdict with a rules answer.
