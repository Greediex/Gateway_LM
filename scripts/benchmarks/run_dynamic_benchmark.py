"""Compare the Core and dynamic probe policies on curated synthetic replay."""

import argparse
import json
from pathlib import Path

from gateway_pilot.graph_v3.contracts import validate
from gateway_pilot.workflow import diagnose, workflow_registry
from gateway_pilot.workflow_advisor import OllamaProbeAdvisor
from .run_html_benchmark import TARGET, internet_replay


REQUEST = "Máy tính phòng khách vẫn có Wi-Fi nhưng không mở được trang web."
WAN_REQUEST = "Kiểm tra WAN của router."
DNS_REQUEST = "Kiểm tra DNS của router."
DHCP_REQUEST = "Máy tính phòng khách chưa có IP."
SYSTEM_REQUEST = "Kiểm tra CPU và RAM của router."
LOSS = {"client.probe": {"loss_pct": 80}}
CASES = (
    ("client_dns", {"client": {"client.dns": {"rcode": "REFUSED"}}},
     "client_dns_failure", ("client.dns", "client.probe", "dns.probe"), False),
    ("client_loss", {"client": LOSS}, "client_path_loss", ("client.probe",), False),
    ("wan_down", {"gateway": {"wan.status": {"link_up": False}}},
     "wan_link_down", ("wan.status",), False),
    ("wan_timeout", {"gateway": {"wan.probe": {"_status": "TIMEOUT"}}, "client": LOSS},
     "client_path_loss", ("client.probe",), True),
    ("wan_malformed", {"gateway": {"wan.routes": {"default_route": "true"}}},
     "client_ip_reachable", ("client.probe",), True),
    ("dns_timeout", {"gateway": {"dns.probe": {"_status": "TIMEOUT"}}},
     "client_ip_reachable", ("client.probe",), True),
    ("stale_client_probe", {"client": {"client.probe": {"_age_s": 300}}},
     "client_path_unverified", ("dns.probe", "wan.probe"), True),
    ("wrong_dns_target", {"client": {"client.dns": {"rcode": "REFUSED", "_target": "other-client"}}},
     "client_ip_reachable", ("client.probe",), True),
    ("no_client_adapter", {"disable": ["client.probe", "client.dns"]},
     "client_path_unverified", ("dns.probe", "wan.probe"), False),
)

EXTRA_CASES = (
    (WAN_REQUEST, "wan_healthy", {}, "no_fault_observed", ("wan.status", "wan.routes", "wan.probe"), False),
    (WAN_REQUEST, "wan_route_missing", {"wan.routes": {"default_route": False}},
     "wan_no_route", ("wan.status", "wan.routes"), False),
    (WAN_REQUEST, "wan_adapter_timeout", {"wan.probe": {"_status": "TIMEOUT"}},
     "insufficient_evidence", (), True),
    (DNS_REQUEST, "gateway_dns_servfail", {"dns.probe": {"rcode": "SERVFAIL"}},
     "gateway_dns_failure", ("dns.probe", "wan.probe"), False),
    (DNS_REQUEST, "gateway_dns_timeout", {"dns.probe": {"_status": "TIMEOUT"}},
     "gateway_ip_reachable_dns_unverified", ("wan.probe",), True),
    (DHCP_REQUEST, "dhcp_pool_empty", {"dhcp.pool": {"free_addresses": 0}},
     "dhcp_pool_exhausted", ("dhcp.leases", "dhcp.pool"), False),
    (DHCP_REQUEST, "dhcp_pool_timeout", {"dhcp.pool": {"_status": "TIMEOUT"}, "dhcp.service": {"running": False}},
     "dhcp_service_down", ("dhcp.leases", "dhcp.service"), True),
    (SYSTEM_REQUEST, "system_cpu_high", {"system.resources": {"cpu_pct": 97}},
     "system_cpu_load", ("system.resources",), False),
    (SYSTEM_REQUEST, "system_resources_stale", {"system.resources": {"_age_s": 300}},
     "insufficient_evidence", (), True),
)


def workflow_replay(overrides):
    replay = internet_replay({"permissions": ["network.read", "system.read"]})
    world = replay["world"]
    world.update({"dhcp.pool": {"free_addresses": 3}, "dhcp.service": {"running": True},
                  "system.resources": {"available_ram_pct": 40, "cpu_pct": 20, "storage_used_pct": 30}})
    device = replay["devices"][0]["world"]
    device["dhcp.leases"] = {"lease_valid": False}
    replay["capabilities"] = sorted(world.keys() | device.keys())
    for tool, data in overrides.items():
        world[tool].update(data)
    return replay


def score(result, registry, expected, ports):
    graph, terminal = result["graph"], result["terminal"]
    observations = {e["id"]: e for e in graph["evidence"]}
    cited = [observations[eid] for eid in terminal["evidence_ids"]]
    evidence_ok = tuple(sorted(e["port"] for e in cited)) == tuple(sorted(ports)) and all(
        e["status"] == "OK" and 0 <= e["age_s"] <= e["ttl_s"]
        and e["scope"] == registry.ports[e["port"]].scope
        and e["target"] == (TARGET if e["scope"] == "client" else "gateway_01")
        and e["source"].startswith(registry.ports[e["port"]].provenance)
        and validate(e["value"], registry.ports[e["port"]].schema)
        for e in cited
    )
    calls = [row["function_id"] for row in graph["executed"]]
    order_ok = all(
        edge["source"] in calls and calls.index(edge["source"]) < calls.index(edge["target"])
        for plan in graph["plans"] for edge in plan["edges"] if edge["target"] in calls
    )
    read_only = all(registry.functions[fid].risk == "READ" for fid in calls)
    first_failure = next((i for i, e in enumerate(graph["events"])
                          if e.get("state") in {"FAILED", "INCONCLUSIVE"}), None)
    return {"diagnosis": terminal["diagnosis"], "case_status": result["case_status"],
            "pass": terminal["diagnosis"] == expected
            and evidence_ok and order_ok and read_only, "evidence_ok": evidence_ok,
            "dependency_order_ok": order_ok, "read_only": read_only, "calls": calls, "plans": len(graph["plans"]),
            "calls_after_first_failure": (len(calls) - first_failure - 1 if first_failure is not None else None),
            "model_calls": len(graph["advice"]),
            "accepted_model_calls": sum(event["accepted"] for event in graph["advice"])}


def benchmark(advisor=None):
    registry = workflow_registry()
    report = {}
    arms = [("core", False, None), ("dynamic", True, None)]
    if advisor is not None:
        arms.append(("dynamic_with_advisor", True, advisor))
    for name, dynamic, probe_advisor in arms:
        rows = []
        inputs_by_case = [(REQUEST, name, internet_replay(inputs), diagnosis, ports, injected)
                          for name, inputs, diagnosis, ports, injected in CASES]
        inputs_by_case += [(request, name, workflow_replay(inputs), diagnosis, ports, injected)
                           for request, name, inputs, diagnosis, ports, injected in EXTRA_CASES]
        for request, case_id, replay, diagnosis, ports, injected in inputs_by_case:
            result = diagnose(request, replay, registry=registry, dynamic=dynamic,
                              advisor=probe_advisor)
            rows.append({"case": case_id, "workflow": result["workflow"], "injected": injected,
                         **score(result, registry, diagnosis, ports)})
        report[name] = {"passed": sum(row["pass"] for row in rows), "total": len(rows),
                        "fault_cases_passed": sum(row["pass"] for row in rows if row["injected"]),
                        "fault_cases_total": sum(row["injected"] for row in rows),
                        "tool_calls": sum(len(row["calls"]) for row in rows),
                        "plans": sum(row["plans"] for row in rows),
                        "model_calls": sum(row["model_calls"] for row in rows),
                        "accepted_model_calls": sum(row["accepted_model_calls"] for row in rows), "cases": rows}
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--model", help="Optional local Ollama model with fewer than 3B parameters")
    args = parser.parse_args()
    advisor = OllamaProbeAdvisor(args.model) if args.model else None
    report = benchmark(advisor)
    if advisor is not None:
        report["dynamic_with_advisor"].update(model=advisor.model, parameters=advisor.parameter_count)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as output:
        json.dump(report, output, indent=2, ensure_ascii=False)
    for name, row in report.items():
        print(f'{name}: {row["passed"]}/{row["total"]} passed, '
              f'{row["fault_cases_passed"]}/{row["fault_cases_total"]} fault cases passed, '
              f'{row["tool_calls"]} tool calls, {row["model_calls"]} model calls')
    return int(report["dynamic"]["passed"] != report["dynamic"]["total"])


if __name__ == "__main__":
    raise SystemExit(main())
