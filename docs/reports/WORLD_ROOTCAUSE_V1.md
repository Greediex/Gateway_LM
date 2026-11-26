# WORLD-01 incident replay and root-cause ordering

Measured on 2026-11-26 with Python 3.12.3 and the EVAL-01 scorer. The before
run used `v2` at `6d61d52`. The after run used the WORLD-01 worktree over
that commit. Both runs used the same 151 dev descriptions, with the model
disabled. The paired stage took up to three proposed cards per trial and ran
the same selection in the incident and `normal` sessions through Core.
The after run supplied the proposed replay pin through an in-memory test
operator approval. The test split was outside this measurement.

```bash
.venv-graph/bin/python -m scripts.eval_triage --split dev --incidents
```

The dev split SHA-256 was
`78e27c627a80d6447b2e705328d7d7cd903d5dfcfc587ffebf06536dc41f6076`.

| Metric | Before | After |
| --- | ---: | ---: |
| Dev top-1 / top-3 / top-6 | 14/132 · 27/132 · 41/132 | 14/132 · 27/132 · 41/132 |
| Group hits | 0/136 | 0/136 |
| Case–world trials from 42 descriptions | 45 | 45 |
| Incident FAULT with evidence | 7/45 (15.6%) | 7/45 (15.6%) |
| Incident HEALTHY / UNKNOWN / no cards | 34 / 2 / 2 | 33 / 3 / 2 |
| Normal false FAULT | 0/45 | 0/45 |
| Normal HEALTHY / UNKNOWN / no cards | 43 / 0 / 2 | 43 / 0 / 2 |
| Core READ calls per arm | 258 | 258 |

Seven evidenced FAULTs came from bufferbloat (3/4 trials), sticky client (3/4)
and weak signal (1/4) in both runs. One overheat trial selected L07, N02 and F02.
It changed to UNKNOWN because L07 requires a two-gateway snapshot and this
world has one. The paired normal trial stayed HEALTHY. The selected cards
were identical across all 45 trials. The incident FAULT rate remains limited
by which checks those cards run. See the all-Skill measurement for the wider
fault coverage. [Incident consistency matrix](INCIDENT_WORLD_CONSISTENCY_V1.md)

## Aggregation

The curated relations prioritize high queue delay ahead of latency and
jitter, channel crowding ahead of airtime congestion, and selection of a
weak AP ahead of its low RSSI symptom. The WAN relations put a verified
missing default route ahead of upstream unreachability and the iGate Internet
status. These directions are ordering rules for the modeled incidents. They do not attribute a real causal
mechanism. An edge participates only when both endpoint Claims are TRUE
and their proofs are current in selected FAULT results. Findings without a
matching edge retain the ordinary finding label.

In the HTTP role-play regression, choosing G01 before G06 still displayed the
verified bufferbloat Claim under “Nguyên nhân chính” and latency under
“Hệ quả/liên quan”. G06's suggested steps appeared before G01's. Running G01
alone, or expiring G06's proof before aggregation, removed G06 and the ordering
labels. Selecting O07 alone put its default-route checks before general WAN
advice. The EVAL-01 FAULT metric measures evidenced severity and does not
score cause ranking. Its synthetic labels still await human review.

## Reproduction and approval

| Arm | Local scorer output | Incident scenario pin |
| --- | --- | --- |
| Before | `runs/triage_eval_v1_dev_20261126T074800466491Z.json` | `52e01c6f94ac66fed6204e5de3ce34e5251ef5230c130dfed4ccd3a3a1702ed5` |
| After | `runs/triage_eval_v1_dev_20261126T080451385018Z.json` | `3d52f59586cb170bff1ae421c5dad1cf87e6508943e53d2b97aad1245bb2cece` |

`.venv-graph/bin/python -m scripts.prepare_replay_sim_approval` printed the
after pin. The other nine replay approval values matched the operator file.
The relation table used for ordering has SHA-256
`808dde7cfeff1ac0c74d3c1506454e75232671e599b894bbc4bbfdd649140a2f`.
Deployed Replay requires operator approval of the proposed pin. The local
run used synthetic READ data. Device behavior, repair and real root-cause
accuracy remain unmeasured.
