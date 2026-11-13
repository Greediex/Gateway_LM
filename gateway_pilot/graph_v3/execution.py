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
        adapter = case.get("adapter")
        if getattr(runner.registry, "contract_format", None) == "v0.2":
            runtime = getattr(runner.registry, "runtime", None)
            if runtime is None or adapter is not runtime:
                raise PlanError("v02_requires_trusted_runtime_adapter")
        # The adapter is a trusted service object; no fixture data can supply
        # or complete an adapter's missing outputs.
        local_case = case if live else {
            key: value if key == "adapter" else copy.deepcopy(value)
            for key, value in case.items()
        }
        if adapter is not None:
            from ..adapters.results import ToolResult
            result = adapter.call(function.id, arguments, state, local_case)
            if isinstance(result, ToolResult):
                if result.is_error:
                    raise PlanError("adapter_reported_error:" + result.error_code)
                return list(result.observations), 0
            if len(function.outputs) == 1 and isinstance(result, dict):
                # Existing one-observation Adapter API remains supported.
                return [result], 0
            raise PlanError("adapter_typed_result_required")
        if len(function.outputs) == 1:
            # Preserve the legacy synthetic duration used by timeout/repair
            # fixtures. This value is meaningful ONLY without an Adapter.
            replay = local_case.get("world", {}).get(function.id, {})
            simulated_ms = replay.get("_duration_ms", 0) if isinstance(replay, dict) else 0
            observation = execute(function.id, arguments, state, local_case, runner.registry.legacy)
            if not isinstance(observation, dict):
                raise PlanError("adapter_invalid_observation")
            return [observation], simulated_ms
        if live:
            raise PlanError("live_requires_explicit_adapter_contract")
        # Synthetic multi-output replay is allowed only when no adapter is
        # configured; the envelope is not a substitute for a real backend.
        response = copy.deepcopy(local_case.get("world", {}).get(function.id, {}))
        if not isinstance(response, dict):
            raise PlanError("replay_invalid_multi_output_envelope")
        simulated_ms = response.pop("_duration_ms", 0)
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
