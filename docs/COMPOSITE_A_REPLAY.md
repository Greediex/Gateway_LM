# Batch A composite replay v1

`config/skill_launcher/replay_a_composite.diagnostics.json` declares the synthetic
A03/A05/A07 source requirements and Claims. It is not a deployment approval or a
new READ Function registry. `scripts.simulate_composites` executes the existing
inventory, identity-consistency and vendor measurements through the existing
smoke harness, `execute_ready_once` and `GraphRunner.step`. Client measurements
reuse the existing synthetic identity dependency.

Gateway and client sources retain their separate Core states and scoped bindings.
The local Claim view resolves source aliases to usable facts without copying
observations into another CaseState, creating ports, or weakening scope gates.
The simulation explicitly binds synthetic targets; an inventory count does not
prove membership of a particular client. Before evaluating Claims, every source
must pass its Core checks, permission/capability checks, expected scope/target,
synthetic provenance and matching environment. Missing or invalid sources make
**all** composite Claims UNKNOWN, even if another source indicates a fault.
Claim evidence lists contain the original Core evidence IDs.

| Skill | Sources | Meaning of HEALTHY / FAULT in this simulation |
|---|---|---|
| A03 | inventory + identity consistency | Nonempty inventory and consistent identity / IP-MAC or hostname conflict |
| A05 | inventory + vendor | Nonempty inventory and known, nonempty OUI vendor / unknown OUI |
| A07 | current inventory + previous inventory | Stable count / count increased or decreased |

These are bounded predicates, not causal RCA or repaired incidents. A03 does not
implement a per-device merge. A05 does not infer device type from vendor. A07
does not identify individual arrivals/departures: existing inventory only supplies
count and segment. These limits are returned with each assessment. Full catalog
Skill acceptance and production launchability are not asserted here.

A07 uses two independently Core-verified samples with distinct evidence IDs,
strictly increasing declared simulation timestamps, identical segment, target and
environment, and nonnegative counts. Both samples must remain usable on their
Core clocks. Simulation timestamps describe the fixture sequence; they do not
replace observation timestamps or extend live TTL. Comparison thresholds come
only from the verified earlier count. Source aliases never become evidence.

Fixtures and scorer-only expectations have their own version in
`data/skill_expansion_v1/simulation_composite_v1/`. Gold is read only after
execution. The existing direct-scenario `evaluate()` API remains unchanged;
`python -m scripts.simulate_skills` scores both direct and composite suites.
No production approval is written. Coverage remains unmodified pending WP-A5.
