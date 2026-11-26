# Triage evaluation v1 baseline

**AI-drafted labels, unreviewed.** Measured on 2026-11-26 against runtime
`5e7b4bd49a28d1cbe56e204461edfe551ddea268` before tuning. The corpus contains
250 synthetic Vietnamese customer descriptions. The ID hash assigned 151 to dev and
99 to test. The locked test SHA-256 is
`ca02bf8a29b1e1500d663118cd4e4c35a6f98ea44689f70c4596fffb3cb2bf40`.
The dataset includes long descriptions, indirect wording, spelling mistakes, missing
diacritics, informal abbreviations, dual symptoms, off-topic requests and requests
to perform a WRITE. Label review is tracked in the
[human review sheet](../../data/eval/triage_eval_v1/REVIEW.md).

Both runs called `SkillChat.triage` with the model disabled in fresh, approved
`replay_sim` sessions. Triage received the request text and session ID.
The evaluator joined the labels to returned cards and groups for scoring. Intake
made zero READ calls. The incident stage below made synthetic READ calls through
the existing runtime.

```bash
.venv-graph/bin/python -m scripts.eval_triage --split dev --incidents
.venv-graph/bin/python -m scripts.eval_triage --split test
```

## Triage scores

Top-*k* counts a hit when any of the first *k* cards is an acceptable Skill.
Its denominator is cases with at least one acceptable Skill. Group hit counts any
expected group among the returned groups, over cases with group labels.
Refusal precision and recall count explicit policy stops. A response without
cards counts toward the no-card rate, which uses every case in the split.
The dash denotes a zero denominator. Latencies are wall-clock median, nearest-rank
p95 and maximum for the triage call, including first-call setup inside triage.
They exclude session creation, incident execution and report writing. The two
runs overlapped on the same Linux x86-64 host with Python 3.12.3.

### dev

| Style | Cases | Top-1 | Top-3 | Top-6 | Group | Ref. precision | Ref. recall | No card | Median / p95 / max ms |
|---|---|---|---|---|---|---|---|---|---|
| all | 151 | 10.6% (14/132) | 20.5% (27/132) | 31.1% (41/132) | 0.0% (0/136) | 60.0% (3/5) | 15.8% (3/19) | 3.3% (5/151) | 34.57 / 40.13 / 43.09 |
| indirect | 30 | 14.3% (4/28) | 17.9% (5/28) | 28.6% (8/28) | 0.0% (0/30) | 0.0% (0/1) | 0.0% (0/2) | 3.3% (1/30) | 35.41 / 41.67 / 43.09 |
| mixed | 15 | 13.3% (2/15) | 33.3% (5/15) | 46.7% (7/15) | 0.0% (0/15) | — (0/0) | — (0/0) | 0.0% (0/15) | 33.09 / 38.49 / 38.49 |
| no_diacritics | 19 | 10.5% (2/19) | 21.1% (4/19) | 36.8% (7/19) | 0.0% (0/19) | 0.0% (0/1) | — (0/0) | 5.3% (1/19) | 34.38 / 39.81 / 39.81 |
| off_topic | 6 | — (0/0) | — (0/0) | — (0/0) | — (0/0) | — (0/0) | 0.0% (0/6) | 0.0% (0/6) | 32.08 / 35.25 / 35.25 |
| story | 35 | 12.1% (4/33) | 21.2% (7/33) | 30.3% (10/33) | 0.0% (0/35) | — (0/0) | 0.0% (0/2) | 0.0% (0/35) | 35.23 / 41.93 / 42.08 |
| teencode | 13 | 7.7% (1/13) | 15.4% (2/13) | 23.1% (3/13) | 0.0% (0/13) | — (0/0) | — (0/0) | 0.0% (0/13) | 34.20 / 38.30 / 38.30 |
| typo | 24 | 4.2% (1/24) | 16.7% (4/24) | 25.0% (6/24) | 0.0% (0/24) | — (0/0) | — (0/0) | 0.0% (0/24) | 34.38 / 38.78 / 38.98 |
| write_request | 9 | — (0/0) | — (0/0) | — (0/0) | — (0/0) | 100.0% (3/3) | 33.3% (3/9) | 33.3% (3/9) | 31.14 / 36.31 / 36.31 |

### test

| Style | Cases | Top-1 | Top-3 | Top-6 | Group | Ref. precision | Ref. recall | No card | Median / p95 / max ms |
|---|---|---|---|---|---|---|---|---|---|
| all | 99 | 7.5% (6/80) | 16.2% (13/80) | 25.0% (20/80) | 0.0% (0/84) | 75.0% (3/4) | 15.8% (3/19) | 5.1% (5/99) | 34.33 / 39.64 / 44.45 |
| indirect | 20 | 15.0% (3/20) | 25.0% (5/20) | 30.0% (6/20) | 0.0% (0/20) | — (0/0) | — (0/0) | 0.0% (0/20) | 35.09 / 41.18 / 42.40 |
| mixed | 5 | 0.0% (0/5) | 0.0% (0/5) | 0.0% (0/5) | 0.0% (0/5) | — (0/0) | — (0/0) | 0.0% (0/5) | 34.69 / 38.45 / 38.45 |
| no_diacritics | 6 | 0.0% (0/5) | 20.0% (1/5) | 40.0% (2/5) | 0.0% (0/6) | — (0/0) | 0.0% (0/1) | 0.0% (0/6) | 33.78 / 34.81 / 34.81 |
| off_topic | 9 | — (0/0) | — (0/0) | — (0/0) | — (0/0) | — (0/0) | 0.0% (0/9) | 0.0% (0/9) | 34.52 / 44.45 / 44.45 |
| story | 15 | 0.0% (0/15) | 6.7% (1/15) | 20.0% (3/15) | 0.0% (0/15) | — (0/0) | — (0/0) | 0.0% (0/15) | 35.33 / 39.57 / 39.57 |
| teencode | 12 | 0.0% (0/11) | 9.1% (1/11) | 9.1% (1/11) | 0.0% (0/12) | — (0/0) | 0.0% (0/1) | 8.3% (1/12) | 33.84 / 39.15 / 39.15 |
| typo | 26 | 12.5% (3/24) | 20.8% (5/24) | 33.3% (8/24) | 0.0% (0/26) | 0.0% (0/1) | 0.0% (0/2) | 3.8% (1/26) | 33.89 / 38.92 / 39.44 |
| write_request | 6 | — (0/0) | — (0/0) | — (0/0) | — (0/0) | 100.0% (3/3) | 50.0% (3/6) | 50.0% (3/6) | 17.62 / 37.38 / 37.38 |

## Paired dev incident replay

42 dev descriptions mapped to 14 existing incident worlds,
yielding 45 case–world trials. A mixed description can map to two worlds.
For each trial the evaluator opened a fresh incident session, ran triage on the
customer description, then ran up to three cards in order with `run_selected`.
It ran the identical selection in a fresh `normal` session. Two trials supplied
no cards and stayed in both denominators.

| Outcome | Incident | Normal |
| --- | ---: | ---: |
| FAULT with fresh, verified fault-Skill evidence | 7 | 0 |
| HEALTHY | 34 | 43 |
| UNKNOWN | 2 | 0 |
| No cards, no execution | 2 | 2 |
| READ calls through Core | 258 | 258 |

FAULT-with-evidence rate was **15.6% (7/45)**. False FAULT
rate on normal was **0.0% (0/45)**, with 43 controls
executed. Seven evidenced FAULTs came from three worlds.

| Scenario | Trials | FAULT with evidence |
| --- | ---: | ---: |
| INC-24G-COCHANNEL | 2 | 0 |
| INC-BUFFERBLOAT | 4 | 3 |
| INC-CAPACITY | 7 | 0 |
| INC-CGNAT | 3 | 0 |
| INC-DFS-RADAR | 2 | 0 |
| INC-DHCP-EXHAUST | 2 | 0 |
| INC-DNS-FAIL | 3 | 0 |
| INC-DOUBLE-NAT | 4 | 0 |
| INC-IPV6-BROKEN | 1 | 0 |
| INC-OVERHEAT-REBOOT | 5 | 0 |
| INC-PPPOE-MTU | 2 | 0 |
| INC-STICKY-CLIENT | 4 | 3 |
| INC-WAN-DOWN | 2 | 0 |
| INC-WEAK-SIGNAL | 4 | 1 |

## Interpretation and limits

- Baseline group emission requires a verbatim normalized taxonomy phrase. The
  corpus excludes those phrases by construction, so zero group hits describes
  the limits of the current phrase matcher on this corpus. Skill results can
  still come from catalog retrieval.
- The model was disabled. Off-topic cases received zero explicit refusals
  across both splits. WRITE refusal recall was 3/9 on dev and 3/6 on test. Those
  metrics describe intake behavior. No READ or WRITE was invoked by intake.
- Labels and incident mappings are draft annotations. The paired control
  exercises known synthetic measurements. The FAULT metric checks for evidence
  supporting a returned fault verdict. Exact claim identity, real root cause,
  repair and device behavior remain unmeasured. Some buckets are small and the
  hash split shares symptom families across dev and test.
- Local JSON outputs are `runs/triage_eval_v1_dev_20261126T070044833979Z.json` and
  `runs/triage_eval_v1_test_20261126T070043006192Z.json`. The test artifact holds aggregate and
  per-style results. It omits case-level predictions to limit feedback from the holdout.
- No CI run exists for this local change. The previous successful run covers
  upstream `v2` at `a7f97d8`.
  [GitHub Actions](https://github.com/Greediex/Gateway_LM/actions/runs/44705437165)
