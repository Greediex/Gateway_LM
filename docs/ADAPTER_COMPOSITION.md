# Composite Adapter — extensible Function dispatch

This first refactor is intentionally narrow and backward compatible.
It does **not** implement OpenWrt firmware Functions, general Task DAGs, or Cloud execution.

## What changes

`CompositeAdapter` implements the existing `Adapter` interface and
dispatches each Function ID to a single explicitly assigned backend.

```python
from gateway_pilot.adapters import CompositeAdapter, OpenWrtUbusAdapter

# Example only: OpenWrtUbusAdapter is still a skeleton; all its probes fail.
backend = OpenWrtUbusAdapter()
adapter = CompositeAdapter({"wan.status": backend, "wan.routes": backend})
```

Use trusted startup configuration to construct assignments, never user/model
text. An unassigned Function must not be available even if a backend advertises it.

## Invariants

- Only explicitly assigned Function IDs can be probed or called.
- One ID maps to one backend; there is no silent fallback.
- Missing, malformed or failing probes fail closed.
- Capability is rechecked at call time.
- The runner still validates arguments, permissions, scope and evidence.
- No dynamic shell execution or arbitrary plugin loader is introduced.

## Tests

```bash
python -m unittest tests.graph_v3.test_composite_adapter -v
python -m unittest discover -s tests -v
```

## Next changes (separate PRs)

1. Normalize multi-output ToolResult and remove replay-specific logic from GraphRunner.
2. Connect read-only, independently probed OpenWrt Function implementations.
3. Unify Fastpath/Resolver/ReAct execution and repair.
4. Add firmware-specific capability catalogs and adapter conformance tests.
