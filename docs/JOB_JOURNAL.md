# Signed read-only job journal — durable execution *audit* pilot

`ReadOnlyJobJournal` persists a bounded, HMAC-chained list of
`(revision, node, state, reason)` transitions recorded **after** read-only
`GraphRunner.step()` and before returning control to the planner.

The journal is written to a trusted local directory using atomic replace,
file mode `0600`, fsync and SHA-256 keyed HMAC over each entry and its
predecessor. It binds records to registry Function/Port digests, request hash,
goal set, case, gateway/client target, boot/config revision and ACL.

A restarted process verifies the complete chain before further work. A
mismatched context, invalid signature, truncated/rewritten entries or event
budget failure **aborts** rather than silently hiding an audit problem.
The journal does not store raw request text, evidence values or tool arguments.

```python
from pathlib import Path
from gateway_pilot.graph_v3.job_journal import ReadOnlyJobJournal
from gateway_pilot.graph_v3.checkpoint import EvidenceCheckpoint
from gateway_pilot.graph_v3.goal_agent import GoalAgent

journal = ReadOnlyJobJournal(Path(".gateway_state/run-01.json"), secret)
facts = EvidenceCheckpoint(Path(".gateway_state/facts-01.json"), secret)
agent = GoalAgent(registry, journal=journal, checkpoint=facts)
```

**Recovery semantics:**

1. `EvidenceCheckpoint` optionally restores only still-fresh verified facts.
2. `ReadOnlyJobJournal` verifies previous step receipts and exposes history.
3. The Agent recompiles the missing **READ-only** work and may safely
   re-execute a measurement if evidence expired. It never resumes a RUNNING
   Action or independently replays a WRITE.
4. Journal failure stops the GoalAgent execution path even when a READ
   already occurred; it cannot be treated as a successful audited run.

**Not yet durable distributed execution:** This is not an exactly-once
outbox, remote device transaction log, anti-rollback secure monotonic counter,
encrypted audit store, distributed scheduler or a reconciliation mechanism for
post-crash side effects. Local HMAC prevents undetected *modification*, but a
malicious party with write access could replace a valid journal with an older
complete valid snapshot. Protection against this requires trusted external
anchoring. No router/NPU or long-running hardware workload was tested.

```bash
python -m unittest tests.graph_v3.test_job_journal -v
```
