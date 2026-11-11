"""Typed capability graph, shared policy and read-only evidence adapters."""
from __future__ import annotations

import copy
import json
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


class PlanError(ValueError):
    pass


def terms(text):
    return re.findall(r"[^\W_]+", text.lower(), flags=re.UNICODE)


class Registry:
    def __init__(self, path=ROOT / "data" / "registry.json", *, data=None):
        self.data = read_json(path) if data is None else copy.deepcopy(data)
        self.functions = {f["id"]: f for f in self.data["functions"]}
        self.skills = {s["id"]: s for s in self.data["skills"]}
        self.producers = {}
        for f in self.functions.values():
            for port in f["produces"]:
                self.producers.setdefault(port, []).append(f["id"])
        self.documents = []
        for item in [*self.skills.values(), *self.functions.values()]:
            self.documents.append((item["id"], Counter(terms(json.dumps(item, ensure_ascii=False)))))
        self.avgdl = sum(sum(d.values()) for _, d in self.documents) / len(self.documents)

    def retrieve(self, query, k=4):
        """Joint Skill/Function BM25, then soft membership; no gold fields."""
        q = Counter(terms(query))
        n = len(self.documents)
        scored = {}
        for item_id, doc in self.documents:
            score = 0.0
            for term in q:
                freq = doc[term]
                df = sum(term in d for _, d in self.documents)
                idf = math.log(1 + (n - df + .5) / (df + .5))
                score += idf * freq * 2.2 / (freq + 1.2 * (.25 + .75 * sum(doc.values()) / self.avgdl))
            scored[item_id] = score
        ranked = []
        for fid, f in self.functions.items():
            affinity = max((scored.get(sid, 0) for sid in f["skills"]), default=0)
            ranked.append((scored[fid] + .20 * affinity, fid))
        return [fid for score, fid in sorted(ranked, key=lambda x: (-x[0], x[1]))[:k]]

    def closure(self, seeds, state, max_nodes=12):
        """Backward typed deficit expansion; all producers must be safe/read-only."""
        ordered, visiting, visited = [], set(), set()

        def visit(fid):
            if fid in visiting:
                raise PlanError("dependency_cycle")
            if fid in visited:
                return
            if fid not in self.functions:
                raise PlanError("unknown_function")
            f = self.functions[fid]
            if f["risk"] != "READ":
                raise PlanError("write_requires_transaction_not_implemented")
            if fid not in state.capabilities:
                raise PlanError("unsupported_capability:" + fid)
            visiting.add(fid)
            for port in f["requires"]:
                if state.fact(port) is not None:
                    continue
                producers = [p for p in self.producers.get(port, [])
                             if p in state.capabilities and self.functions[p]["risk"] == "READ"]
                if not producers:
                    raise PlanError("missing_producer:" + port)
                visit(sorted(producers)[0])
            visiting.remove(fid)
            visited.add(fid)
            ordered.append(fid)
            if len(ordered) > max_nodes:
                raise PlanError("graph_node_budget")

        for fid in seeds:
            visit(fid)
        # Relations are constraints, not causal diagnoses.
        for a, b in self.data.get("conflicts", []):
            if a in ordered and b in ordered:
                raise PlanError("function_conflict")
        return ordered

    def candidates(self, case, state, arm, k=4):
        allowed = [fid for fid, f in self.functions.items()
                   if fid in state.capabilities and f["risk"] == "READ"]
        if arm in ("flat", "rules"):
            return allowed
        seeds = [fid for fid in self.retrieve(case["request"], k) if fid in allowed]
        if arm == "retrieval":
            return seeds
        expanded = list(seeds)
        # Verifier contracts expose outstanding evidence goals, not hidden causes.
        # The same requirements are presented as checklists to every model arm.
        for port in self.data.get("workflow_evidence", {}).get(case["workflow"], []):
            if state.fact(port) is not None:
                continue
            for fid in self.producers.get(port, []):
                if fid in allowed and fid not in expanded:
                    expanded.append(fid)
        for fid in list(expanded):
            try:
                for dependency in self.closure([fid], state):
                    if dependency not in expanded:
                        expanded.append(dependency)
            except PlanError:
                pass
        return expanded


@dataclass
class State:
    target: dict
    capabilities: set
    evidence: list = field(default_factory=list)
    errors: list = field(default_factory=list)
    attempts: Counter = field(default_factory=Counter)
    executed: list = field(default_factory=list)

    def fact(self, port):
        for e in reversed(self.evidence):
            if (e["port"] == port and e["status"] == "OK" and
                    e["age_s"] <= e["ttl_s"] and self.same_scope(e)):
                return e
        return None

    def same_scope(self, e):
        if e["scope"] == "gateway":
            return e["target"] == "gateway_01"
        identity = next((e for e in reversed(self.evidence)
                         if e["port"] == "client.identity" and e["status"] == "OK"
                         and e["age_s"] <= e["ttl_s"]), None)
        expected = identity["value"].get("client_id") if identity else self.target.get("client_id")
        return bool(expected) and e["target"] == expected

    def public(self):
        return {"target": self.target, "evidence": self.evidence,
                "recent_errors": self.errors[-3:], "executed": self.executed}


def new_state(case, registry):
    state = State(copy.deepcopy(case["target"]), set(case.get("capabilities", registry.functions)))
    for e in case.get("initial_evidence", []):
        state.evidence.append(copy.deepcopy(e))
    return state


def bind_and_gate(fid, arguments, state, registry):
    if fid not in registry.functions:
        raise PlanError("unknown_function")
    f = registry.functions[fid]
    if fid not in state.capabilities:
        raise PlanError("unsupported_capability")
    if f["risk"] != "READ":
        raise PlanError("write_requires_transaction_not_implemented")
    if not isinstance(arguments, dict):
        raise PlanError("arguments_must_be_object")
    if set(arguments) - {"client_id", "interface", "resolver", "domain"}:
        raise PlanError("unknown_argument")
    for port in f["requires"]:
        if state.fact(port) is None:
            raise PlanError("missing_precondition:" + port)
    args = copy.deepcopy(arguments)
    identity = state.fact("client.identity")
    if f["scope"] == "client" and fid != "clients.resolve":
        client_id = identity["value"]["client_id"]
        if args.get("client_id", client_id) != client_id:
            raise PlanError("wrong_target")
        args["client_id"] = client_id
    for key, value in args.items():
        if not isinstance(value, str) or len(value) > 128 or any(x in value for x in (";", "\n", "`", "$", "|")):
            raise PlanError("invalid_typed_argument:" + key)
    if "interface" in args and args["interface"] != "wan":
        raise PlanError("wrong_interface")
    cfg = state.fact("dns.config")
    if fid == "dns.probe" and cfg:
        resolver = cfg["value"]["resolver"]
        if args.get("resolver", resolver) != resolver:
            raise PlanError("resolver_out_of_scope")
        args["resolver"] = resolver
    if state.attempts[fid] >= 2:
        raise PlanError("duplicate_tool_budget")
    return args


def execute(fid, args, state, case, registry):
    """Collect and record a single-output observation after checking the read gate."""
    bound = bind_and_gate(fid, args, state, registry)
    state.attempts[fid] += 1
    state.executed.append({"function_id": fid, "arguments": bound})
    f = registry.functions[fid]
    reader = case.get("live_reader")
    if reader is None:
        raw = copy.deepcopy(case["world"].get(fid, {"_status": "MISSING"}))
        source, observed_at = "synthetic_replay/v1", "2026-11-07T00:00:00Z"
    else:
        raw, source, observed_at = reader(fid, state)
    status = raw.pop("_status", "OK")
    age = raw.pop("_age_s", 0)
    scope_target = raw.pop("_target", None)
    port = f["produces"][0]
    # Minimal per-port schema rejects malformed adapter output, never invents facts.
    required = registry.data["port_fields"][port]
    if status == "OK" and any(k not in raw or type(raw[k]) not in types_for(t)
                              for k, t in required.items()):
        status = "PARSE_ERROR"
    identity = state.fact("client.identity")
    default_target = (raw.get("client_id") if fid == "clients.resolve" else
                      identity["value"]["client_id"] if identity else state.target.get("client_id", "unresolved"))
    observation = {"id": "e" + str(len(state.evidence) + 1), "function_id": fid,
                   "port": port, "scope": f["scope"],
                   "target": scope_target or ("gateway_01" if f["scope"] == "gateway" else default_target),
                   "source": source, "observed_at": observed_at,
                   "age_s": age, "ttl_s": f["ttl_s"], "status": status, "value": raw}
    state.evidence.append(observation)
    return observation


def types_for(name):
    return {"str": (str,), "bool": (bool,), "number": (int, float), "list": (list,)}[name]


DIAGNOSES = {
    "wan_link_down": "WAN physical link is down",
    "wan_no_route": "Gateway has no default WAN route",
    "wan_packet_loss": "Gateway external IP probe has excessive loss",
    "gateway_dns_failure": "Configured resolver fails from gateway; not proof of client root cause",
    "dhcp_pool_exhausted": "DHCP pool exhausted and target client has no lease",
    "dhcp_service_down": "DHCP service stopped and target client has no lease",
    "client_no_lease": "Client has no lease; exact cause unconfirmed",
    "system_memory_pressure": "Gateway available RAM critically low",
    "system_cpu_load": "Gateway CPU utilization high",
    "system_storage_full": "Gateway persistent storage nearly full",
    "wifi_weak_signal": "Target client's Wi-Fi signal is weak",
    "no_fault_observed": "Relevant checks healthy within observed scope",
    "insufficient_evidence": "Missing/stale/failed measurements prevent a conclusion",
    "target_ambiguous": "Target cannot be uniquely resolved",
    "client_path_unverified": "Gateway checks healthy but client path not observed",
    "unsafe_change_denied": "Requested write unavailable in read-only pilot",
}


def support(diagnosis, state, case):
    """Product evidence verifier, independent of gold answers in the scorer."""
    def v(port):
        e = state.fact(port)
        return e["value"] if e else {}

    def ids(*ports):
        return [state.fact(p)["id"] for p in ports if state.fact(p)]

    wan, route, probe = v("wan.status"), v("wan.routes"), v("wan.probe")
    lease, pool, service = v("dhcp.leases"), v("dhcp.pool"), v("dhcp.service")
    dns, resources = v("dns.probe"), v("system.resources")
    checks = {
        "wan_link_down": (wan.get("link_up") is False, ["wan.status"]),
        "wan_no_route": (wan.get("link_up") is True and route.get("default_route") is False, ["wan.status", "wan.routes"]),
        "wan_packet_loss": (probe.get("loss_pct", 0) >= 50, ["wan.probe"]),
        "gateway_dns_failure": (dns.get("rcode") in ("SERVFAIL", "TIMEOUT", "REFUSED") and probe.get("loss_pct") == 0,
                                ["dns.probe", "wan.probe"]),
        "dhcp_pool_exhausted": (lease.get("lease_valid") is False and pool.get("free_addresses") == 0,
                                ["dhcp.leases", "dhcp.pool"]),
        "dhcp_service_down": (lease.get("lease_valid") is False and service.get("running") is False,
                              ["dhcp.leases", "dhcp.service"]),
        "client_no_lease": (lease.get("lease_valid") is False, ["dhcp.leases"]),
        "system_memory_pressure": (resources.get("available_ram_pct", 100) < 10, ["system.resources"]),
        "system_cpu_load": (resources.get("cpu_pct", 0) > 90, ["system.resources"]),
        "system_storage_full": (resources.get("storage_used_pct", 0) > 95, ["system.resources"]),
        "wifi_weak_signal": (v("wifi.station").get("rssi_dbm", 0) < -78, ["wifi.station"]),
    }
    if diagnosis in checks:
        ok, ports = checks[diagnosis]
        return bool(ok), ids(*ports)
    if diagnosis == "no_fault_observed":
        wf = case["workflow"]
        if wf == "WF-018":
            ok = wan.get("link_up") is True and route.get("default_route") is True and probe.get("loss_pct") == 0
            return ok, ids("wan.status", "wan.routes", "wan.probe")
        if wf == "WF-023":
            return dns.get("rcode") == "NOERROR" and probe.get("loss_pct") == 0, ids("dns.probe", "wan.probe")
        if wf == "WF-024":
            return (lease.get("lease_valid") is True and pool.get("free_addresses", 0) > 0 and service.get("running") is True,
                    ids("dhcp.leases", "dhcp.pool", "dhcp.service"))
        if wf == "WF-039":
            return (bool(resources) and resources.get("available_ram_pct", 0) >= 10 and
                    resources.get("cpu_pct", 100) <= 90 and resources.get("storage_used_pct", 100) <= 95,
                    ids("system.resources"))
    return False, []


def validate_decision(d, state, case, registry, candidates):
    if not isinstance(d, dict) or d.get("action") not in ("CALL_TOOL", "FINISH", "ASK_USER", "INCOMPLETE"):
        raise PlanError("decision_schema")
    if d["action"] == "CALL_TOOL":
        fid = d.get("function_id")
        if fid not in candidates:
            raise PlanError("function_not_exposed")
        bind_and_gate(fid, d.get("arguments", {}), state, registry)
    else:
        if d.get("diagnosis") not in DIAGNOSES:
            raise PlanError("unknown_diagnosis")
        cited = d.get("evidence_ids", [])
        if not isinstance(cited, list) or any(not isinstance(x, str) or x not in {e["id"] for e in state.evidence} for x in cited):
            raise PlanError("fabricated_evidence_id")
        if d["action"] == "ASK_USER" and d["diagnosis"] != "target_ambiguous":
            raise PlanError("action_diagnosis_mismatch")
        if d["action"] == "INCOMPLETE" and d["diagnosis"] not in ("insufficient_evidence", "client_path_unverified", "unsafe_change_denied"):
            raise PlanError("action_diagnosis_mismatch")
        if d["action"] == "FINISH":
            ok, supporting_ids = support(d["diagnosis"], state, case)
            cited = d.get("evidence_ids", [])
            if not ok or not supporting_ids or not isinstance(cited, list) or not set(supporting_ids).issubset(cited):
                raise PlanError("unsupported_finish_or_missing_citations")
    return d


def rules_decision(case, state, registry):
    """Fixed workflow baseline: data rules, no hidden world or gold access."""
    orders = {
        "WF-018": ["wan.status", "wan.routes", "wan.probe"],
        "WF-023": ["dns.config", "dns.probe", "wan.status", "wan.routes", "wan.probe"],
        "WF-024": ["clients.resolve", "dhcp.leases", "dhcp.pool", "dhcp.service"],
        "WF-039": ["system.resources", "system.logs"],
        "WF-INTERNET": ["clients.resolve", "client.ipv4", "wifi.station", "wan.status", "wan.routes", "wan.probe", "dns.config", "dns.probe", "client.probe"],
    }
    if case["workflow"] == "WF-WRITE":
        return {"action": "INCOMPLETE", "diagnosis": "unsafe_change_denied", "evidence_ids": []}
    # Only finish on evidence; prefer a specific cause over a symptom.
    for diagnosis in ("wan_link_down", "wan_no_route", "wan_packet_loss", "gateway_dns_failure",
                      "dhcp_pool_exhausted", "dhcp_service_down", "system_memory_pressure",
                      "system_cpu_load", "system_storage_full", "wifi_weak_signal", "no_fault_observed"):
        ok, evidence = support(diagnosis, state, case)
        if ok:
            return {"action": "FINISH", "diagnosis": diagnosis, "evidence_ids": evidence}
    if any(e["status"] == "AMBIGUOUS" for e in state.evidence):
        return {"action": "ASK_USER", "diagnosis": "target_ambiguous", "evidence_ids": []}
    for fid in orders.get(case["workflow"], []):
        if fid not in state.capabilities or state.attempts[fid] or state.fact(registry.functions[fid]["produces"][0]):
            continue
        try:
            bind_and_gate(fid, {}, state, registry)
        except PlanError:
            continue
        return {"action": "CALL_TOOL", "function_id": fid, "arguments": {}}
    ok, evidence = support("client_no_lease", state, case)
    if ok:
        return {"action": "FINISH", "diagnosis": "client_no_lease", "evidence_ids": evidence}
    diag = "client_path_unverified" if case["workflow"] == "WF-INTERNET" else "insufficient_evidence"
    return {"action": "INCOMPLETE", "diagnosis": diag, "evidence_ids": []}
