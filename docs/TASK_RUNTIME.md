# Unified read-only TaskRuntime — staged orchestration (pilot)

`gateway_pilot/graph_v3/task_runtime.py` offers one typed application
contract for **measurement** (`GoalAgent`) and **diagnosis** (`RCAAgent`).
Both already use the same `GraphRunner`, `READY` selector, adapter,
capability/ACL checks, and evidence verifier.

```text
TaskRequest
  → RECEIVED (type/size)
  → ROUTED (MEASURE or DIAGNOSE, no WRITE)
  → EXECUTED (common GraphRunner kernel)
  → VERIFIED (EvidenceVerifier / ClaimBook)
  → TERMINAL (RESOLVED measurement or verified RCA)
```

```python
from gateway_pilot.graph_v3.task_runtime import TaskRuntime, TaskRequest
from gateway_pilot.graph_v3.graphs import GraphRegistry

agent = TaskRuntime(GraphRegistry.from_v01(), method="bm25")

# Known, trusted fixture / measured CaseState source only.
result = agent.run(
    TaskRequest("Check WAN", mode="MEASURE", goals=("wan.status",)),
    trusted_case,
)
# result["diagnosis"] is ALWAYS None for MEASURE.

result = agent.run(
    TaskRequest("Why is WAN down?", mode="DIAGNOSE", workflow="WF-018"),
    trusted_case,
)
# RCA output requires all Claim predicates proven by fresh evidence.
```

`AUTO` uses trusted *typed* fields: if `workflow` is given, DIAGNOSE;
otherwise MEASURE and GoalAgent's bounded routing. It never turns free text
into an arbitrary workflow, Function or WRITE operation. Mixed WRITE text
is blocked before running any READ Function.

**Limitations:** This unifies the read-only *entrypoint and phase trace*;
the older `diagnose()` fastpath/ReAct/Resolver business policies still
contain separate terminal logic. Migrating those completely, while
preserving baseline diagnoses and session behavior, remains an open task.
No public HTTP endpoint is exposed for TaskRuntime; the trusted service
must provide the Case source and policy.

```bash
python -m unittest tests.graph_v3.test_task_runtime -v
```
