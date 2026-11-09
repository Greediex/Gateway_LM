"""Versioned evidence state with a clock, target, schema and provenance checks."""
import copy
import math
import time
from ..core import State
from .contracts import validate


class CaseState(State):
    def __init__(self, case, registry, clock=time.monotonic):
        super().__init__(copy.deepcopy(case["target"]), set(case.get("capabilities", registry.functions)))
        self.registry, self.clock = registry, clock
        self.permissions = set(case.get("permissions", ["network.read", "system.read"]))
        self.boot_id = case.get("boot_id", "simulated-boot-1")
        self.config_version = case.get("config_version", "simulated-config-1")
        self.gateway_id = case.get("gateway_id", "gateway_01")
        for evidence in case.get("initial_evidence", []):
            e = copy.deepcopy(evidence)
            self.evidence.append(e)
            self.record(e)

    def record(self, evidence):
        # Supersede an older observation of the same adapter/port/target, while
        # keeping independent producers' immutable proofs for explicit bindings.
        for old in self.evidence:
            if old is not evidence and all(old.get(k) == evidence.get(k) for k in ("port", "function_id", "target")):
                old["_invalidated"] = True
        evidence.setdefault("_received_at", self.clock())
        evidence.setdefault("boot_id", self.boot_id)
        evidence.setdefault("config_version", self.config_version)

    def allowed(self, function):
        return (function.id in self.capabilities and function.id in self.registry.legacy.functions and function.risk == "READ" and
                function.permission in self.permissions)

    def by_id(self, evidence_id, port):
        e = next((x for x in self.evidence if x["id"] == evidence_id), None)
        return e if e is not None and self.usable(e, port) else None

    def usable(self, e, port):
        if (e.get("_invalidated") or e.get("status") != "OK" or e.get("boot_id") != self.boot_id
                or e.get("config_version") != self.config_version or e.get("scope") != port.scope
                or not str(e.get("source", "")).startswith(port.provenance)):
            return False
        age, ttl = e.get("age_s", 0), e.get("ttl_s", 0)
        if not isinstance(age, (int, float)) or not isinstance(ttl, (int, float)):
            return False
        if not math.isfinite(age + ttl) or age < 0 or ttl <= 0 or age + self.clock() - e.get("_received_at", self.clock()) > ttl:
            return False
        if not validate(e.get("value"), port.schema):
            return False
        if port.scope == "gateway":
            return e.get("target") == self.gateway_id
        if port.name == "client.identity":
            identity = e["value"].get("client_id")
            return bool(identity) and e.get("target") == identity and self.target.get("client_id", identity) == identity
        identity = self.fact("client.identity")
        return identity is not None and e.get("target") == identity["value"]["client_id"]

    def fact(self, name, port=None):
        port = port or self.registry.ports.get(name)
        if port is None:
            return None
        # A newer failure/invalidated observation supersedes an older value.
        e = next((x for x in reversed(self.evidence) if x.get("port") == name), None)
        return e if e is not None and self.usable(e, port) else None

    def completed(self, function, *, exact_producer=False):
        facts = [self.fact(name, port) for name, port in function.outputs.items()]
        return bool(facts) and all(
            fact is not None and (not exact_producer or fact["function_id"] == function.id)
            for fact in facts
        )

    def invalidate(self, evidence_ids):
        for e in self.evidence:
            if e["id"] in evidence_ids:
                e["_invalidated"] = True

    def public(self):
        return {"target": self.target, "evidence": [{k: v for k, v in e.items() if not k.startswith("_")}
                                                     for e in self.evidence],
                "recent_errors": self.errors[-3:], "executed": self.executed}
