"""GATEWAY_DESIGN: data-driven claim contracts evaluated tri-state on Case State (C4).

Conclusion rules live in ``data/registry_v01.json`` (``claims``), not in Python.
A claim is TRUE only when every required predicate is TRUE on verified, fresh,
correctly scoped facts; a missing fact or field makes it UNKNOWN, never FALSE.
The Core assembles the supporting evidence ids itself. ``core.support`` is kept
unchanged as the v1 baseline and as the reference these claims are checked
against on all replay fixtures.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

from ..core import ROOT, PlanError, read_json
from .contracts import Truth

REGISTRY_PATH = ROOT / "data/registry_v01.json"
SEVERITIES = ("FAULT", "OBSERVATION", "HEALTHY")
OPS = ("exists", "eq", "in", "lt", "le", "gt", "ge")


@dataclass(frozen=True)
class Requirement:
    port: str
    field: str
    op: str
    value: object

    def evaluate(self, state):
        fact = state.fact(self.port)
        if fact is None:
            return Truth.UNKNOWN, None
        if self.op == "exists":
            return Truth.TRUE, fact["id"]
        value = fact["value"]
        for part in self.field.split("."):
            if not isinstance(value, dict) or part not in value:
                return Truth.UNKNOWN, fact["id"]
            value = value[part]
        return (Truth.TRUE if _compare(value, self.op, self.value) else Truth.FALSE), fact["id"]


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _compare(actual, op, expected):
    if op == "eq":
        if isinstance(expected, bool):
            return actual is expected
        if _number(expected):
            return _number(actual) and actual == expected
        return type(actual) is type(expected) and actual == expected
    if op == "in":
        return any(type(actual) is type(option) and actual == option for option in expected)
    if not _number(actual):
        return False
    return {"lt": actual < expected, "le": actual <= expected,
            "gt": actual > expected, "ge": actual >= expected}[op]


@dataclass(frozen=True)
class Claim:
    claim_id: str
    diagnosis: str
    scope: str
    severity: str
    requires: tuple
    excludes: tuple
    message_key: str
    workflow: str | None = None

    def evaluate(self, state):
        """(Truth, evidence ids). Excludes that are TRUE make the claim FALSE."""
        truths, ids = [], []
        for requirement in self.requires:
            truth, eid = requirement.evaluate(state)
            truths.append(truth)
            if eid is not None and eid not in ids:
                ids.append(eid)
        if Truth.FALSE in truths or any(r.evaluate(state)[0] == Truth.TRUE for r in self.excludes):
            return Truth.FALSE, []
        if Truth.UNKNOWN in truths:
            return Truth.UNKNOWN, []
        return Truth.TRUE, ids


class ClaimBook:
    def __init__(self, rows, ports, workflows):
        self.claims, self.workflows = {}, {}
        for row in rows:
            if set(row) - {"claim_id", "diagnosis", "scope", "severity", "requires", "excludes",
                           "message_key", "workflow"}:
                raise PlanError("invalid_claim_fields:" + str(row.get("claim_id")))
            if row["claim_id"] in self.claims:
                raise PlanError("duplicate_claim:" + row["claim_id"])
            if row["severity"] not in SEVERITIES or row["scope"] not in ("gateway", "client"):
                raise PlanError("invalid_claim:" + row["claim_id"])
            reqs = []
            for key in ("requires", "excludes"):
                items = []
                for item in row[key]:
                    if item["port"] not in ports or item["op"] not in OPS:
                        raise PlanError("invalid_claim_requirement:" + row["claim_id"])
                    if item["op"] in ("lt", "le", "gt", "ge") and not _number(item["value"]):
                        raise PlanError("invalid_claim_requirement:" + row["claim_id"])
                    if item["op"] == "in" and not isinstance(item["value"], list):
                        raise PlanError("invalid_claim_requirement:" + row["claim_id"])
                    items.append(Requirement(item["port"], item.get("field", ""), item["op"], item.get("value")))
                reqs.append(tuple(items))
            if not reqs[0]:
                raise PlanError("claim_without_requirements:" + row["claim_id"])
            self.claims[row["claim_id"]] = Claim(row["claim_id"], row["diagnosis"], row["scope"], row["severity"],
                                                 reqs[0], reqs[1], row["message_key"], row.get("workflow"))
        for wid, meta in workflows.items():
            partial = list(meta.get("partial_claims", ()))
            if not set(partial) <= set(meta.get("claims", ())):
                raise PlanError("partial_claim_outside_workflow:" + wid)
            self.workflows[wid] = {"target_scope": meta["target_scope"], "partial_claims": partial,
                                   "claims": list(meta.get("claims", ()))}
        declared = {c.diagnosis for c in self.claims.values()}
        for wid, meta in self.workflows.items():
            missing = set(meta["claims"]) - declared
            if missing:
                raise PlanError("workflow_claim_without_contract:" + wid + ":" + ",".join(sorted(missing)))

    @classmethod
    def from_data(cls, data, ports):
        workflows = {w["workflow_id"]: w for w in data["workflows"]}
        return cls(data.get("claims", ()), ports, workflows)

    @staticmethod
    @lru_cache(maxsize=4)
    def _default_data(path):
        return read_json(path)

    @classmethod
    def default(cls, ports, path=REGISTRY_PATH):
        """Shipped claims, for registries (legacy contracts) that carry none of their own."""
        data = cls._default_data(path)
        rows = [row for row in data.get("claims", ())
                if all(r["port"] in ports for key in ("requires", "excludes") for r in row[key])]
        workflows = {w["workflow_id"]: {**w, "claims": [c for c in w["claims"]
                                                        if any(r["diagnosis"] == c for r in rows)]}
                     for w in data["workflows"]}
        return cls(rows, ports, workflows)

    def lookup(self, diagnosis, workflow=None):
        """The claim for a diagnosis; workflow-specific variants win over generic ones."""
        generic = None
        for claim in self.claims.values():
            if claim.diagnosis != diagnosis:
                continue
            if claim.workflow == workflow and workflow is not None:
                return claim
            if claim.workflow is None:
                generic = claim
        return generic

    def support(self, diagnosis, state, workflow=None):
        """Drop-in for core.support: (TRUE?, evidence ids) for a diagnosis."""
        claim = self.lookup(diagnosis, workflow)
        if claim is None:
            return False, []
        truth, ids = claim.evaluate(state)
        return truth == Truth.TRUE, ids

    def status(self, diagnosis, action, workflow):
        """Case status of a concluded claim: router-only proof for a client question is PARTIAL."""
        claim = self.lookup(diagnosis, workflow)
        meta = self.workflows.get(workflow, {})
        if claim is None:
            return None
        if (claim.severity == "OBSERVATION"
                or (claim.scope == "gateway" and meta.get("target_scope") == "client")
                or diagnosis in meta.get("partial_claims", ())):
            return "PARTIAL"
        return "RESOLVED" if action == "FINISH" else "INCONCLUSIVE"

    def evaluate_all(self, state, workflow=None):
        """Tri-state view of every claim relevant to a workflow (all claims when None)."""
        names = self.workflows.get(workflow, {}).get("claims") if workflow else None
        result = {}
        for claim in self.claims.values():
            if names is not None and claim.diagnosis not in names:
                continue
            if claim.workflow not in (None, workflow):
                continue
            truth, ids = claim.evaluate(state)
            result[claim.claim_id] = {"value": truth.value, "evidence": ids, "scope": claim.scope,
                                      "severity": claim.severity, "diagnosis": claim.diagnosis}
        return result

    def next_best_action(self, registry, state, workflow, candidates):
        """Deterministic NBA (HTML 08/07) over claims that are still possible (not FALSE).

        Score per candidate, compared lexicographically: open predicates of claims in
        the workflow's own scope, then of any claim; a Function also earns the score of
        the open predicates its outputs unlock one hop downstream (prerequisites).
        Ties keep the caller's order, then cost. Returns None when nothing scores.
        """
        scope = self.workflows.get(workflow, {}).get("target_scope")
        open_ports = {}
        for claim in self.claims.values():
            if workflow and claim.diagnosis not in self.workflows.get(workflow, {}).get("claims", ()):
                continue
            if claim.workflow not in (None, workflow) or claim.evaluate(state)[0] == Truth.FALSE:
                continue
            for requirement in claim.requires:
                if requirement.evaluate(state)[0] == Truth.UNKNOWN:
                    own, total = open_ports.get(requirement.port, (0, 0))
                    open_ports[requirement.port] = (own + (claim.scope == scope), total + 1)

        def direct(fid):
            scores = [open_ports.get(p, (0, 0)) for p in registry.functions[fid].outputs]
            return (sum(s[0] for s in scores), sum(s[1] for s in scores))

        def unlocked(fid):
            outputs = set(registry.functions[fid].outputs)
            consumers = [g for g, f in registry.functions.items() if outputs & set(f.inputs) and g != fid]
            scores = [direct(g) for g in consumers]
            return (sum(s[0] for s in scores), sum(s[1] for s in scores))

        order = list(candidates)
        scored = {fid: (direct(fid)[0] + unlocked(fid)[0], direct(fid)[1] + unlocked(fid)[1]) for fid in order}
        best = [fid for fid in order if scored[fid] != (0, 0)]
        if not best:
            return None
        return min(best, key=lambda fid: (-scored[fid][0], -scored[fid][1], order.index(fid), registry.objective(fid)))


def claim_book(registry):
    book = getattr(registry, "claim_book", None)
    if book is None:
        book = registry.claim_book = ClaimBook.default(registry.ports)
    return book
