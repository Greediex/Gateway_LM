# CAT-01 — Skill mapping and first READ profile

**Goal:** Validate all 120 design mappings, select a reproducible scope-local metadata batch and report gaps without granting runtime capability.
**Spec:** ../../NEXT_ROADMAP_V2.md CAT-01.
**Design:** Reuse official v0.2 validator/builder and dependency indexes. New skill_expansion/profiles.py audits cross-file mapping and validates a pinned profile against the complete source bundle. First profile selects gateway Wi-Fi B02/B03/B05; 5 client proposals remain explicitly blocked on missing identity dependency. No graph proposal is promoted to execution and no backend/probe is called.

- [x] Implement strict bundle/mapping audit and exact profile/version/digest/scope/dependency checks.
- [x] Commit config/skill_profiles/wifi_gateway_replay_v1.json: 3 Skills, 3 Functions, 3 Ports, synthetic backend descriptor, no runtime approvals.
- [x] Add scripts/skill_profiles.py CLI to build metadata artifact + print deterministic coverage/gap report.
- [x] Add negative tests for duplicate/missing/foreign/ambiguous mappings, version/digest/source drift, scope/identity/provenance and unapproved edge policy.
- [x] Run focused/full regression, source hashes and replay; review metadata decisions and update TODO/docs/report.
- [x] Push v2 and verify CI for exact commit. Runtime/session and launcher stay CAT-02/CAT-03.
