# Evidence-driven RCA — adaptive read-only pilot

`gateway_pilot/graph_v3/rca_agent.py` implements a bounded loop:

```text
Supported DIAGNOSE Workflow
  → ClaimBook tri-state predicates (TRUE/FALSE/UNKNOWN)
  → rank missing evidence ports across still-possible fault Claims
  → Type/permission/target/probe-gated DAG planning
  → shared READY execution → EvidenceVerifier → CaseState
  → re-evaluate Claims after each verified batch
  → VERIFIED_FAULT / MULTIPLE_FAULTS / HEALTHY_OBSERVED / INCONCLUSIVE
```

**No evidence, no diagnosis.** A root cause label is emitted only for a
declared Claim whose complete requirement predicates evaluate TRUE on fresh,
scoped and schema-valid observations. The result carries supporting
`evidence_ids`, per-Claim tri-state results, selected evidence goals, plan
revisions and tool call traces. A positive fault Claim stops further probes to
avoid unnecessary reads; this is a scoped fault pattern, **not** proof of an
underlying causal mechanism.

The system refuses catalog-only/CHANGE workflows. Missing client identity,
insufficient capability/ACL, missing device data, unassigned firmware backend
and exhausted call budgets remain `NEEDS_INPUT` or `INCONCLUSIVE`. An
observation Claim (`severity=OBSERVATION`) is not promoted to root cause.
`HEALTHY_OBSERVED` is only returned if a HEALTHY Claim is TRUE and no
relevant FAULT Claim is still UNKNOWN or TRUE.

Example from trusted Python (synthetic replay):

```python
from gateway_pilot.graph_v3.rca_agent import RCAAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry

result = RCAAgent(GraphRegistry.from_v01(), method="bm25").run(
    "Check WAN fault", trusted_case, workflow="WF-018"
)
```

The existing public `/api/goals` endpoint does not expose this diagnostic
mode, and `/api/chat` keeps its existing behavior. The new RCA agent is
opt-in and does not grant WRITE access or contact the cloud.

This solves **MVP evidence selection and Claim evaluation**. It does not
establish real-world RCA reliability, counterfactual reasoning, fleet
correlation or root-cause causal identification. Board-backed ground-truth
fault injection and held-out tests are still required.

```bash
python -m unittest tests.graph_v3.test_rca_agent -v
python -m unittest discover -s tests -v
```

## Web replay endpoint

`POST /api/rca` được expose trên localhost cùng `/api/goals`, nhưng luôn dùng fixture trong `data/cases.json`. Frontend input chỉ quyết định workflow có kiểu `DIAGNOSE`, phương pháp BM25/GoS và ngân sách được giới hạn; không thể cấp dữ liệu đo, quyền hay Adapter từ JSON. Xem [Web UI](WEB_UI.md).
