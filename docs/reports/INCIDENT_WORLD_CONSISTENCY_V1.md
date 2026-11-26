# Incident world consistency matrix

WORLD-01 ran **1,582** independent synthetic READ replays across **14**
incident worlds and **113** approved replay entries per world. The entries
comprise 101 catalog Skills, five iGate Skills and seven supplemental GP
checks. Each run used a fresh session and the existing Core and Verifier.
The test operator supplied the proposed replay approval in memory.

The all-Skill run executed **2,408 READ calls**. Every expected source produced
evidence. There were **33 FAULT**, **1,466 HEALTHY** and **83 UNKNOWN** verdicts.
Every FAULT below had evidence. There were **zero cross-Skill Claim conflicts**
in the nine audited quantity groups, checked in every world. The groups cover
CPU, temperature, RSSI, SNR, resolver availability, the IPv4 default route,
upstream reachability, airtime and queue delay.

| Scenario | FAULT Skills | FAULT | HEALTHY | UNKNOWN | Claim conflicts |
| --- | --- | ---: | ---: | ---: | ---: |
| INC-24G-COCHANNEL | B05, B06 | 2 | 104 | 7 | 0 |
| INC-BUFFERBLOAT | G01, G02, G06, G07, G08 | 5 | 102 | 6 | 0 |
| INC-CAPACITY | A07, GP04 | 2 | 106 | 5 | 0 |
| INC-CGNAT | E05, GP05 | 2 | 105 | 6 | 0 |
| INC-DFS-RADAR | GP06 | 1 | 106 | 6 | 0 |
| INC-DHCP-EXHAUST | D02 | 1 | 107 | 5 | 0 |
| INC-DNS-FAIL | F02, GP01 | 2 | 106 | 5 | 0 |
| INC-DOUBLE-NAT | GP05 | 1 | 107 | 5 | 0 |
| INC-IPV6-BROKEN | GP03 | 1 | 107 | 5 | 0 |
| INC-OVERHEAT-REBOOT | H05, H07 | 2 | 105 | 6 | 0 |
| INC-PPPOE-MTU | C08, GP02 | 2 | 106 | 5 | 0 |
| INC-STICKY-CLIENT | B04, GP07, SK02 | 3 | 104 | 6 | 0 |
| INC-WAN-DOWN | E03, E08, IG03, K07, M05, O01, O07 | 7 | 96 | 10 | 0 |
| INC-WEAK-SIGNAL | B04, SK02 | 2 | 105 | 6 | 0 |

## Snapshot checks

The versioned world layer applies current overrides across base, iGate and
GP readers, including the sources selected by joint checks. Values at a given
port, scope, target and timestamp were identical. Earlier history samples
remain separate observations. The V2 timeline places K02's baseline and
K07's prior failure at distinct offsets from the other history readings.

- Capacity reported 96% CPU, 88% RAM and 38 devices across the relevant
  resource and inventory ports. Both iGate device views flagged truncated
  inventory, and the application-session view marked its list incomplete.
  SK08 assessed storage and temperature.
- The co-channel world reports channel 6 at 2.4 GHz. GP06 returned UNKNOWN
  because its DFS check requires a 5 GHz sample.
- L07 returned UNKNOWN in one-gateway worlds because its check requires
  two gateways. An UNKNOWN can coexist with verified source measurements.

Reproduce the coherence assertions and exact verdict matrix with
`.venv-graph/bin/python -m unittest tests.test_incident_replay.IncidentReplayTests.test_each_world_keeps_unrelated_checks_at_their_normal_verdict`.
The contradiction table compares declared Claims about selected quantities.
These results describe the modeled snapshots and do not establish device
behavior or real causation.
