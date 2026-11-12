# Bounded LLM goal proposal and shared execution kernel (pilot)

## Boundary: LLM proposes, Registry decides

`gateway_pilot/graph_v3/llm_goals.py` introduces an **opt-in** proposal
stage, not an LLM executor. The trusted model implements
`local_only=True` and `propose_goals(request, catalog)`. No remote model,
provider SDK or network transport is shipped.

Untrusted model output is required to be exactly:

```json
{
  "goals": ["wan.status"],
  "confidence": 0.93,
  "spans": {"wan.status": "nghẽn kết nối"},
  "needs_clarification": false
}
```

The proposed port must be registered and supported by an authorized
read-only Function. The cited span must occur in the request. Uncertain,
unsupported, malformed, ungrounded or mixed-WRITE proposals return
`NEEDS_INPUT` or `BLOCKED`, **with zero Function calls**.

The model receives only allowlisted port names and static descriptions,
not raw logs or private network evidence. This is a *bounded proposal API*:
confidence is model-reported and not calibrated. Exact request spans make
audit possible but do **not** independently prove semantic correctness;
unfamiliar high-risk or ambiguous requests must still ask the user.

```python
from gateway_pilot.graph_v3.llm_goals import BoundedGoalProposer
from gateway_pilot.graph_v3.goal_agent import GoalAgent

# Trusted startup only, not an HTTP parameter.
planner = BoundedGoalProposer(approved_local_model)
agent = GoalAgent(versioned_registry, method="bm25",
                  goal_proposer=planner)
# agent.run("nghẽn kết nối", trusted_case)  # if deterministic routing cannot select
```

The legacy `GoalAgent` behavior is unchanged when no proposer is installed.
For an explicit output-port `goals=` call the LLM is not invoked.
The model is a fallback only after deterministic decomposition and calibrated
`route_turn` do not return an executable plan. This does not magically
support unregistered tasks or WRITE.

## Shared execution kernel

`execution_kernel.execute_ready_once` is a single READY-node admission
and dispatch path shared by `orchestrator.run_plan` (used by fastpath/
ReAct evidence acquisition and GoalAgent) and `Diagnostic.run_resolver`.
It applies the caller's validated policy ranking, then invokes the *same*
GraphRunner with permission, capability, schema, target, budget, repair and
EvidenceVerifier checks. Retrieval trace is recorded before the call so even
execution failures preserve selection audit.

**Not claimed:** identical state machines for all policies, generic LLM
execution, production crash recovery, or hardware validation. End-to-end
replay compatibility and negative-path tests are required.

```bash
python -m unittest tests.graph_v3.test_llm_goals -v
python -m unittest tests.graph_v3.test_execution_kernel -v
python -m unittest discover -s tests -v
```

## Real local LLM adapter and calibration

`OllamaGoalModel` validates the local Ollama model via `/api/show`, uses structured JSON response, and never creates Function IDs. A trusted operator can pass it into `BoundedGoalProposer`. Use `python -m scripts.analysis.evaluate_goal_proposals --model qwen3:0.6b --input /trusted/labeled_goal_holdout.jsonl --output runs/goal_model_eval.json` on a host with an actual downloaded model. The harness checks dev/test separation, picks a threshold using **dev only**, and reports precision/coverage/unsafe acceptances on untouched test. If no safe threshold exists, evaluation fails closed. The bundled `examples/evaluation/illustrative_goal_proposals.jsonl` only illustrates the format.
