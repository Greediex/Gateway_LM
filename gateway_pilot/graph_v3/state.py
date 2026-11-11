"""Versioned evidence state with a clock, target, schema and provenance checks.

GATEWAY_DESIGN (T7): three levels kept apart - observation (evidence record),
verified fact (declared assertion over usable evidence, scoped router_*/client_*)
and hypothesis (advisor text, never a fact). Contract C is exported from here.
"""
import copy
import math
import time
from datetime import datetime, timedelta, timezone
from collections import Counter
from uuid import uuid4
from ..core import State
from .contracts import Truth, validate

REPLAY_EPOCH = "2026-11-07T00:00:00Z"


class CaseState(State):
    def __init__(self, case, registry, clock=time.monotonic):
        super().__init__(copy.deepcopy(case["target"]), set(case.get("capabilities", registry.functions)))
        self.registry, self.clock = registry, clock
        self.probe_capabilities = set(case.get("capabilities", ()))
        self.permissions = set(case.get("permissions", ["network.read", "system.read"]))
        self.boot_id = case.get("boot_id", "simulated-boot-1")
        self.config_version = case.get("config_version", "simulated-config-1")
        self.gateway_id = case.get("gateway_id", "gateway_01")
        self.case_id = case.get("case_id") or case.get("id")
        if self.case_id is None:
            self.case_id = uuid4().hex if getattr(registry, "contract_format", None) == "v0.1" else "case"
        self._client_target = None
        self._targeted_clients = False
        self.hypotheses = []
        self._revision, self._fact_values = 0, None
        self._epoch = datetime.fromisoformat(case.get("observed_epoch", REPLAY_EPOCH).replace("Z", "+00:00"))
        self._started = clock()
        for evidence in case.get("initial_evidence", []):
            e = copy.deepcopy(evidence)
            self.evidence.append(e)
            self.record(e)
        self.refresh_revision()  # revision 0 = the facts the Case starts with

    def record(self, evidence):
        # Supersede an older observation of the same adapter/port/target, while
        # keeping independent producers' immutable proofs for explicit bindings.
        for old in self.evidence:
            if (old is not evidence and not evidence.get("_invalidated") and
                    all(old.get(k) == evidence.get(k) for k in ("port", "function_id", "target"))):
                old["_invalidated"] = True
        evidence.setdefault("_received_at", self.clock())
        evidence.setdefault("boot_id", self.boot_id)
        evidence.setdefault("config_version", self.config_version)

    def for_target(self, target):
        view = copy.copy(self)
        view.target = copy.deepcopy(target)
        view._client_target = target["client_id"]
        view.attempts = Counter()
        return view

    def allowed(self, function):
        if getattr(self.registry, "contract_format", None) == "v0.1":
            safe = (self.registry.contract_allowed(function) and
                    (function.risk != "PROBE" or function.id in self.probe_capabilities))
        else:
            safe = function.risk == "READ"
        return (function.id in self.capabilities and function.id in self.registry.legacy.functions and safe and
                function.permission in self.permissions)

    def by_id(self, evidence_id, port):
        e = next((x for x in self.evidence if x["id"] == evidence_id), None)
        return e if e is not None and self.usable(e, port) else None

    def usable(self, e, port):
        if (e.get("_invalidated") or e.get("status") != "OK"
                or not str(e.get("source", "")).startswith(port.provenance)):
            return False
        checks = self.validator(e, port)
        return checks["fresh"] and checks["schema"] and checks["target"]

    def validator(self, e, port):
        """The HTML validator triple; usable() additionally needs status OK, provenance, not invalidated."""
        return {"schema": self._schema_ok(e, port), "target": self._target_ok(e, port), "fresh": self._fresh(e)}

    def _fresh(self, e):
        if e.get("boot_id") != self.boot_id or e.get("config_version") != self.config_version:
            return False
        age, ttl = e.get("age_s", 0), e.get("ttl_s", 0)
        if not isinstance(age, (int, float)) or not isinstance(ttl, (int, float)):
            return False
        return (math.isfinite(age + ttl) and age >= 0 and ttl > 0 and
                age + self.clock() - e.get("_received_at", self.clock()) <= ttl)

    @staticmethod
    def _schema_ok(e, port):
        return e.get("status") != "PARSE_ERROR" and validate(e.get("value"), port.schema)

    def _target_ok(self, e, port):
        if e.get("scope") != port.scope:
            return False
        if port.scope == "gateway":
            return e.get("target") == self.gateway_id
        if self._client_target is not None and e.get("target") != self._client_target:
            return False
        if self._targeted_clients and self.target.get("scope") == "gateway":
            return False
        if port.name == "client.identity":
            identity = e.get("value", {}).get("client_id") if isinstance(e.get("value"), dict) else None
            return bool(identity) and e.get("target") == identity and self.target.get("client_id", identity) == identity
        identity = self.fact("client.identity")
        return identity is not None and e.get("target") == identity["value"]["client_id"]

    def fact(self, name, port=None):
        port = port or self.registry.ports.get(name)
        if port is None:
            return None
        # A newer failure/invalidated observation supersedes an older value.
        e = next((x for x in reversed(self.evidence) if x.get("port") == name and not x.get("_scope_mismatch") and
                  (port.scope != "client" or self._client_target is None or
                   x.get("target") == self._client_target)), None)
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

    # T7 evidence layer ---------------------------------------------------------

    def observed_at(self):
        """Wall time from the injected clock (replay epoch + elapsed case time)."""
        moment = self._epoch + timedelta(seconds=max(0.0, self.clock() - self._started))
        return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def set_environment(self, *, boot_id=None, config_version=None):
        """A reboot or config change makes every earlier observation UNKNOWN."""
        self.boot_id = boot_id or self.boot_id
        self.config_version = config_version or self.config_version

    @property
    def fact_assertions(self):
        declared = getattr(self.registry, "fact_assertions", None)
        if declared is None:
            from .registry_v01 import default_fact_assertions
            declared = self.registry.fact_assertions = default_fact_assertions(self.registry.ports)
        return declared

    def fact_table(self):
        """Declared facts over usable evidence: TRUE / FALSE / UNKNOWN with evidence ids."""
        table = {}
        for assertion in self.fact_assertions:
            evidence = self.fact(assertion.predicate.port)
            table[assertion.fact] = {"value": assertion.predicate.evaluate(self).value,
                                     "evidence": [evidence["id"]] if evidence is not None else [],
                                     "scope": assertion.scope, "port": assertion.predicate.port}
        return table

    def refresh_revision(self):
        values = {name: row["value"] for name, row in self.fact_table().items()}
        if self._fact_values is not None and values != self._fact_values:
            self._revision += 1
        self._fact_values = values
        return self._revision

    @property
    def state_revision(self):
        return self.refresh_revision()

    def add_hypothesis(self, statement, *, source="advisor"):
        """Advisor output is kept as an untested hypothesis, never as evidence or a fact."""
        hypothesis = {"id": "h" + str(len(self.hypotheses) + 1), "statement": str(statement),
                      "source": source, "status": "UNTESTED"}
        self.hypotheses.append(hypothesis)
        return hypothesis

    def assertions_for(self, e):
        port = self.registry.ports.get(e.get("port"))
        if port is None or not self.usable(e, port) or self.fact(e["port"], port) is not e:
            return []
        return [{"fact": a.fact, "value": a.predicate.evaluate(self).value}
                for a in self.fact_assertions if a.predicate.port == e["port"]]

    def evidence_record(self, e):
        """HTML evidence record for one observation (target as {kind, id})."""
        port = self.registry.ports.get(e.get("port"))
        validator = e.get("validator_result") or (self.validator(e, port) if port else
                                                  {"schema": False, "target": False, "fresh": False})
        return {"evidence_id": e["id"], "case_id": e.get("case_id", self.case_id),
                "skill_context": e.get("skill_context"), "function_id": e.get("function_id"),
                "source": e.get("source"), "target": {"kind": e.get("scope"), "id": e.get("target")},
                "observed_at": e.get("observed_at"), "ttl_seconds": e.get("ttl_seconds", e.get("ttl_s")),
                "raw": copy.deepcopy(e.get("value")), "validator": validator,
                "assertions": e.get("assertions", self.assertions_for(e))}

    def case_status(self, goals, *, exhausted=False, blocked=False):
        """HTML terminal states over goal ports; CONTINUE while measurement is still possible."""
        if blocked:
            return "BLOCKED"
        missing = [g for g in goals if g in self.registry.ports and self.fact(g) is None]
        if not missing:
            return "RESOLVED"
        client_missing = [g for g in missing if self.registry.ports[g].scope == "client"]
        target_known = bool(self.target.get("client_id") or self.target.get("selector")
                            or self.fact("client.identity") is not None)
        if client_missing and not target_known:
            return "NEEDS_INPUT"
        eligible = self.registry.eligible(self)
        measurable = [g for g in missing
                      if any(fid in eligible for fid in self.registry.hf.producers(self.registry.ports[g]))]
        if measurable and not exhausted:
            return "CONTINUE"
        gateway_proof = any(self.fact(g) is not None for g in goals
                            if g in self.registry.ports and self.registry.ports[g].scope == "gateway")
        if len(client_missing) == len(missing) and gateway_proof:
            return "PARTIAL"
        return "INCONCLUSIVE"

    def export_contract_c(self, goals=(), *, exhausted=False, blocked=False):
        """Contract C (evidence layer -> planner). Hypotheses are never part of facts."""
        table = self.fact_table()
        outstanding = []
        for goal in goals:
            if goal in self.registry.ports and self.fact(goal) is None:
                named = [name for name, row in table.items() if row["port"] == goal]
                outstanding.extend(named or [goal])
        status = self.case_status(goals, exhausted=exhausted, blocked=blocked)
        decision = status
        if status == "CONTINUE" and outstanding and all(
                self.registry.ports[g].scope == "client" for g in goals
                if g in self.registry.ports and self.fact(g) is None):
            decision = "CONTINUE_OR_REQUEST_CLIENT_PROBE"
        return {"case_id": self.case_id, "state_revision": self.state_revision,
                "facts": {name: {"value": row["value"], "evidence": row["evidence"]} for name, row in table.items()},
                "outstanding_questions": list(dict.fromkeys(outstanding)), "decision": decision}

    def public(self):
        return {"target": self.target, "evidence": [{k: v for k, v in e.items() if not k.startswith("_")}
                                                     for e in self.evidence],
                "recent_errors": self.errors[-3:], "executed": self.executed}
