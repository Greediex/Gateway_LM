# Authenticated evidence checkpoint (read-only pilot)

This opt-in local feature lets the `GoalAgent` reuse **verified, unexpired
read-only observations** after a process restart. It does **not** persist
running jobs, uncommitted actions, tool-side effects, or WRITE commands.

## Example (trusted Python host only)

```python
import os
from pathlib import Path
from gateway_pilot.graph_v3.checkpoint import EvidenceCheckpoint
from gateway_pilot.graph_v3.goal_agent import GoalAgent
from gateway_pilot.graph_v3.graphs import GraphRegistry

# Generate a random 32+ byte secret once and store it in a protected keystore.
# Never commit, print, log or accept it from a client request.
secret = bytes.fromhex(os.environ["GLM_CHECKPOINT_KEY_HEX"])
checkpoint = EvidenceCheckpoint(
    Path(".gateway_state/verified-evidence.json"), secret
)
agent = GoalAgent(GraphRegistry(), method="bm25", checkpoint=checkpoint)
# result = agent.run(request, trusted_case, goals=("wan.status",))
```

The file is stored with mode `0600` and written by an atomic replace. The
HMAC-SHA256 signature protects integrity, **not confidentiality**. Host
filesystem permissions and encryption-at-rest are still necessary when
handling private data. The signing key is separate from the checkpoint file.

Restore is rejected or skipped if:

- signature, file format, registry ports or Function digests changed;
- request, goal set, case ID, gateway, client target or ACL changed;
- boot ID/config revision changed or the observation's TTL elapsed;
- observation's Function, typed port, source, schema or scope fails validation;
- system clock moved backwards by more than one second.

Untrusted text (e.g. `system.logs`) is deliberately never persisted.
The cache **never** grants extra capabilities or substitutes a failed Adapter.
A revived process re-plans unfinished READ work from the restored facts; the
previous call counter, retries and outstanding actions are **not** restored.

The Web `/api/goals` endpoint does not accept checkpoint paths or secrets.
Enabling automatic checkpointing in Web requires an authenticated trusted
server-side configuration and privacy review.

Tests: `python -m unittest tests.graph_v3.test_checkpoint -v`.
