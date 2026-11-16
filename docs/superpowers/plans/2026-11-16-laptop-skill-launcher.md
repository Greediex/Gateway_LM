# Laptop-first Skill launcher — shared sessions + CLI/API/UI

**User direction:** “hoàn thiện đi” clarified to “chạy trên laptop trước”. Real local Linux measurements take priority; synthetic fixtures never fill unavailable live measurements.
**Goal:** Complete laptop Skill selection/execution with scoped shared Core sessions, truthful 120-design catalog coverage and CLI/Web test flow. Preserve CAT-01 source proposals and existing live/replay behavior.

## Design / rulings
- Extend ReadRuntime with a bounded reusable session (CaseState + GraphRunner + shared execution kernel); no separate Runner or direct tool bypass. Expired/context/permission/binding/contract changes fail closed; facts reused only when fresh, scoped and verified.
- Commit separate reviewed live deployment/catalog for laptop actions, exact artifact/binding implementation pins. Source 72 PROPOSED contracts remain unchanged. Add live A08 association contract v2 using actual BSSID/association (not inferred router telemetry).
- Offer six namespaced laptop READ actions plus exact local SK01 identity and A08 association mappings. The 120 design rows remain visible with per-Skill reasons. Gateway/SNR/history/composite capabilities absent on laptop remain UNAVAILABLE; do not relabel them fulfilled.
- Keep first gateway synthetic profile explicitly replay-only. Its committed deployment is opt-in, reviewed, context-bound and cannot become a laptop live fallback.
- Operator-owned mode/profile/target/backend; HTTP accepts only bounded IDs/session handle, no permissions/paths/targets/functions/commands. Session limits, expiry, lock and max capacity.

## Tasks
- [x] Shared Core session API + mutation/TTL/budget/reuse tests.
- [x] Separate laptop and first-batch replay deployment metadata, pin config, live provider and explicit action registry.
- [x] Application catalog/availability/session service, verified result snapshots and clear unsupported reasons.
- [x] CLI and local HTTP endpoints, existing Web catalog launcher with loading/stale/error/isolation behavior.
- [x] Real laptop acceptance, full regression/frozen hashes, visual QA and independent review.
- [ ] Update README/TODO/acceptance with actual coverage, push v2 and verify exact CI; leave test server ready.
