# FND-07 — Laptop Connectivity/Wi-Fi → verified snapshot → UI

**Date:** 13/11/2026. **Base:** `8ac04b6ad633d1e2b445303e191749a70f4ab537`, branch `v2`. [Guide](../LAPTOP_NETWORK_V2.md), [plan](../superpowers/plans/2026-11-13-fnd-07-laptop-demo.md).

## Delivered

- Dedicated laptop-network catalog: 7 bounded READ Functions, selected exact versions and committed reviewed registry approval digest. Baseline v0.1, seed replay and prior laptop profile unchanged.
- Linux backend reads current NetworkManager Wi-Fi without rescan/change, kernel route/IPv4, 4-packet source-bound gateway/public-IP probes and interface-scoped DNS. Fixed IP/domain; timeout/byte/schema gates; no HTTP-provided commands/targets.
- FND-06 shared Core execution, verified immutable snapshot, consumption TTL/environment recheck and Connectivity/Wi-Fi rules. Snapshot rejects raw dictionaries, stale/context-mismatched facts and implicit replay.
- Existing UI supports Linux live Overview + chat, evidence/provenance/time/units, manual refresh, missing/error/issue/measurement states and automatic clearing after expiry. Router health unavailable. Windows/replay behavior retained.
- README rewritten around branch v2, Linux setup, quick test, Windows/replay and precise measurement limits. CI uses the existing workflow_dispatch on v2. Updating the push trigger was rejected because the existing OAuth token lacks workflow scope, so workflow configuration is unchanged.

## Validation

| Check | Result |
|---|---|
| New focused tests | **28 pass**, parsers/provider/snapshot/rules/Core application/HTTP |
| Final full unittest discovery | **622 total, 617 pass, 5 skip, 0 failures/errors**, 64.978 seconds |
| Repository hygiene + Markdown links | PASS |
| JavaScript syntax + diff whitespace | PASS |
| Frozen data/benchmark checks against base | 19/19 tracked files unchanged |
| v0.1 golden Function digest vectors | 17/17 unchanged |
| Legacy replay smoke | GLM-04-0 WAN and GLM-21-1 client: valid JSON, exit 0 |
| Independent review | Identified issues fixed and rechecked; no unresolved findings after scoped re-review |

Negative and boundary coverage includes escaped nmcli fields, radio off/disconnected, missing metrics, malformed Wi-Fi/route/ping, 100% loss/missing RTT, timeout, route/resolver changes, incorrect target/provenance/contract, snapshot mutation/expiry/clock rollback, slow context recheck, no-route/DNS/loss rules, no WRITE/router inventory execution and local-only HTTP/config isolation.

## Actual Linux laptop acceptance

At **2026-11-13 07:53:35 UTC**, Python **3.12.3**, LinuxWifiBackend **1.0.0**, `POST /api/network {}` executed **7 Core calls**, produced **7 verified outputs**, **1 plan**, no missing ports or execution errors. Public IP and DNS responded; Wi-Fi signal at that sample was below the documented heuristic 40% threshold. No causal diagnosis is asserted.

The actual Internet route used **Ethernet**, while Wi-Fi was associated. UI correctly stated that Ethernet probes do not prove Internet over Wi-Fi. Local interfaces and evidence details were inspected; SSID/BSSID/IP identifiers are excluded from this committed report. Redacted acceptance counts are in ignored `runs/fnd-07/live-summary.json`.

Browser checks confirmed no automatic initial collection, loading, live MEASURED/ISSUE cards, interface distinction, compact/full evidence details and STALE clearing after expiry. A real Wi-Fi chat request returned verified measurements and scope caveats. Final trace wiring reports actual Core calls rather than an empty timeline, and Linux labels use Core rather than claiming GoS/LLM use.

UI behavior checks with a mocked DOM also cover missing/error states, source-switch/in-flight response isolation, Windows no-Linux-endpoint behavior and a slow 18-second response retaining its final 12-second TTL. These are UI contract checks, not hardware outage experiments.

Review caught missing RTT displayed as -1 ms, double subtraction of collection time from remaining TTL, and freshness timing around a slow environment callback. Fixed with explicit missing RTT text, absolute server expiry + receipt monotonic deadline, and clock recapture after environment validation. Regression tests cover the backend/freshness fixes; UI mock checks cover the deadline logic.

## Limits

- Five Windows-only tests skipped on Linux; no new Windows hardware acceptance.
- Disconnection/radio-off, timeouts, changed routes/resolvers and bad responses were tested with mocks. No deliberate laptop network disconnection or router reconfiguration was performed.
- Signal remains percent; AP advertised Mbps is not negotiated link rate or throughput. No RSSI dBm, speedtest or web-access claim.
- IPv4 IP/DNS checks are short measurements on the kernel-selected route, not continuous monitoring or proof of all Internet applications. Other clients/AP inventory/router CPU/RAM remain unsupported.
- No router firmware, WRITE, NPU or product reliability acceptance.

Local logs/artifacts under `runs/fnd-07/` are ignored. Hosted CI is verified for the pushed commit and its exact URL/result is reported separately after push. Local test server uses localhost port 8766; default launcher port remains 8765.
