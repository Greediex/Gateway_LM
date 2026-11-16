"""Bounded, operator-owned reuse of one verified Core READ case."""
from __future__ import annotations

import copy
from threading import RLock

from ..adapters.bindings import require
from ..application.feature_availability import _time
from ..core import PlanError
from ..graph_v3.execution_kernel import execute_ready_once
from ..graph_v3.runner import GraphRunner
from .loader import digest


class ReadSession:
    """Reuse fresh Core facts without resetting cumulative execution budgets.

    This is a trusted local service object, never an HTTP evidence container.
    The public execute boundary accepts goals and descriptive text only.
    """

    def __init__(self, runtime, *, max_calls=24, ttl_s=300, max_plans=64,
                 cost_budget=100, context_valid=lambda: True):
        from .runtime import ReadRuntime
        require(type(runtime) is ReadRuntime, "session_runtime")
        require(type(max_calls) is int and 1 <= max_calls <= 4096
                and type(max_plans) is int and 1 <= max_plans <= 4096
                and _time(ttl_s) and 0 < ttl_s <= 86400
                and _time(cost_budget) and 0 < cost_budget <= 1e6
                and callable(context_valid), "session_limits")
        self.runtime = runtime
        self._lock = RLock()
        self.closed = False
        self._context_valid = context_valid
        self._max_plans = max_plans
        self.created_at = runtime._clock()
        require(_time(self.created_at), "session_clock")
        self.expires_at = self.created_at + ttl_s
        self._last_clock = self.created_at
        case, self.state = runtime.new_case()
        self.runner = GraphRunner(runtime.registry, case, self.state, max_calls=max_calls,
                                  max_repairs=0, deadline_s=ttl_s, cost_budget=cost_budget)
        self._target = copy.deepcopy(self.state.target)
        self._pins = self._configuration()
        self._validate()

    def _configuration(self):
        rt = self.runtime
        # Inspect the live selection as well as the runtime's cached pins.
        bindings = []
        for fid, bid in sorted(rt._bindings.items()):
            binding, metadata, ports, backend = rt._selection.checked_binding(
                bid, rt.context, frozenset({"network.read", "system.read"}) | rt.permissions)
            bindings.append((fid, bid, digest(binding), digest(metadata), digest(ports), id(backend)))
        return (id(rt.registry), id(rt._selection), id(rt._clock), id(rt._wall_clock),
                rt.registry.contract_format, rt.registry.gs.version, digest(rt.registry.skills),
                rt.context, rt.permissions,
                copy.deepcopy(rt.checkpoint_binding()), rt._selection.registry_digest(),
                copy.deepcopy(rt.registry._contract_pins),
                {fid: f.digest() for fid, f in rt.registry.functions.items()}, bindings)

    def close(self):
        """Invalidate all evidence; closing is idempotent and serialized."""
        with self._lock:
            self.closed = True
            self.state.invalidate({e["id"] for e in self.state.evidence})

    def _validate(self):
        try:
            require(not self.closed, "session_closed")
            now = self.runtime._clock()
            require(_time(now) and self._last_clock <= now < self.expires_at, "session_expired_or_clock")
            self._last_clock = now
            require(self._context_valid() is True, "session_context_invalid")
            require(self._configuration() == self._pins, "session_configuration_changed")
            rt, state = self.runtime, self.state
            require(state.registry is rt.registry and rt.registry.runtime is rt
                    and state.target == self._target
                    and state.boot_id == state.config_version == rt.context.environment_id
                    and frozenset(state.permissions) == rt.permissions
                    and state.gateway_id == (rt.context.target_id if rt.context.scope == "gateway" else "unavailable")
                    and self.runner.case.get("adapter") is rt, "session_state_changed")
        except Exception as exc:
            self.close()
            if isinstance(exc, PlanError):
                raise
            raise PlanError("binding_v02:session_context_check_failed") from exc

    def execute(self, goals, *, request="READ selected catalog ports"):
        """Compile each request against fresh capabilities and shared verified facts."""
        with self._lock:
            self._validate()
            require(type(request) is str and 0 < len(request) <= 4096, "runtime_request")
            require(type(goals) in (tuple, list) and 0 < len(goals) <= 256
                    and all(type(g) is str for g in goals), "session_goals")
            require(len(self.runner.plans) < self._max_plans, "session_plan_budget")
            try:
                snapshot = self.runtime.probe()
            except Exception:
                self.close()
                raise
            unavailable = {row.function_id for row in snapshot.functions if row.status != "AVAILABLE"}
            self.state.invalidate({e["id"] for e in self.state.evidence
                                   if e.get("function_id") in unavailable})
            self._validate()
            self.runner.case["request"] = request
            plan = self.runner.compiler().compile(tuple(goals), self.state)
            # The duplicate guard is per plan; only nodes that require new
            # measurements get another attempt. Runner calls/spent stay global.
            for node in plan.nodes.values():
                self.state.attempts[node.function_id] = 0
            self.runner.attach(plan)
            while True:
                self._validate()
                node, _ = execute_ready_once(self.runner, plan, goals, ordered_ids=plan.topological())
                if node is None:
                    break
            self._validate()
            return self.runner, plan
