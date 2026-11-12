# Gateway LM — runtime stage boundaries (PR-02)

**Status: implemented and regression-tested on synthetic replay only.**
This refactor establishes composable stage boundaries. It does **not** imply
OpenWrt production integration, general-purpose task decomposition, arbitrary
user-request execution, or successful RCA on real networks.

## Request → evidence loop

```text
Request / CaseState
      |
      v
FunctionRouter  -- Contract 0 (candidate IDs and selected Skill context)
      |
      v
FunctionPlanner -- Typed ExecutionDAG and dependency closure
      |
      v
GraphRunner     -- READY scheduler, policy/target/argument gates, bounded repair
      |
      v
InvocationExecutor --> assigned CompositeAdapter or synthetic replay
      |
      v
EvidenceVerifier --> Contract B, schema/scope/provenance/freshness, CaseState facts
      |                                                |
      +----------- observe / re-resolve / replan <------+
```

## Responsibility / implementation

| Stage | Module | Enforcement |
| --- | --- | --- |
| Function routing | `gateway_pilot/graph_v3/routing.py` | Calls existing typed Resolver; refuses unknown IDs, duplicate IDs, blocked candidates and mismatched Skill membership. |
| DAG planning | `gateway_pilot/graph_v3/planning_stage.py` | Compiles only contract-selected Functions. Compiler remains responsible for typed dependency constraints and policy. |
| Execution | `gateway_pilot/graph_v3/execution.py` | Invokes validated, explicitly assigned Functions through an adapter; synthetic multi-output replay never substitutes for an assigned backend. |
| Verification | `gateway_pilot/graph_v3/verification.py` | Requires exact expected output set; keeps tool status separate from terminal Claim; checks evidence through CaseState. |
| Lifecycle | `gateway_pilot/graph_v3/orchestrator.py`, `runner.py` | Existing budget, DAG revisions, retry, global/local repair and evidence-driven continuation remain in place. |

Only trusted startup/test code may inject a different router, planner,
executor or verifier. **Never** construct these from user/LLM input.
Never grant WRITE based on Function names or model-generated arguments.
Pending adapter-specific multi-output contracts are **fail closed** rather
than silently filled with synthetic fixture values.

## Compatibility and extension

- `acquire(case, registry, state, ...)` keeps its previous defaults and adds
  optional trusted `router` and `planner` parameters.
- `GraphRunner(...)` adds optional trusted `executor` and `verifier`
  parameters. The old `ttl_seconds`, `annotate`, `export_contract_b` methods
  remain compatibility facades.
- Add typed Functions via `registry_v01.json` and assigned Adapters, then
  add negative-path and replay tests. Do not add Function-name branches to Core.
- The dynamic ReAct and legacy policy paths have their existing execution
  semantics; this PR changes the resolver-led graph acquisition path and the
  common `GraphRunner.step()`, not every routing strategy.
- GoS/SkillDAG pins, frozen benchmark data and historical results are unchanged.

## Validation

```bash
python setup_upstream.py
python -m unittest tests.graph_v3.test_runtime_stages -v
python -m unittest discover -s tests -v
python -m scripts.benchmarks.run_dynamic_benchmark --output runs/dynamic-stage.json
```

See `AGENTS.md` for hard safety constraints. CI provides replay, HTML and
end-to-end smoke results; do not claim hardware performance from those results.

## Still planned, not implemented here

1. Typed multi-output `ToolResult` for hardware Adapters and per-port conformance.
2. OpenWrt read-only Function probes verified on actual board/firmware.
3. General Goal/Skill/Function decomposition across new workflow families.
4. Versioned Registry expansion toward 22 skills and 270 **requirements**
   (not 270 already executable Functions); zero hard-coded workflow-name branches.
5. Independent benchmarks for routing, dynamic replanning, evidence RCA,
   latency, memory and NPU use on device.

## Further implementation: structured Adapter results and registered multi-goal execution

The opt-in `ToolResult` API supports verified multiple outputs and explicit tool errors; `GoalAgent` can dynamically compile registered output goals without a hard-coded Workflow ID. Neither path claims arbitrary-task planning or production OpenWrt support. See [upstream alignment and tests](REFERENCE_IMPLEMENTATION.md).
