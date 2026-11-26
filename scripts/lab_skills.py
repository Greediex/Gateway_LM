"""LAB-01: run Skills against the OpenWrt lab router through the same Core and Claims.

Reads over ubus as the lab's read-only ``gwlm`` account (127.0.0.1:18080).
Results are "emulated" (QEMU VMs), never "Router verified". Inject faults with
``python3 ../openwrt_lab/lab.py fault wan_down`` and ``clear`` between runs.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateway_pilot.adapters.ubus_http import UbusHttpReadTransport
from gateway_pilot.skill_expansion.coverage import DIRECT_BATCHES
from scripts.core_replay_smoke_v2 import smoke
from scripts.simulate_skills import assess_claims

ROOT = Path(__file__).resolve().parents[1]
SKILLS = {'E02': 'expansion.wan_link', 'E03': 'expansion.wan_routes', 'H08': 'expansion.firmware_info'}


def diagnostics(skill_id: str) -> Path:
    return ROOT / 'config/skill_launcher' / f'{DIRECT_BATCHES[skill_id[0]][1]}.diagnostics.json'


def run(transport, skill_ids=tuple(SKILLS)) -> list[dict]:
    rows = []
    for sid in skill_ids:
        result = smoke(SKILLS[sid], lab_transport=transport, require_fact=False,
                       assess=lambda state, sid=sid: assess_claims(state, sid, diagnostics(sid)))
        claims = [cid for cid, c in result['assessment']['claims'].items()
                  if c['value'] == 'TRUE' and c['evidence']]
        rows.append({'skill': sid, 'verdict': result['assessment']['verdict'], 'claims': claims,
                     'value': result['fact_value'], 'source': result['source'],
                     'core_calls': result['core_calls']})
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab-dir', type=Path, default=ROOT.parent / 'openwrt_lab')
    parser.add_argument('--url', default='http://127.0.0.1:18080/ubus')
    options = parser.parse_args()
    transport = UbusHttpReadTransport(options.url, 'gwlm', options.lab_dir / 'run/gwlm.secret')
    rows = run(transport)
    print(json.dumps({'emulated_lab': True, 'router_verified': False, 'rows': rows},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
