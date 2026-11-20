"""INCIDENT-GAPS: incident checks GP01..GP07 over the new READ ports (MSS, IPv6, load, NAT class, DFS, AP signal) plus DNS.

Thresholds are declared synthetic heuristics in replay_gaps_composite.diagnostics.json, not calibrated
values. Samples that cannot support a verdict (outside a bounded domain, inconsistent, source missing)
must be UNKNOWN, never HEALTHY/FAULT.
"""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gateway_pilot.application import replay_sim_run, skill_chat
from gateway_pilot.application.skill_launcher import SkillLauncher
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.skill_expansion import deployment as dep, replay_sim
from gateway_pilot.skill_expansion.catalog import SkillCatalog
from gateway_pilot.skill_expansion.coverage import ACCEPTANCE, accepted_skills, coverage_report

from gateway_pilot.skill_expansion.composite import batch_paths, contracts, load_scenarios
from gateway_pilot.skill_expansion.simulation import GAPS_DIR, function_proposals
from scripts.simulate_composites import evaluate, run_scenario

BATCH = "GAP"
SKILLS_GP = SKILLS = ("GP01", "GP02", "GP03", "GP04", "GP05", "GP06", "GP07")
NEW_PORTS = ("wan_mss", "ipv6_connectivity", "system_load", "wan_addressing", "radio_events", "client_ap_signal")
DOWN = {"reachable": False, "loss_pct": 100.0}

# (skill, {alias: field changes applied on the normal scenario}, expected verdict)
BOUNDARIES = [
    # GP01 / G1: DNS resolvers down while the upstream answers by IP
    ("GP01", {"dns": {"healthy_count": 0}}, "FAULT"),
    ("GP01", {"dns": {"healthy_count": 1}}, "HEALTHY"),
    ("GP01", {"dns": {"resolver_count": 0, "healthy_count": 0}}, "FAULT"),
    ("GP01", {"dns": {"healthy_count": 3}}, "UNKNOWN"),              # more healthy than configured
    ("GP01", {"dns": {"resolver_count": -1, "healthy_count": 0}}, "UNKNOWN"),
    ("GP01", {"dns": {"healthy_count": -1}}, "UNKNOWN"),
    ("GP01", {"dns": {"healthy_count": 0}, "upstream": {"loss_pct": 5.0}}, "FAULT"),
    ("GP01", {"dns": {"healthy_count": 0}, "upstream": {"loss_pct": 5.01}}, "UNKNOWN"),
    ("GP01", {"dns": {"healthy_count": 0}, "upstream": DOWN}, "UNKNOWN"),   # outage is not a DNS finding
    ("GP01", {"upstream": DOWN}, "UNKNOWN"),
    # GP02 / G2: PPPoE MTU below 1500 without MSS clamping
    ("GP02", {"mss": {"mss_clamping": False}}, "FAULT"),
    ("GP02", {"mss": {"mss_clamping": False, "mtu_bytes": 1499}}, "FAULT"),
    ("GP02", {"mss": {"mss_clamping": False, "mtu_bytes": 576}}, "FAULT"),
    ("GP02", {"mss": {"mss_clamping": False, "mtu_bytes": 575}}, "UNKNOWN"),
    ("GP02", {"mss": {"mss_clamping": False, "mtu_bytes": 1500}}, "HEALTHY"),   # no reduction, nothing to clamp
    ("GP02", {"mss": {"mtu_bytes": 9216}}, "HEALTHY"),
    ("GP02", {"mss": {"mtu_bytes": 9217}}, "UNKNOWN"),
    ("GP02", {"mss": {"mss_clamping": True}}, "HEALTHY"),
    ("GP02", {"mss": {"proto": "dhcp", "mtu_bytes": 1500, "mss_clamping": False}}, "HEALTHY"),
    ("GP02", {"mss": {"proto": "dhcp", "mtu_bytes": 1492, "mss_clamping": False}}, "UNKNOWN"),
    ("GP02", {"mss": {"proto": "l2tp", "mss_clamping": False}}, "UNKNOWN"),
    ("GP02", {"mss": {"mss_clamping": False}, "upstream": DOWN}, "UNKNOWN"),
    # GP03 / G3: IPv6 address without route (broken) versus no IPv6 offered
    ("GP03", {"v6": {"default_route": False, "reachable": False}}, "FAULT"),
    ("GP03", {"v6": {"reachable": False}}, "FAULT"),                          # route exists, path dead
    ("GP03", {"v6": {"default_route": False}}, "UNKNOWN"),                   # reachable without a route
    ("GP03", {"ra": {"router_advertisements": False, "prefix_count": 0},
             "v6": {"global_address": False, "default_route": False, "reachable": False}}, "HEALTHY"),
    ("GP03", {"v6": {"global_address": False, "default_route": False, "reachable": False}}, "UNKNOWN"),  # RA says IPv6 is offered
    ("GP03", {"ra": {"router_advertisements": False, "prefix_count": 1},
             "v6": {"global_address": False, "default_route": False, "reachable": False}}, "UNKNOWN"),
    ("GP03", {"v6": {"global_address": False}}, "UNKNOWN"),                  # reachable without an address
    ("GP03", {"ra": {"prefix_count": -1}}, "UNKNOWN"),
    ("GP03", {"ra": {"prefix_count": 65}}, "UNKNOWN"),
    # GP04 / G4: router CPU high together with many devices
    ("GP04", {"load": {"cpu_pct": 85.0, "clients_count": 25}}, "FAULT"),
    ("GP04", {"load": {"cpu_pct": 100.0, "clients_count": 25, "mem_pct": 95.0}}, "FAULT"),
    ("GP04", {"load": {"cpu_pct": 84.99, "clients_count": 25}}, "HEALTHY"),
    ("GP04", {"load": {"cpu_pct": 85.0, "clients_count": 24}}, "UNKNOWN"),   # busy CPU, few devices
    ("GP04", {"load": {"cpu_pct": 100.01}}, "UNKNOWN"),
    ("GP04", {"load": {"cpu_pct": -1.0}}, "UNKNOWN"),
    ("GP04", {"load": {"mem_pct": 89.99}}, "HEALTHY"),
    ("GP04", {"load": {"mem_pct": 90.0}}, "UNKNOWN"),
    ("GP04", {"load": {"mem_pct": 100.01}}, "UNKNOWN"),
    ("GP04", {"load": {"clients_count": 4096, "cpu_pct": 10.0}}, "HEALTHY"),
    ("GP04", {"load": {"clients_count": 4097}}, "UNKNOWN"),
    ("GP04", {"load": {"clients_count": -1}}, "UNKNOWN"),
    ("GP04", {"load": {"load1": -0.1}}, "UNKNOWN"),
    # GP05 / G5: double NAT is a different finding from carrier-grade NAT
    ("GP05", {"addr": {"wan_ip_class": "private", "upstream_is_router": True}}, "FAULT"),
    ("GP05", {"addr": {"wan_ip_class": "private", "upstream_is_router": False}}, "UNKNOWN"),
    ("GP05", {"addr": {"wan_ip_class": "cgnat", "upstream_is_router": False}}, "FAULT"),
    ("GP05", {"addr": {"wan_ip_class": "cgnat", "upstream_is_router": True}}, "FAULT"),
    ("GP05", {"addr": {"wan_ip_class": "public", "upstream_is_router": True}}, "HEALTHY"),
    ("GP05", {"nat": {"nat_enabled": False}, "addr": {"wan_ip_class": "private", "upstream_is_router": True}}, "UNKNOWN"),
    ("GP05", {"addr": {"wan_ip_class": "other"}}, "UNKNOWN"),
    ("GP05", {"addr": {"wan_ip_class": ""}}, "UNKNOWN"),
    # GP06 / G6: DFS radar detections on the 5 GHz radio
    ("GP06", {"events": {"radar_detected_count": 1, "channel_changes": 1}}, "FAULT"),
    ("GP06", {"events": {"radar_detected_count": 1, "channel_changes": 1, "observation_window_s": 10}}, "FAULT"),
    ("GP06", {"events": {"radar_detected_count": 1, "channel_changes": 0}}, "UNKNOWN"),   # no channel change on record
    ("GP06", {"events": {"radar_detected_count": 0, "observation_window_s": 3600}}, "HEALTHY"),
    ("GP06", {"events": {"radar_detected_count": 0, "observation_window_s": 3599}}, "UNKNOWN"),
    ("GP06", {"events": {"radar_detected_count": -1}}, "UNKNOWN"),
    ("GP06", {"events": {"radar_detected_count": 1001, "channel_changes": 1}}, "UNKNOWN"),
    ("GP06", {"events": {"observation_window_s": -1}}, "UNKNOWN"),
    ("GP06", {"radio": {"band": "2.4GHz"}, "events": {"radar_detected_count": 1, "channel_changes": 1}}, "UNKNOWN"),
    ("GP06", {"radio": {"channel": 0}, "events": {"radar_detected_count": 1, "channel_changes": 1}}, "UNKNOWN"),
    # GP07 / G7: weak RSSI, a much stronger AP exists, no roaming (Apple margin: 12 dB)
    ("GP07", {"sig": {"current_rssi_dbm": -75.01, "rssi_gap_db": 12.0}}, "FAULT"),
    ("GP07", {"sig": {"current_rssi_dbm": -120.0, "rssi_gap_db": 120.0}}, "FAULT"),
    ("GP07", {"sig": {"current_rssi_dbm": -75.0, "rssi_gap_db": 12.0}}, "HEALTHY"),   # adequate signal is not a fault
    ("GP07", {"sig": {"current_rssi_dbm": -90.0, "rssi_gap_db": 11.99}}, "HEALTHY"),  # no clearly better AP
    ("GP07", {"sig": {"current_rssi_dbm": -90.0, "rssi_gap_db": -5.0}}, "HEALTHY"),   # current AP is the best one
    ("GP07", {"sig": {"current_rssi_dbm": -90.0, "rssi_gap_db": 20.0, "roam_count": 1}}, "UNKNOWN"),  # it roams: B07 territory
    ("GP07", {"sig": {"current_rssi_dbm": -90.0, "rssi_gap_db": 20.0, "observation_window_s": 599}}, "UNKNOWN"),
    ("GP07", {"sig": {"current_rssi_dbm": -90.0, "rssi_gap_db": 20.0, "observation_window_s": 600}}, "FAULT"),
    ("GP07", {"assoc": {"associated": False}, "sig": {"current_rssi_dbm": -90.0, "rssi_gap_db": 20.0}}, "UNKNOWN"),
    ("GP07", {"sig": {"current_rssi_dbm": 1.0}}, "UNKNOWN"),
    ("GP07", {"sig": {"current_rssi_dbm": -121.0}}, "UNKNOWN"),
    ("GP07", {"sig": {"rssi_gap_db": 120.01}}, "UNKNOWN"),
    ("GP07", {"sig": {"roam_count": -1}}, "UNKNOWN"),
]


class GapCompositeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = contracts(BATCH)
        cls.workflows = cls.doc["workflows"]
        cls.rows = {row["id"]: row for row in load_scenarios(BATCH)}

    def run_normal(self, skill, changes):
        row = copy.deepcopy(self.rows[f"{skill}-normal"])
        for alias, fields in changes.items():
            row["sources"][alias]["values"].update(fields)
        return run_scenario(row, batch=BATCH)

    def assert_unusable(self, result):
        self.assertEqual(result["verdict"], "UNKNOWN")
        self.assertTrue(result["claims"])
        for claim in result["claims"].values():
            self.assertEqual(claim["value"], "UNKNOWN")
            self.assertEqual(claim["evidence"], [])

    def test_new_ports_are_read_only_and_leave_the_reviewed_catalog_alone(self):
        main_ids = {f["function_id"] for f in json.loads((batch_paths("A")[0].parent / "function_proposals.json").read_text())}
        new = {f["function_id"]: f for f in json.loads((GAPS_DIR / "functions.json").read_text())}
        self.assertEqual(set(new), {f"expansion.{n}" for n in NEW_PORTS})
        self.assertFalse(set(new) & main_ids)
        self.assertEqual(len(function_proposals()), len(main_ids) + len(new))
        for fid, f in new.items():
            with self.subTest(function=fid):
                port = json.loads((GAPS_DIR / "ports" / f"{fid}.json").read_text())
                self.assertEqual((f["risk"], f["permission"], f["lifecycle"]), ("READ_ONLY", "network.read", "PROPOSED"))
                self.assertEqual(set(f["outputs"]), {fid})
                self.assertEqual((port["port_id"], port["version"], port["scope"]), (fid, "1.0.0", f["scope"]))
                self.assertFalse(port["schema"]["additionalProperties"])
                self.assertEqual(set(port["schema"]["required"]), set(port["schema"]["properties"]))

    def test_workflows_claims_and_sources(self):
        self.assertEqual(set(self.workflows), set(SKILLS))
        self.assertEqual(set(self.rows), {f"{s}-{c}" for s in SKILLS for c in ("normal", "fault", "missing")})
        used = set()
        for skill, workflow in self.workflows.items():
            with self.subTest(skill=skill):
                self.assertTrue(workflow["limitation"].strip())
                self.assertTrue(workflow["require_same_sample_time"])
                claims = [c for c in self.doc["claims"] if c["workflow"] == workflow["workflow_id"]]
                self.assertEqual({c["claim_id"] for c in claims}, set(workflow["claims"]))
                self.assertTrue({"FAULT", "HEALTHY"} <= {c["severity"] for c in claims})
                for claim in claims:
                    self.assertTrue(claim["claim_id"].endswith("_v1"))
                    self.assertEqual(claim["excludes"], [])
                    for p in claim["requires"]:
                        schema = workflow["sources"][p["port"]]["value_schema"]["properties"][p["field"]]
                        self.assertIn(p["op"], {"eq", "lt", "le", "gt", "ge"})
                        self.assertIn(type(p["value"]), {bool, int, float, str})
                        self.assertTrue(schema)
                used |= {s["function_id"] for s in workflow["sources"].values()}
        self.assertLessEqual({f"expansion.{n}" for n in NEW_PORTS}, used)
        self.assertIn("expansion.dns_resolvers", used)  # G1 needs no new port

    def test_scored_suite_and_original_core_proof_ids(self):
        report = evaluate(BATCH)
        self.assertEqual((report["passed"], report["total"]), (21, 21))
        claim_ports = {c["claim_id"]: [p["port"] for p in c["requires"]] for c in self.doc["claims"]}
        for row in self.rows.values():
            with self.subTest(scenario=row["id"]):
                specs = self.workflows[row["skill_id"]]["sources"]
                proofs = {}

                def capture(sources):
                    for alias, source in sources.items():
                        fact = source.state.fact(specs[alias]["function_id"])
                        if fact:
                            self.assertEqual(fact["value"], row["sources"][alias]["values"])
                            proofs[alias] = fact["id"]

                result = run_scenario(row, batch=BATCH, inspect=capture)
                if row["id"].endswith("-missing"):
                    self.assertEqual(sum(s["values"] is None for s in row["sources"].values()), 1)
                    self.assertEqual(len(proofs), len(specs) - 1)
                    self.assert_unusable(result)
                    continue
                self.assertEqual(set(proofs), set(specs))
                self.assertFalse(result["source_errors"])
                positive = {cid: c for cid, c in result["claims"].items() if c["value"] == "TRUE"}
                self.assertTrue(positive)
                for cid, claim in positive.items():
                    self.assertEqual(set(claim["evidence"]), {proofs[a] for a in claim_ports[cid]})

    def test_threshold_boundaries_and_out_of_range_values(self):
        for skill, changes, expected in BOUNDARIES:
            with self.subTest(skill=skill, changes=changes):
                result = self.run_normal(skill, changes)
                self.assertEqual(result["verdict"], expected)
                if expected == "UNKNOWN":
                    self.assertFalse([c for c in result["claims"].values() if c["value"] == "TRUE" and c["evidence"]])

    def test_incidents_are_told_apart(self):
        def positive(skill, changes):
            return {cid for cid, c in self.run_normal(skill, changes)["claims"].items() if c["value"] == "TRUE"}

        self.assertEqual(positive("GP03", {"v6": {"default_route": False, "reachable": False}}),
                         {"gp03_ipv6_address_without_route_v1"})
        self.assertEqual(positive("GP03", {"ra": {"router_advertisements": False, "prefix_count": 0},
                                          "v6": {"global_address": False, "default_route": False, "reachable": False}}),
                         {"gp03_ipv6_not_offered_v1"})
        self.assertEqual(positive("GP05", {"addr": {"wan_ip_class": "private", "upstream_is_router": True}}),
                         {"gp05_double_nat_v1"})
        self.assertEqual(positive("GP05", {"addr": {"wan_ip_class": "cgnat", "upstream_is_router": True}}),
                         {"gp05_carrier_grade_nat_v1"})
        self.assertEqual(positive("GP07", {"sig": {"current_rssi_dbm": -90.0, "rssi_gap_db": 20.0}}),
                         {"gp07_sticky_to_weak_ap_v1"})
        self.assertEqual(positive("GP01", {"dns": {"healthy_count": 0}}), {"gp01_dns_all_resolvers_down_v1"})

    def test_fields_reject_wrong_types_and_values_outside_their_domains(self):
        for skill, workflow in self.workflows.items():
            for alias, spec in workflow["sources"].items():
                for field, schema in spec["value_schema"]["properties"].items():
                    free_text = schema["type"] == "string" and "enum" not in schema and "const" not in schema
                    invalid = [None, 5, ""] if free_text else [None, 5] if schema["type"] == "string" else [None, "0"]
                    if schema["type"] == "boolean":
                        invalid.append(0)
                    elif schema["type"] != "string":
                        invalid.extend([True, float("nan"), float("inf")])
                        if "minimum" in schema:
                            invalid.append(schema["minimum"] - 1)
                        if "maximum" in schema:
                            invalid.append(schema["maximum"] + 1)
                        if schema["type"] == "integer":
                            invalid.append(1.5)
                    elif not free_text:
                        invalid.append("not-a-member")
                    for value in invalid:
                        with self.subTest(skill=skill, alias=alias, field=field, value=value):
                            self.assert_unusable(self.run_normal(skill, {alias: {field: value}}))

    def test_extra_or_missing_fields_are_rejected(self):
        for skill, workflow in self.workflows.items():
            for alias in workflow["sources"]:
                with self.subTest(skill=skill, alias=alias, case="extra"):
                    self.assert_unusable(self.run_normal(skill, {alias: {"unexpected": 1}}))
                with self.subTest(skill=skill, alias=alias, case="missing_field"):
                    row = copy.deepcopy(self.rows[f"{skill}-normal"])
                    del row["sources"][alias]["values"][next(iter(row["sources"][alias]["values"]))]
                    self.assert_unusable(run_scenario(row, batch=BATCH))

    def test_each_source_is_required(self):
        for skill, workflow in self.workflows.items():
            for alias in workflow["sources"]:
                with self.subTest(skill=skill, alias=alias):
                    row = copy.deepcopy(self.rows[f"{skill}-fault"])
                    row["sources"][alias]["values"] = None
                    self.assert_unusable(run_scenario(row, batch=BATCH))


class GapReplaySimTests(unittest.TestCase):
    """GP01..GP07 run in replay_sim with their own IDs and never count as verified Skills."""

    QUESTIONS = {
        "GP01": "có Wi-Fi mà không vào được web",
        "GP02": "một số trang web không tải xong",
        "GP03": "IPv6 hỏng",
        "GP04": "tối đông người dùng là chậm",
        "GP05": "lắp thêm router thì game báo NAT",
        "GP06": "Wi-Fi 5G tự mất khoảng một phút rồi có lại",
        "GP07": "lên tầng mà vẫn bắt điểm phát dưới nhà",
    }

    @classmethod
    def setUpClass(cls):
        cls.profile = replay_sim.prepare_profile()

    def approve(self):
        def fake_read(path, **kwargs):
            doc = read_json(path, **kwargs)
            if Path(path).name == "approvals.json":
                doc["replay_sim"] = copy.deepcopy(self.profile.approval)
            return doc
        return patch.object(dep, "read_json", side_effect=fake_read)

    def test_incident_checks_are_not_among_the_120_skills_or_verified(self):
        self.assertEqual(set(self.profile.incidents.actions), set(SKILLS_GP))
        self.assertFalse(set(SKILLS_GP) & set(self.profile.actions))
        self.assertFalse(set(SKILLS_GP) & accepted_skills())
        self.assertFalse(set(SKILLS_GP) & set(json.loads(ACCEPTANCE.read_text())["skills"]))
        self.assertFalse(set(SKILLS_GP) & set(SkillCatalog.load().skills))
        self.assertIn("incident_checks_digest", self.profile.approval)
        report = coverage_report()
        self.assertEqual(set(report["incident_checks_simulated"]), set(SKILLS_GP))
        self.assertEqual(report["summary"]["levels"]["simulation_verified"], len(accepted_skills()))

    def test_every_check_replays_its_three_scenarios_through_core(self):
        gold = json.loads((batch_paths(BATCH)[0] / "gold.json").read_text())["expected"]
        for state in replay_sim.STATES:
            for sid in SKILLS_GP:
                with self.subTest(skill=sid, scenario=state):
                    replay = replay_sim.ReplaySession(self.profile, state)
                    result = replay_sim_run.run_replay_skill(replay, "test-only", sid, deadline=None)
                    self.assertEqual(result["verdict"], gold[f"{sid}-{state}"])
                    self.assertEqual(len(result["timeline"]), result["calls_this_run"])
                    self.assertEqual(bool(result["evidence_ids"]), state != "missing")
        with self.assertRaises(KeyError):
            self.profile.incidents.samples["GP01"]["fault-unknown"]

    def test_natural_questions_select_the_matching_check(self):
        model = Mock(side_effect=AssertionError("known phrases must route deterministically"))
        launcher = SkillLauncher(factory=lambda mode, **kw: dep.composition(mode, **kw))
        chat = skill_chat.SkillChat(launcher, model_factory=model, fast=True)
        texts = self.profile.incidents.diagnostics["claim_text"]
        with self.approve():
            for state, expected in (("normal", "HEALTHY"), ("fault", "FAULT"), ("missing", "UNKNOWN")):
                for sid, question in self.QUESTIONS.items():
                    with self.subTest(skill=sid, scenario=state):
                        r = chat.chat(question, mode="replay_sim", scenario=state)
                        launcher.close(r["session_id"])
                        self.assertEqual([run["skill_id"] for run in r["skill_runs"]], [sid])
                        self.assertEqual(r["verdict"], expected)
                        self.assertIn(replay_sim.NOTICE, r["answer"])
                        said = [t for c, t in texts.items() if c.startswith(sid.lower()) and t in r["answer"]]
                        self.assertEqual(bool(said), expected != "UNKNOWN")
                        self.assertEqual(bool(r["evidence_ids"]), expected != "UNKNOWN")
        model.assert_not_called()

    def test_findings_state_measurements_without_naming_a_cause(self):
        facts = {"expansion.wan_mss": {"proto": "pppoe", "mtu_bytes": 1492, "mss_clamping": False},
                 "expansion.ipv6_connectivity": {"global_address": True, "default_route": False, "reachable": False},
                 "expansion.system_load": {"cpu_pct": 96.0, "load1": 4.2, "mem_pct": 88.0, "clients_count": 38},
                 "expansion.wan_addressing": {"wan_ip_class": "cgnat", "upstream_is_router": False},
                 "expansion.radio_events": {"radar_detected_count": 2, "channel_changes": 2,
                                            "on_dfs_channel": True, "observation_window_s": 3600},
                 "expansion.client_ap_signal": {"current_rssi_dbm": -82.0, "rssi_gap_db": 19.0,
                                                "roam_count": 0, "observation_window_s": 3600}}
        for port, value in facts.items():
            with self.subTest(port=port):
                line = skill_chat._simulation_finding({"port": port, "value": value})
                self.assertTrue(line)
                self.assertNotRegex(line.lower(), "nguyên nhân|do |vì |lỗi")


if __name__ == "__main__":
    unittest.main()
