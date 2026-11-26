# LAB-01: Skills read the OpenWrt lab router through Core

Measured on 2026-11-26 against the rootless QEMU lab in `../openwrt_lab`
(OpenWrt 25.12.6 x86-64, three VMs). **Emulated, not hardware**: no board,
firmware hash, Wi-Fi radio or NPU numbers. Nothing here is "Router verified" (L2).

## What runs

`scripts/lab_skills.py` reads the lab router over rpcd/ubus as the read-only
`gwlm` account (`127.0.0.1:18080/ubus`). The ACL lives on the router; the
transport (`gateway_pilot/adapters/ubus_http.py`) refuses any non-loopback URL.
`gateway_pilot/skill_expansion/lab_backend.py` maps raw ubus replies to three
proposed Skill ports and validates them against the port schema. The read
happens inside Core through `core_replay_smoke_v2.smoke(..., lab_transport=...)`,
the same path as simulation, and the same versioned Claims judge the result.

| Skill | Port | ubus reads |
|---|---|---|
| E02 WAN link | `expansion.wan_link` | `network.interface.wan status`, `network.device status` (carrier) |
| E03 default route | `expansion.wan_routes` | `network.interface.wan status` (`route`) |
| H08 firmware precheck | `expansion.firmware_info` | `system board`, `system info` (`root.avail`) |

Evidence carries source `openwrt_lab/ubus-ro`. The disposable catalog declares
the port provenance `openwrt_lab/`, so Core's binding check would reject a lab
read labelled as synthetic replay, and the reverse.

## Results

```bash
python3 ../openwrt_lab/lab.py up
.venv-graph/bin/python -m scripts.lab_skills
python3 ../openwrt_lab/lab.py fault wan_down
```

| Lab state | E02 | E03 | H08 |
|---|---|---|---|
| `wan_down` (cable pulled) | FAULT `wan_link_down_v1` | FAULT `no_default_route_v1` | HEALTHY, 73.6 MB free |
| WAN restored, uptime < 60 s | UNKNOWN | HEALTHY `single_default_route_v1` | HEALTHY |
| WAN restored, uptime 65 s | HEALTHY `wan_link_stable_v1` | HEALTHY | HEALTHY |

Each run made one Core call per Skill. The UNKNOWN right after restore is the
Claim working as declared: HEALTHY needs 60 s of uptime.

## Limits

- Three Skills only. DNS, latency and loss faults (`dns_fail`, `wan_latency`,
  `wan_loss`) need an active probe; the read-only ACL has no ping or resolve
  method, so those Skills are not wired.
- Probe is a real read: rpcd's `session access` needs its own grant, which the
  account lacks on purpose.
- Thresholds are still the synthetic heuristics; the lab does not calibrate them.
- `tests/test_lab_backend.py` covers the mapping and Core path with a fake
  transport; the lab itself is not part of CI.
