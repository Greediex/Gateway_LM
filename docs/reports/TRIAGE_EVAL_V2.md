# Triage evaluation V2

TRIAGE-02 was developed with the 151 dev requests from the frozen triage_eval_v1
corpus. The final deterministic run scored the locked 99-case test split once
and emitted aggregate rows only. Automated integrity and leakage checks compare
both splits without exposing test requests. Labels are AI-drafted and await
human review. See the [V1 baseline](TRIAGE_EVAL_V1.md).

Dev top-three hits rose from **27/132 to 126/132**. Locked-test top-three hits
fell from **13/80 to 10/80**, and top-six hits fell from 20/80 to 11/80.
Locked-test refusal recall rose from 3/19 to 16/19, with **41 false refusals**
among requests that had acceptable Skills. The dev-tuned classifier showed
limited transfer to unseen wording in this corpus.

## Changes and dev miss analysis

- V1 returned zero taxonomy-group hits. Indirect and story requests often
  described effects across several details, while the original taxonomy matched
  whole phrases. V2 also matches combinations of short, reusable symptom cues.
- The V1 top-three hit counts for no-diacritics, teencode and typos were
  4/19, 2/13 and 4/24 on dev. V2 folds Vietnamese accents, normalizes Wi-Fi
  spellings, and expands reviewed abbreviations and typos at token boundaries.
- Mixed requests had 5/15 top-three hits in V1. V2 interleaves eligible READ
  cards from matched groups. All expected groups appeared in 8/15 mixed dev
  requests, up from 0/15. For a curated pair with disjoint cards and similar
  scores, the server can offer a clarifying question when the clauses do not
  describe independent symptoms. The Web chips resubmit the original request
  and one offered group in the same session.
- V1 explicitly refused 3/19 dev requests that required refusal. V2 gives a
  scope-specific response for unsupported topics and recognizes more change
  requests before catalog retrieval. Intake still makes zero diagnostic READ
  calls. Running selected cards uses the existing Core and Verifier.

## Deterministic results

Each arrow compares V1 with V2. The three top-k cells give hit counts over the
eligible denominator in the preceding column. Top-k and group hit credit **any**
acceptable Skill or expected group. They give no credit for covering an
additional symptom once a hit is recorded. Refusal precision and recall include
V2's new explicit unsupported-topic stop. A dash denotes a zero denominator.
Latency covers the triage call and excludes session creation, replay execution
and report writing. V1 and V2 dev measurements had other local processes
running, so differences in latency are descriptive.

### Dev

| Style | Cases / eligible | Top-1 / Top-3 / Top-6 hits | Any group | Refusal precision | Refusal recall | No card | Median / p95 / max ms |
|---|---|---|---|---|---|---|---|
| all | 151 / 132 | 14/27/41 → 123/126/129 | 0/136 → 123/136 | 3/5 → 19/21 | 3/19 → 19/19 | 5/151 → 21/151 | 34.57 / 40.13 / 43.09 → 30.34 / 52.12 / 63.19 |
| indirect | 30 / 28 | 4/5/8 → 26/26/27 | 0/30 → 27/30 | 0/1 → 2/3 | 0/2 → 2/2 | 1/30 → 3/30 | 35.41 / 41.67 / 43.09 → 31.15 / 53.31 / 55.90 |
| mixed | 15 / 15 | 2/5/7 → 14/15/15 | 0/15 → 14/15 | — → — | — → — | 0/15 → 0/15 | 33.09 / 38.49 / 38.49 → 24.27 / 39.66 / 39.66 |
| no_diacritics | 19 / 19 | 2/4/7 → 15/16/17 | 0/19 → 13/19 | 0/1 → 0/1 | — → — | 1/19 → 1/19 | 34.38 / 39.81 / 39.81 → 31.81 / 52.12 / 52.12 |
| off_topic | 6 / 0 | — → — | — → — | — → 6/6 | 0/6 → 6/6 | 0/6 → 6/6 | 32.08 / 35.25 / 35.25 → 23.11 / 45.48 / 45.48 |
| story | 35 / 33 | 4/7/10 → 32/32/33 | 0/35 → 33/35 | — → 2/2 | 0/2 → 2/2 | 0/35 → 2/35 | 35.23 / 41.93 / 42.08 → 31.54 / 56.63 / 63.19 |
| teencode | 13 / 13 | 1/2/3 → 13/13/13 | 0/13 → 13/13 | — → — | — → — | 0/13 → 0/13 | 34.20 / 38.30 / 38.30 → 40.26 / 56.27 / 56.27 |
| typo | 24 / 24 | 1/4/6 → 23/24/24 | 0/24 → 23/24 | — → — | — → — | 0/24 → 0/24 | 34.38 / 38.78 / 38.98 → 30.41 / 50.11 / 56.96 |
| write_request | 9 / 0 | — → — | — → — | 3/3 → 9/9 | 3/9 → 9/9 | 3/9 → 9/9 | 31.14 / 36.31 / 36.31 → 2.28 / 2.57 / 2.57 |

### Locked test

| Style | Cases / eligible | Top-1 / Top-3 / Top-6 hits | Any group | Refusal precision | Refusal recall | No card | Median / p95 / max ms |
|---|---|---|---|---|---|---|---|
| all | 99 / 80 | 6/13/20 → 6/10/11 | 0/84 → 3/84 | 3/4 → 16/57 | 3/19 → 16/19 | 5/99 → 57/99 | 34.33 / 39.64 / 44.45 → 11.11 / 22.28 / 41.19 |
| indirect | 20 / 20 | 3/5/6 → 2/2/2 | 0/20 → 0/20 | — → 0/10 | — → — | 0/20 → 10/20 | 35.09 / 41.18 / 42.40 → 12.93 / 20.74 / 22.53 |
| mixed | 5 / 5 | 0/0/0 → 1/1/1 | 0/5 → 1/5 | — → 0/3 | — → — | 0/5 → 3/5 | 34.69 / 38.45 / 38.45 → 11.01 / 22.47 / 22.47 |
| no_diacritics | 6 / 5 | 0/1/2 → 0/1/1 | 0/6 → 0/6 | — → 0/2 | 0/1 → 0/1 | 0/6 → 2/6 | 33.78 / 34.81 / 34.81 → 14.80 / 19.37 / 19.37 |
| off_topic | 9 / 0 | — → — | — → — | — → 8/8 | 0/9 → 8/9 | 0/9 → 8/9 | 34.52 / 44.45 / 44.45 → 9.72 / 15.38 / 15.38 |
| story | 15 / 15 | 0/1/3 → 1/2/3 | 0/15 → 1/15 | — → 0/5 | — → — | 0/15 → 5/15 | 35.33 / 39.57 / 39.57 → 20.17 / 41.19 / 41.19 |
| teencode | 12 / 11 | 0/1/1 → 0/0/0 | 0/12 → 0/12 | — → 1/12 | 0/1 → 1/1 | 1/12 → 12/12 | 33.84 / 39.15 / 39.15 → 10.11 / 12.09 / 12.09 |
| typo | 26 / 24 | 3/5/8 → 2/4/4 | 0/26 → 1/26 | 0/1 → 2/12 | 0/2 → 2/2 | 1/26 → 12/26 | 33.89 / 38.92 / 39.44 → 15.16 / 21.70 / 22.13 |
| write_request | 6 / 0 | — → — | — → — | 3/3 → 5/5 | 3/6 → 5/6 | 3/6 → 5/6 | 17.62 / 37.38 / 37.38 → 0.99 / 14.99 / 14.99 |

## Optional local model on dev

Ollama 0.40.16 served `qwen3:4b` on `127.0.0.1:11434`. The model uses seed 42,
temperature 0 and a maximum 15-second advisory budget bounded by the current
turn and session. The Web server opts in with `GATEWAY_LM_TRIAGE_MODEL=1` and
asks the model only for weak or ambiguous intake. The model can select from
offered group, card and curated-question IDs. Validation failures, timeouts
and resource contention return the deterministic result. The evaluation used
the actual local model and fresh replay sessions.

| Style | Cases / eligible | Top-1 / Top-3 / Top-6 hits | Any group | Accepted / fallback | Median / p95 / max ms |
|---|---|---|---|---|---|
| all | 151 / 132 | 123/126/129 | 123/136 | 1 / 22 | 29.98 / 14054.62 / 14229.01 |
| indirect | 30 / 28 | 26/26/27 | 27/30 | 1 / 3 | 30.34 / 14042.57 / 14051.89 |
| mixed | 15 / 15 | 14/15/15 | 14/15 | 0 / 2 | 23.20 / 14063.97 / 14063.97 |
| no_diacritics | 19 / 19 | 15/16/17 | 13/19 | 0 / 6 | 35.90 / 14065.48 / 14065.48 |
| off_topic | 6 / 0 | — | — | 0 / 0 | 17.28 / 22.58 / 22.58 |
| story | 35 / 33 | 32/32/33 | 33/35 | 0 / 4 | 30.17 / 14050.96 / 14068.94 |
| teencode | 13 / 13 | 13/13/13 | 13/13 | 0 / 3 | 32.76 / 14229.01 / 14229.01 |
| typo | 24 / 24 | 23/24/24 | 23/24 | 0 / 4 | 30.39 / 14061.38 / 14067.97 |
| write_request | 9 / 0 | — | — | 0 / 0 | 1.48 / 2.10 / 2.10 |

The model returned a valid selection on **1/23** advised requests. The
remaining 22 used deterministic fallback at roughly 14 seconds. The attempted
subset took 14048.85 / 14068.94 / 14229.01 ms (median / p95 / max).
Dev top-three and group hits stayed at 126/132 and 123/136, respectively.
Refusal counts were identical. The Qwen path was evaluated on dev only.

## Paired deterministic dev replay

The same protocol as V1 used 42 dev descriptions over 14 synthetic incident
worlds and matched `normal` controls. Each of 45 pairs ran up to the first three
cards through Core with an identical selection on both sides.

| Outcome | V1 incident | V1 normal | V2 incident | V2 normal |
|---|---:|---:|---:|---:|
| FAULT with fresh, verified fault-Skill evidence | 7 | 0 | 35 | 0 |
| HEALTHY | 34 | 43 | 5 | 43 |
| UNKNOWN | 2 | 0 | 3 | 0 |
| No cards, no execution | 2 | 2 | 2 | 2 |
| READ calls through Core | 258 | 258 | 193 | 189 |

Across all 45 pairs, evidenced FAULT rose from **7/45 to 35/45**.
False FAULT on normal was **0/45**, with 43 controls executed. This checks
whether a Skill returned a verdict supported by its fresh synthetic evidence.
Causal diagnosis, device behavior and repair are outside this evaluation.

## Limitations and reproducibility

- Dev wording informed the cues, so locked-test results are the estimate of
  transfer to unseen requests from this synthetic corpus. Families are shared
  across splits and the per-style denominators can be small.
- Deterministic triage triggered clarification for 0/151 dev
  and 0/99 test requests. HTTP and Web presentation
  tests exercise the chip flow. The corpus measures first-turn cards and does
  not measure users' answers or improvement after clarification. Card
  coverage is capped at six and the question table covers selected pairs.
- Missed and false refusals remain visible in the tables. The heuristic is
  sensitive to phrasing and historical descriptions of changes. The parser
  and model provide suggestions for the operator and supply no evidence.

All runs used Linux, Python 3.12.3 from `.venv-graph`, and the runtime in the
commit containing this report. The JSON outputs record parent Git revision
`85e93d0737cf3dcd01076d9fe5d55a5a48bf9649` because the gate ran before the local commit.
Both dataset SHA-256 values match the frozen split metadata. All 10 fields
printed by `scripts.prepare_replay_sim_approval` matched the existing approval.

```bash
.venv-graph/bin/python -m scripts.eval_triage --split dev --incidents
GATEWAY_LM_CHAT_MODEL=qwen3:4b .venv-graph/bin/python -m scripts.eval_triage --split dev --with-llm
.venv-graph/bin/python -m scripts.eval_triage --split test
```

- Deterministic dev output is `runs/triage_eval_v2_dev_20261126T072618148033Z.json`.
- Model-assisted dev output is `runs/triage_eval_v2_dev_20261126T073139867334Z.json`.
- Deterministic test output is `runs/triage_eval_v2_test_20261126T073628394343Z.json`.
- Dev SHA-256 is `78e27c627a80d6447b2e705328d7d7cd903d5dfcfc587ffebf06536dc41f6076`.
- Test SHA-256 is `ca02bf8a29b1e1500d663118cd4e4c35a6f98ea44689f70c4596fffb3cb2bf40`.
- Qwen model digest is `359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7`.
- This commit was created locally. The recorded CI baseline covers prior
  commit `a7f97d8`. [GitHub Actions](https://github.com/Greediex/Gateway_LM/actions/runs/44705437165)

Local verification finished with **1,164 passes**, zero failures and five
Windows-only skips across 1,169 tests. Repository hygiene and both Node checks
passed. The simulation scorer passed 303/303 Skill scenarios and 21/21
incident checks.
