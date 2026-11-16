# CAT-01 acceptance — 16/11/2026

**Base:** `52c7ed0b96fc32bb8629ad85af58a56380bd3891`, branch `v2`.
[Guide/review](../skill_expansion/CAT01_PROFILES.md), [machine-readable coverage](CAT01_PROFILE_COVERAGE_20261116.json), [plan](../superpowers/plans/2026-11-16-cat-01-profiles.md).

## Delivered

- Complete cross-file audit of 120 mappings: 8 legacy references, 72 direct READ proposals, 40 composite/workflow entries.
- First versioned metadata profile: B02/B03/B05, design domain B, gateway scope, synthetic backend descriptor. Exact 3 Function/3 Port/3 Skill versions, nine contract hashes, complete source-bundle digest and synthetic target policy.
- Strict bounded JSON input and official v0.2 validator/builder, deterministic metadata artifact with execution disabled. No Core/Runner changes or backend/probe calls.
- Coverage/gap report separates declared, selected, current-profile replay-verified and live-verified counts. Current-profile bindings/replay/live remain 0; 72 historic individual smokes are separate evidence.
- Typed supplier/consumer witness review for all 203 proposed edges; all remain NOT_APPLIED/runtime_approved=false. B05→B06 produces_for lacks declared consumer input, so cannot create an execution dependency.

## Verified results

| Check | Result |
|---|---|
| New profile tests | **14/14 pass** |
| Full regression | **688 total: 683 pass, 5 skip, 0 failures/errors**, 70.871 seconds |
| Official selected registry build | PASS; 3/3/3 selected metadata records, PROPOSED, execution_enabled=false |
| Determinism | Repeated builds identical bytes and identical reports |
| Mapping gaps | 5 missing client identity dependencies; 9 cross-scope composites; 40 workflow/Claim gaps; 72 missing approved deployment bindings; 8 legacy migration gaps |
| Existing individual synthetic Core smokes | 72/72 pass, not a new-profile runtime acceptance |
| Legacy WAN/client replay smoke | CLI exit 0, valid JSON |
| Existing tracked data/benchmark SHA256 checks | 27/27 unchanged, including imported proposal source data |
| v0.1 Function golden digests | 17/17 unchanged |
| Upstream bootstrap | Pinned commits/source hashes verified in fresh checkout |
| Independent review | 14 focused tests independently passed; no confirmed blockers |
| Project/docs/whitespace checks | PASS |

Tests deny duplicate/missing/foreign mapping, self-granted runtime flags, dangling Function refs, inconsistent scopes, ambiguous Function versions, incorrect selection/version/hash/source, mixed scope, real-target policy, unresolved client identity, unapproved graph policy, missing dependency/completion, live provenance and executable backend fields. Pinning the profile artifact hash still cannot compile PROPOSED metadata into executable runtime.

```bash
python -m scripts.skill_profiles > runs/cat01-coverage.json
python -m unittest tests.test_skill_profiles -v
python -m scripts.check_project
python -m unittest discover -s tests -v
python -m scripts.core_replay_smoke_v2 --synthetic-only --all
```

## Boundaries

The five skips require Windows and are unchanged on the Linux host. No real device, router, firmware, WRITE, RF metric or NPU acceptance was attempted. Current live Linux profile and existing Skill graph/runtime behavior are unchanged.

CAT-01 is metadata/profile selection. Deployment/lifecycle approvals, persistent shared replay runtime/CaseState and bindings belong to CAT-02; user launcher belongs to CAT-03. The new JSON profile descriptor is not operator approval or a capability attestation.

Local generated logs/artifacts remain ignored under `runs/cat-01/`. The committed coverage snapshot is reproducible from source/profile; runtime metadata artifact remains under runs. Hosted CI is verified against the pushed commit and its exact URL is reported separately after push.
