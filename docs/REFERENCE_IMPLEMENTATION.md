# Gateway LM — external reference alignment and bounded goal execution

Implementation status: **pilot, synthetic replay unless a verified Adapter is
explicitly assigned**. This review distinguishes ideas taken from upstream,
code actually used, and work still missing. Historical results were not rerun
or relabeled. This is not a reproduction of the referenced benchmarks.

## Repository comparison

| Reference | Verified approach | Gateway LM implementation | Deliberate limitation |
| --- | --- | --- | --- |
| [Graph of Skills (GoS)](https://github.com/davidliuk/graph-of-skills) | Offline dependency graph; hybrid lexical/semantic seeds; graph reranking and dependency-aware skill bundles | Pinned PPR kernel in `graph_v3/upstream.py`; lexical seeds, typed membership, reranking in `graphs.py` | No semantic embedding or full paper pipeline, no claim of GoS benchmark parity |
| [SkillDAG](https://github.com/Ericbai06/SkillDAG) | Typed Skill dependencies/conflicts; proposal/commit of graph changes backed by execution | Pinned SkillDAG inference/check functions in `skilldag.py`; guarded graph edits in `graphs.py` | No automatic learning from execution evidence or autonomous graph write permissions |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Explicit graph state, bounded cycles and durable checkpoints | Separate stages and DAG revision history; optional existing ReAct runtime | No durable checkpoint/resume after process crash |
| [AutoGen GraphFlow](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/graph-flow.html) | Conditional, directed execution with fan-out and joins | Typed DATA/STATE/ORDER edges, READY scheduling, dependency closure and bounded local/global repair | No asynchronous parallel executor or cross-node distributed scheduling |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Tool input/output schemas, structured output, explicit error status | Internal `ToolResult` envelope and per-output verification, error and evidence isolation | Not an MCP server/client and no external plugin discovery |

Do not copy external files without checking original license and pinned version.
The existing pinned upstream commits and their hashes remain unchanged.

## Changes implemented in this iteration

1. **ToolResult**: an explicit typed success/error envelope for Adapters.
   Success contains nonempty structured observations. Error has a bounded
   `error_code` and **zero** successful observations. A legacy one-output
   Adapter may still return its existing observation dict.
2. **Multi-output Function**: one Adapter call can return a `ToolResult` with
   exactly the declared output ports. Missing/extra ports, duplicate IDs,
   foreign Function IDs and invalid types fail closed. Synthetic replay can
   no longer make up missing output ports for an assigned Adapter.
3. **Evidence admission**: outputs from a fresh Adapter are appended to
   CaseState only after exact shape and ID collision checks. Gateway stamps
   receipt time/boot/config metadata; Adapter cannot forge freshness.
   The verifier still validates schema, target/scope, provenance, TTL and
   status. Tool success never automatically becomes a diagnosis.
4. **GoalAgent**: a new opt-in runtime path using `Compiler` + `GraphRunner`
   and the existing GoS/BM25 READY scheduler. Accepts multiple registered
   goal ports **without a fixed Workflow ID**, compiles typed dependencies,
   verifies each output and attempts bounded replanning on failures.
   `--registry v01` with goals omitted delegates intent selection to the
   existing gated `route_turn()`; uncertain/unsupported requests do not
   execute. Explicit user-requested goal IDs must be in the Registry.
5. **Backend capability probe before planning**: GoalAgent intersects
   declared Case capabilities with the assigned Adapter's probed status.
   An unassigned Function cannot fall back to a synthetic replay world.

6. **Web API**: `POST /api/goals` là giao diện replay-only gọi GoalAgent từ HTTP mà không cho phép client inject `world`, backend, permissions hay Function tùy ý. `POST /api/chat` vẫn giữ nguyên. Xem [Web UI guide](WEB_UI.md).

## How to run

From the repository root after Python 3.12 setup and `setup_upstream.py`:

```bash
python -m gateway_pilot.graph_v3.goal_agent \
  --fixture GLM-04-0 \
  --request "Inspect WAN and memory" \
  --goals wan.status system.resources \
  --method bm25

python -m unittest tests.graph_v3.test_tool_result -v
python -m unittest tests.graph_v3.test_goal_agent -v
python -m unittest discover -s tests -v
```

To try calibrated intent inference on **supported** catalog workflows:
`python -m gateway_pilot.graph_v3.goal_agent --registry v01 --request
"Kiểm tra đường WAN giúp tôi" --fixture GLM-04-0`.

**Important:** `status=RESOLVED` on this API means all requested *measurement
ports* have fresh supporting evidence. `diagnosis=NOT_EVALUATED` explicitly
means no root-cause claim has been generated or verified. This distinction is
intentional, not a missing output field.

## What is still not complete

- General user goals cannot be executed unless they match a supported Workflow
  or a typed, registered output port with a working probe/Adapter.
- OpenWrt Ubus functions, firmware-specific permissions, write approvals,
  real network RCA and device latency/NPU memory measurements need hardware.
- Cloud delegation, durable state checkpoints, semantic retrieval, model-based
  task decomposition, production observability and large-scale cross-domain
  tests remain separate implementation work.
- The existing `/api/chat` and Assistant paths retain their semantics; `/api/goals` is an **opt-in read-only endpoint** and GoalAgent is also available via CLI. This is not a drop-in replacement for all policies.
- For new capabilities, add versioned Function contracts and conformance
  tests before advertising or routing them. Do **not** infer an executable
  Function from one of the 270 product requirements.
