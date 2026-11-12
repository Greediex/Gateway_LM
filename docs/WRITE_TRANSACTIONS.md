# Gated WRITE transaction — mock-verified pilot, disabled by default

Network configuration changes are **not** enabled through the existing
`GoalAgent`, `GraphRunner`, `/api/chat`, `/api/goals`, or `/api/rca`
paths. Those remain read-only.

The opt-in `SafeWriteTransaction` provides an isolated two-phase transaction
contract for a **trusted firmware driver** and a separately authorized
operator. It does not construct a device command or execute user-provided
scripts. No real router/firmware WRITE backend is included.

## Pipeline

```text
Trusted operator permission + approved Function allowlist
       |
       v
ApprovalAuthority.issue (HMAC, exact typed arguments + target + firmware
revision + operator + one-time nonce + 1-300s expiry)
       |
       v
SafeWriteTransaction.commit (disabled by default)
       |
       v
Signature / expiry / operator / gateway / revision / ACL / capability /
Function risk / JSON Schema / live backend probe
       |
       v
DurableApprovalLedger.consume (SQLite unique nonce, WAL + FULL sync)
       |
       v
Snapshot → Side-effect-free Preview → Apply → Read-back comparison
                                        |
                                        +-- mismatch/error --> Rollback
                                                            --> Read-back
                                                            --> ROLLED_BACK
                                                            or MANUAL_RECOVERY_REQUIRED
```

The nonce is consumed **before** any modification and remains consumed even
if the driver fails. A repeated/expired/misbound approval never executes
the same operation again. Successful completion is reported only after
the trusted driver returns a read-back state matching the intended preview.

The driver must implement `probe, snapshot, preview, apply, readback,
rollback`; it is supplied at trusted service startup. The test suite uses
a mock in-memory QoS profile driver.

### Security and acceptance limits

- `enabled=False` by default. No AI/model or frontend may access the
  approval signer, SQLite nonce database or driver methods.
- Schema controls legal arguments; the allowlist and ACL are independent of
  model output. A v0.1 Function requires separately established
  `PROBED_OK` before commit.
- The current pilot is **not** an OpenWrt implementation, distributed
  exactly-once transaction manager, or proof of hardware rollback.
- A device can reboot or lose connectivity between apply/read-back/rollback;
  real drivers require deadlines, power-failure tests, reconciliation,
  idempotent hardware receipts and an independent operator recovery path.
- SQLite approval replay protection needs a protected persistent volume;
  a compromised disk or reset token store defeats its guarantees.
- Do not enable real WRITE for QoS, firewall, DNS or client blocking until
  target firmware conformance, privilege escalation testing and hardware
  fault injection complete.

```bash
python -m unittest tests.graph_v3.test_change_transaction -v
```
