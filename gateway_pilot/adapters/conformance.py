"""READ binding checks only: samples are not CaseState facts or capabilities."""
from __future__ import annotations

import math
import copy
import time
from datetime import UTC, datetime

from .bindings import BindingSelection, TargetContext, backend_matches, require
from .results import ToolResult
from ..core import PlanError
from ..command_catalog.contracts import _json_value
from ..command_catalog.loader import canonical_bytes, digest
from ..graph_v3.contracts import validate


def _check_result(result, function: dict, ports: dict, binding: dict,
                  context: TargetContext, now: datetime) -> str:
    require(isinstance(result, ToolResult) and not result.is_error, "tool_result_error_or_type")
    rows = result.observations
    require(len(rows) == len(function["outputs"]), "output_count_mismatch")
    _json_value(list(rows))
    require(len(canonical_bytes(list(rows))) <= 65536, "sample_byte_limit")
    required = {"id", "function_id", "function_version", "metadata_function_digest", "port", "scope",
                "target", "environment_id", "source", "status", "value", "observed_at", "age_s", "ttl_s"}
    require(all(required <= row.keys() for row in rows), "observation_fields")
    require(all(type(row["port"]) is str and type(row["id"]) is str
                and 1 <= len(row["id"]) <= 128 for row in rows), "observation_identity")
    require({row["port"] for row in rows} == set(function["outputs"])
            and len({row["id"] for row in rows}) == len(rows), "output_set_or_duplicate_id")
    for row in rows:
        require(row["function_id"] == function["function_id"] and row["function_version"] == function["version"]
                and row["metadata_function_digest"] == digest(function), "observation_contract_pin")
        require((row["scope"], row["target"], row["environment_id"])
                == (context.scope, context.target_id, context.environment_id), "observation_context")
        require(row["status"] == "OK" and row["source"] == binding["source"], "observation_status_or_source")
        port = ports[row["port"]]
        require(type(row["source"]) is str and row["source"].startswith(port["provenance"])
                and validate(row["value"], port["schema"]), "output_schema_or_provenance")
        if context.scope == "client" and "client_id" in row["value"]:
            require(row["value"]["client_id"] == context.target_id, "output_client_identity")
        require(type(row["age_s"]) in (int, float) and type(row["ttl_s"]) in (int, float)
                and 0 <= row["age_s"] <= function["ttl_seconds"]
                and row["ttl_s"] == function["ttl_seconds"]
                and math.isfinite(row["age_s"] + row["ttl_s"]), "observation_ttl")
        require(type(row["observed_at"]) is str and len(row["observed_at"]) <= 64, "observation_time_type")
        try:
            observed = datetime.fromisoformat(row["observed_at"])
            require(observed.tzinfo is not None, "observation_time_zone")
            age = (now - observed).total_seconds()
        except ValueError as exc:
            raise PlanError("binding_v02:invalid_observation_time") from exc
        require(0 <= age and row["age_s"] + age <= function["ttl_seconds"], "stale_or_future_observation")
    return digest(list(rows))


def _backend_call(method, *arguments):
    try:
        return method(*arguments)
    except TimeoutError as exc:
        raise PlanError("binding_v02:backend_timeout") from exc
    except Exception as exc:
        # Backend exception strings may contain device payload or identifiers.
        raise PlanError("binding_v02:backend_failure") from exc


class ConformanceHarness:
    """Explicit operator READ checks, not diagnostic execution or attestation.

    Trusted backends must bound their own I/O. Elapsed checks reject late
    results; they cannot preempt arbitrary Python or a stuck kernel syscall.
    """
    def __init__(self, selection: BindingSelection, *, clock=time.monotonic,
                 wall_clock=lambda: datetime.now(UTC)):
        require(isinstance(selection, BindingSelection) and callable(clock) and callable(wall_clock), "harness_configuration")
        self._selection, self._clock, self._wall_clock = selection, clock, wall_clock

    def check(self, binding_id: str, arguments: dict, context: TargetContext,
              permissions: frozenset[str]) -> dict:
        start = self._clock()
        reason, sample_digest, source = "conformance_pass", None, None
        try:
            binding, function, ports, backend = self._selection.checked_binding(binding_id, context, permissions)
            source = binding["source"]
            _json_value(arguments)
            require(type(arguments) is dict and len(canonical_bytes(arguments)) <= 4096
                    and validate(arguments, function["arguments_schema"]), "invalid_arguments")
            if "client_id" in arguments:
                require(context.scope == "client" and arguments["client_id"] == context.target_id, "argument_target")
            require(_backend_call(backend.supports, function["function_id"], context) is True, "backend_unsupported")
            result = _backend_call(backend.sample, copy.deepcopy(function), copy.deepcopy(arguments), context)
            require(_backend_call(backend.supports, function["function_id"], context) is True, "backend_lost_support")
            require(backend_matches(backend, binding, function), "backend_changed_during_sample")
            elapsed = (self._clock() - start) * 1000
            require(0 <= elapsed <= function["timeout_ms"], "backend_timeout")
            sample_digest = _check_result(result, function, ports, binding, context, self._wall_clock())
        except PlanError as exc:
            reason = str(exc).split(":", 1)[-1]
        return {"protocol": "binding-conformance/v1", "binding_id": binding_id,
                "status": "CONFORMANT" if sample_digest is not None else "REJECTED", "reason": reason,
                "source": source, "sample_digest": sample_digest,
                "execution_enabled": False, "evidence_admitted": False}
