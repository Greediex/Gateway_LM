"""Function invocation boundary. Only typed, already-gated Function calls reach here.

The legacy replay format is maintained for reproducibility. Non-replay adapter
backends must return complete observations; synthetic multi-output envelopes
must never silently bypass an explicitly configured adapter.
"""
from __future__ import annotations

import copy

from ..core import PlanError, execute


class InvocationExecutor:
    """Collect raw observations; do not decide whether they prove a claim."""

    def collect(self, runner, function, arguments: dict, state):
        case = runner.case
        live = "live_reader" in case
        # The adapter is a trusted service, not mutable replay input.
        local_case = case if live else {
            key: value if key == "adapter" else copy.deepcopy(value)
            for key, value in case.items()
        }
        response = {} if live else local_case["world"].get(function.id, {})
        simulated_ms = response.pop("_duration_ms", 0) if isinstance(response, dict) else 0
        adapter = case.get("adapter")
        if len(function.outputs) == 1:
            observation = (
                adapter.call(function.id, arguments, state, local_case) if adapter is not None
                else execute(function.id, arguments, state, local_case, runner.registry.legacy)
            )
            if not isinstance(observation, dict):
                raise PlanError("adapter_invalid_observation")
            return [observation], simulated_ms
        if live or adapter is not None:
            # The current adapter API returns one Observation. Never fabricate
            # missing outputs from the replay world for an assigned backend.
            raise PlanError("multi_output_adapter_contract_required")
        if not isinstance(response, dict):
            raise PlanError("replay_invalid_multi_output_envelope")
        outputs = response.get("outputs")
        if not isinstance(outputs, dict) or set(outputs) != set(function.outputs):
            raise PlanError("replay_multi_output_mismatch")
        observations = []
        # One typed invocation; independent evidence records for each output port.
        state.attempts[function.id] += 1
        runner.state.executed.append({"function_id": function.id, "arguments": arguments})
        for name, port in function.outputs.items():
            value = copy.deepcopy(outputs[name])
            if not isinstance(value, dict):
                raise PlanError("replay_invalid_output_value")
            status = value.pop("_status", "OK")
            age = value.pop("_age_s", 0)
            target = value.pop(
                "_target",
                runner.state.gateway_id if port.scope == "gateway"
                else arguments.get("client_id", value.get("client_id", "unresolved")),
            )
            evidence = {
                "id": "e" + str(len(runner.state.evidence) + 1),
                "function_id": function.id,
                "port": name,
                "scope": port.scope,
                "target": target,
                "source": "synthetic_replay/v3",
                "age_s": age,
                "ttl_s": runner.ttl_seconds(function),
                "status": status,
                "value": value,
                "observed_at": runner.state.observed_at(),
            }
            runner.state.evidence.append(evidence)
            observations.append(evidence)
        return observations, simulated_ms
