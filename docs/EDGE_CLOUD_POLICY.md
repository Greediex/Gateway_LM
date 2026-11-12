# Edge-first / Cloud hypothesis delegation (opt-in pilot)

This is a **backend-neutral policy and privacy boundary**, not a deployed
cloud integration. A trusted service may inject an `analyze(payload)` adapter;
the repository ships **no cloud API keys, provider implementation or outbound
HTTP calls**.

## Decision contract

```text
Verified Edge State
    |
    v
Can Edge finish? ─── YES ──> EDGE_ONLY
    |
    NO
    v
Purpose known? (CROSS_LAYER_RCA / FLEET_REFERENCE / LONG_CONTEXT)
    |
    v
Cloud enabled? Explicit consent? Aggregated-only privacy?
    |
    v
Trusted backend configured? Request + USD budget?
    |
    v
Share ONLY verified gateway number/bool telemetry
    |
    v
Cloud returns UNVERIFIED HYPOTHESIS
    |
    v
Edge Claim Verifier must independently gather/verify evidence
```

The `EdgeCloudPolicy` defaults to `enabled=False`, keeps a maximum number
of requests and estimated USD budget, and reserves allowance **before** a
transport call. All decision flags and consent must come from authenticated
server-side state, never model text or arbitrary HTTP fields.

The context exporter excludes raw user prompts, logs, untrusted text,
client-specific data, IP/MAC/identity, evidence IDs, configuration and
unverified data. Previously collected telemetry is not shared if the
Function permission/capability was later revoked.

`CloudHypothesisAdapter` rejects responses that are not exactly a single
bounded `hypothesis` string. Even a valid response is returned as
`HYPOTHESIS_UNVERIFIED`, **never** as a proven diagnosis, executable
Function or permission escalation.

## Explicit limitations

- No provider credentials, retry queues, billing receipts, audit store or
  production data classification.
- USD cost is a *trusted estimate*, not a measured model invoice.
- No cloud execution happens in CI; every backend is mocked.
- No autonomous cloud fallback inside GoalAgent or RCAAgent. A validated
  application must explicitly choose delegation and then separately verify
  any claimed insight at the Edge.
- Real consent UI, legal/privacy review and fleet/network datasets remain
  acceptance prerequisites.

```bash
python -m unittest tests.graph_v3.test_delegation -v
```
