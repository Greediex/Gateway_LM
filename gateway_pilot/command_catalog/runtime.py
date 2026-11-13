"""Trusted READ composition root for catalog v0.2 and the shared Core kernel."""
from __future__ import annotations

import copy
import time
from datetime import UTC, datetime
from uuid import uuid4

from ..core import PlanError
from ..adapters.bindings import BindingSelection, TargetContext, backend_matches, require
from ..adapters.conformance import _backend_call, _check_result
from ..adapters.results import ToolResult
from ..application.feature_availability import CapabilitySnapshot, FunctionCapability, _hash, _permissions, _time
from ..graph_v3.contracts import validate
from ..graph_v3.execution_kernel import execute_ready_once
from ..graph_v3.planner import Compiler
from ..graph_v3.runner import GraphRunner
from ..graph_v3.state import CaseState
from .compatibility import compile_registry
from .loader import digest


class ReadRuntime:
    """Operator-owned service, never a model/request-supplied object.

    Support probes are allowlisted backend supports() calls, not measurements
    or conformance reports. Short leases permit READ execution only in this
    context. Every call rechecks support and its typed result before Verifier.
    Backends must bound their own blocking I/O; elapsed gates reject late output.
    """
    def __init__(self, artifact: dict, policy: dict, *, approved_digest: str,
                 selection: BindingSelection, context: TargetContext,
                 permissions: frozenset[str], policy_context_id: str,
                 clock=time.monotonic, wall_clock=lambda: datetime.now(UTC)):
        require(type(selection) is BindingSelection and isinstance(context, TargetContext)
                and _permissions(permissions) and _hash(policy_context_id)
                and callable(clock) and callable(wall_clock), "runtime_configuration")
        self.registry = compile_registry(artifact, policy, approved_digest=approved_digest)
        require(selection.registry_digest() == approved_digest, "runtime_selection_registry")
        self.context, self.permissions, self.policy_context_id = context, permissions, policy_context_id
        self._selection, self._clock, self._wall_clock = selection, clock, wall_clock
        self._bindings = selection.binding_ids()
        self._binding_pins = {}
        # Check context at startup without I/O, including denied permissions.
        for bid in self._bindings.values():
            binding, _, _, _ = selection.checked_binding(bid, context, frozenset({"network.read", "system.read"}))
            self._binding_pins[bid] = digest(binding)
        self._leases = {}
        self.registry.runtime = self

    def checkpoint_binding(self) -> dict:
        return {"registry_digest": self.registry.catalog_digest,
                "binding_pins": copy.deepcopy(self._binding_pins),
                "policy_context_id": self.policy_context_id,
                "environment_id": self.context.environment_id}

    def probe(self) -> CapabilitySnapshot:
        """Explicit trusted support probe. No backend samples or facts are created."""
        self._leases.clear()
        now = self._clock()
        require(_time(now), "runtime_clock")
        rows = []
        for fid, f in self.registry.functions.items():
            status = "UNVERIFIED"
            if f.permission not in self.permissions:
                status = "PERMISSION_DENIED"
            elif fid in self._bindings and self.registry.contract_allowed(f):
                try:
                    binding, metadata, _, backend = self._selection.checked_binding(
                        self._bindings[fid], self.context, self.permissions)
                    start = self._clock()
                    supported = _backend_call(backend.supports, fid, self.context)
                    require(type(supported) is bool, "invalid_support_result")
                    elapsed = self._clock() - start
                    require(_time(elapsed) and elapsed * 1000 <= f.timeout_ms, "probe_timeout")
                    require(backend_matches(backend, binding, metadata), "probe_backend_changed")
                    status = "AVAILABLE" if supported is True else "UNSUPPORTED"
                    if status == "AVAILABLE":
                        self._leases[fid] = (now, now + 30)
                except PlanError:
                    status = "TEMPORARILY_UNAVAILABLE"
            rows.append(FunctionCapability(fid, f.version, f.metadata_digest, status))
        # A slow batch must not publish expired leases as fresh capabilities.
        end = self._clock()
        require(_time(end) and now <= end < now + 30, "probe_batch_timeout")
        return CapabilitySnapshot(self.registry.catalog_digest, self.context, self.permissions,
                                  self.policy_context_id, now, now + 30, tuple(rows))

    def allowed(self, function, state) -> bool:
        lease = self._leases.get(function.id)
        now = self._clock()
        target = state.target
        expected = target.get("client_id") if self.context.scope == "client" else state.gateway_id
        return bool(lease and _time(now) and lease[0] <= now < lease[1]
                    and state.registry is self.registry and target.get("scope") == self.context.scope
                    and expected == self.context.target_id
                    and state.config_version == self.context.environment_id and state.boot_id == self.context.environment_id
                    and frozenset(state.permissions) == self.permissions
                    and self.registry.contract_allowed(function))

    def new_case(self, request: str = "READ selected catalog ports", *, case_id: str | None = None):
        """Construct scoped, empty state: no externally asserted initial evidence."""
        require(type(request) is str and 0 < len(request) <= 4096, "runtime_request")
        target = {"scope": self.context.scope}
        if self.context.scope == "client":
            target["client_id"] = self.context.target_id
        case = dict(request=request, case_id=case_id or uuid4().hex, target=target,
                    gateway_id=self.context.target_id if self.context.scope == "gateway" else "unavailable",
                    boot_id=self.context.environment_id, config_version=self.context.environment_id,
                    capabilities=list(self.registry.functions), permissions=sorted(self.permissions), adapter=self,
                    observed_epoch=self._wall_clock().isoformat())
        return case, CaseState(case, self.registry, clock=self._clock)

    def call(self, fid: str, arguments: dict, state, case) -> ToolResult:
        """InvocationExecutor adapter; callers must enter via Core READY execution."""
        function = self.registry.functions.get(fid)
        require(function is not None and state.allowed(function), "runtime_gate")
        require(type(arguments) is dict and validate(arguments, function.arguments_schema), "runtime_arguments")
        if "client_id" in arguments:
            require(arguments["client_id"] == self.context.target_id, "argument_target")
        binding, metadata, ports, backend = self._selection.checked_binding(
            self._bindings[fid], self.context, self.permissions)
        start = self._clock()
        try:
            require(_backend_call(backend.supports, fid, self.context) is True, "runtime_support_lost")
            state.attempts[fid] += 1
            state.executed.append({"function_id": fid, "arguments": copy.deepcopy(arguments)})
            result = _backend_call(backend.sample, copy.deepcopy(metadata), copy.deepcopy(arguments), self.context)
            require(_backend_call(backend.supports, fid, self.context) is True, "runtime_support_lost")
            require(backend_matches(backend, binding, metadata), "runtime_backend_changed")
            elapsed = self._clock() - start
            require(_time(elapsed) and elapsed * 1000 <= function.timeout_ms, "runtime_timeout")
            require(state.allowed(function), "runtime_context_or_lease_changed")
            now = self._wall_clock()
            _check_result(result, metadata, ports, binding, self.context, now)
            rows = copy.deepcopy(result.observations)
            for row in rows:
                # Preserve actual age when Core stamps monotonic receipt time.
                observed = datetime.fromisoformat(row["observed_at"])
                row["age_s"] += (now-observed).total_seconds()
            return ToolResult(observations=rows)
        except PlanError:
            self._leases.pop(fid, None)
            raise

    def execute(self, goals, *, request="READ selected catalog ports", max_calls=12):
        """One case, standard compiler/Runner/verifier; no workflow-specific path."""
        case, state = self.new_case(request)
        runner = GraphRunner(self.registry, case, state, max_calls=max_calls, max_repairs=0)
        plan = runner.attach(Compiler(self.registry).compile(tuple(goals), state))
        while True:
            node, _ = execute_ready_once(runner, plan, goals, ordered_ids=plan.topological())
            if node is None:
                break
        return runner, plan
