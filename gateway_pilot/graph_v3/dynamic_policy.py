"""Choose bounded evidence goals for the read-only diagnostic workflows."""

from dataclasses import dataclass

from ..core import PlanError


@dataclass(frozen=True)
class Stage:
    reason: str
    goals: tuple[str, ...]

    @property
    def label(self):
        return "+".join(self.goals)


class DiagnosticPolicy:
    def __init__(self, diag):
        self.diag = diag
        self.attempted = set()
        self.rejected = set()

    def value(self, port, field):
        fact = self.diag.state.fact(port)
        return fact["value"].get(field) if fact else None

    def choices(self, *stages):
        return tuple(stage for stage in stages if stage.goals not in self.rejected and all(
            goal not in self.attempted and self.diag.state.fact(goal) is None for goal in stage.goals))

    def wan_healthy(self):
        return (self.value("wan.status", "link_up") is True
                and self.value("wan.routes", "default_route") is True
                and self.value("wan.probe", "loss_pct") == 0)

    def wan(self):
        proof = self.diag.proof("wan_link_down", "wan_no_route")
        if proof:
            return proof
        if self.value("wan.status", "link_up") is not True:
            return self.choices(Stage("check_physical_link", ("wan.status",)))
        if self.value("wan.routes", "default_route") is None:
            return self.choices(
                Stage("link_up_check_route_then_probe", ("wan.routes", "wan.probe")),
                Stage("check_route_without_probe", ("wan.routes",)),
            )
        return self.diag.proof("wan_packet_loss") or self.choices(
            Stage("route_exists_probe_external_ip", ("wan.probe",)))

    def gateway_wan(self):
        return self.wan() or self.diag.proof("no_fault_observed")

    def gateway_dns(self):
        stage = self.choices(Stage("check_configured_resolver", ("dns.probe",)))
        if stage:
            return stage
        wan = self.wan()
        if wan:
            return wan
        if not self.wan_healthy():
            return None
        if self.diag.state.fact("dns.probe") is None:
            return self.diag.observed("INCOMPLETE", "gateway_ip_reachable_dns_unverified", "wan.probe")
        return self.diag.proof("gateway_dns_failure", "no_fault_observed")

    def dhcp(self, *, check_health):
        valid = self.value("dhcp.leases", "lease_valid")
        if valid is None:
            choices = self.choices(Stage("check_lease_for_selected_device", ("dhcp.leases",)))
            if choices:
                return choices
            return self.diag.unresolved_client() if self.diag.state.fact("client.identity") is None else None
        pool = Stage("check_available_addresses", ("dhcp.pool",))
        service = Stage("check_dhcp_service", ("dhcp.service",))
        if valid:
            if check_health:
                return self.diag.proof("no_fault_observed") or self.choices(
                    Stage("verify_pool_and_service", ("dhcp.pool", "dhcp.service")), pool, service)
            return None
        return (self.diag.proof("dhcp_pool_exhausted", "dhcp_service_down")
                or self.choices(pool, service) or self.diag.proof("client_no_lease"))

    def system_health(self):
        return (self.diag.proof("system_memory_pressure", "system_cpu_load", "system_storage_full", "no_fault_observed")
                or self.choices(Stage("measure_cpu_memory_storage", ("system.resources",))))

    def client_internet(self):
        associated = self.value("wifi.station", "associated")
        if associated is None:
            return (self.choices(Stage("check_client_association_and_signal", ("wifi.station",)))
                    or (self.diag.unresolved_client() if self.diag.state.fact("client.identity") is None else None))
        if associated is False:
            return self.diag.observed("FINISH", "client_not_associated", "wifi.station")
        weak = self.diag.proof("wifi_weak_signal")
        if weak:
            return weak
        configured = self.value("client.ipv4", "configured")
        if configured is None:
            return self.choices(Stage("check_client_address", ("client.ipv4",)))
        if configured is False:
            return self.dhcp(check_health=False) or self.diag.observed(
                "FINISH", "client_ipv4_unconfigured", "wifi.station", "client.ipv4")
        if not self.value("client.ipv4", "address"):
            return None
        return self.wan() or self.client_probes()

    def client_probes(self):
        wan_ok = self.wan_healthy()
        client_loss = self.value("client.probe", "loss_pct")
        dns_code = self.value("dns.probe", "rcode")
        if wan_ok and (fault := self.diag.proof("gateway_dns_failure")):
            return fault
        if client_loss is not None and client_loss >= 50:
            return self.diag.observed("FINISH", "client_path_loss", "client.probe")

        stages = [Stage("verify_ip_path_from_client" if wan_ok else "wan_unverified_measure_client_path",
                        ("client.probe",))]
        if wan_ok:
            stages.append(Stage("external_ip_reachable_check_gateway_dns", ("dns.probe",)))
        query = self.value("dns.probe", "query")
        if client_loss == 0 and dns_code == "NOERROR" and query and query.rstrip("."):
            client_query = self.value("client.dns", "query")
            if (client_query and client_query.rstrip(".").casefold() == query.rstrip(".").casefold()
                    and self.value("client.dns", "rcode") in {"SERVFAIL", "TIMEOUT", "REFUSED"}):
                return self.diag.observed("FINISH", "client_dns_failure", "client.dns", "client.probe", "dns.probe")
            stages.append(Stage("compare_dns_from_client_and_router", ("client.dns",)))
        choices = self.choices(*stages)
        if choices:
            return choices
        if client_loss == 0:
            return self.diag.observed("INCOMPLETE", "client_ip_reachable", "client.probe")
        if wan_ok and dns_code == "NOERROR" and client_loss is None:
            return self.diag.observed("INCOMPLETE", "client_path_unverified", "dns.probe", "wan.probe")
        return None

    def decide(self):
        decide = {"WF-018": self.gateway_wan, "WF-023": self.gateway_dns,
                  "WF-024": lambda: self.dhcp(check_health=True), "WF-039": self.system_health,
                  "WF-INTERNET": self.client_internet}[self.diag.case["workflow"]]
        return decide()

    def select_stage(self, choose_stage=None):
        runner = self.diag.runner
        while True:
            decision = self.decide()
            if not isinstance(decision, tuple):
                return decision
            if not decision:
                return None
            revision = runner.plans[-1].revision + 1 if runner.plans else 1
            candidates, rejected = {}, {}
            for stage in decision:
                try:
                    plan = runner.compiler().compile(stage.goals, runner.state, revision=revision)
                    if len(plan.nodes) > runner.max_calls - runner.calls:
                        raise PlanError("insufficient_call_budget")
                except PlanError as exc:
                    rejected[stage.label] = str(exc)
                    self.rejected.add(stage.goals)
                else:
                    candidates[stage] = plan
            event = {"after_call": runner.calls, "wan_verified": self.wan_healthy(),
                     "candidates": {stage.label: plan.topological() for stage, plan in candidates.items()},
                     "rejected": rejected, "selected": None}
            self.diag.policy_steps.append(event)
            if not candidates:
                continue
            stage = next(iter(candidates))
            if choose_stage is not None:
                stage = choose_stage(candidates, event)
            elif {item.goals for item in candidates} == {("client.probe",), ("dns.probe",)}:
                ordered = self.diag.order_probes(tuple(item.label for item in candidates), prechecked=True)
                stage = next(item for item in candidates if item.label == ordered[0])
            event.update(selected=stage.label, goals=list(stage.goals), reason=stage.reason)
            return stage, candidates[stage]

    def execute_stage(self, stage, plan):
        self.attempted.update(stage.goals)
        return self.diag.observe_stage(stage.goals, stage.reason, plan=plan)

    def run(self):
        while isinstance(selection := self.select_stage(), tuple):
            self.execute_stage(*selection)
        return selection
