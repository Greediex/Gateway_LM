"""Golden fixtures for the C++ port (T10): input -> Contract 0 -> Contract A -> events -> B -> C -> verdict.

Synthetic replay through the v0.1 contracts on the resolver route. The random
Case id is normalised to ``golden-<case>`` so a rebuild is byte-identical.
Run from the pilot directory:  python docs/contracts/golden/build_golden.py [--check]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from gateway_pilot.core import read_json  # noqa: E402
from gateway_pilot.graph_v3.graphs import GraphRegistry  # noqa: E402
from gateway_pilot.workflow import diagnose, replay_from_fixture  # noqa: E402

OUT = Path(__file__).resolve().parent
CASES = {  # golden id -> (fixture, request, workflow)
    "wan_link_down": ("GLM-01-0", "Cổng WAN có bị mất kết nối không?", "WF-018"),
    "gateway_dns_failure": ("GLM-06-0", "Router có phân giải tên miền được không?", "WF-023"),
    "dhcp_pool_exhausted": ("GLM-10-0", "Laptop An không nhận được địa chỉ IP", "WF-024"),
    "system_memory_pressure": ("GLM-15-0", "Router có thiếu RAM không?", "WF-039"),
    "client_path_unverified": ("GLM-21-1", "Laptop An vẫn có Wi-Fi, sao không truy cập Internet?", "WF-INTERNET"),
    "write_denied": ("GLM-23-0", "Đổi DNS router sang 8.8.8.8", None),
}


def golden(name, registry, fixtures):
    fixture_id, request, workflow = CASES[name]
    replay = replay_from_fixture(fixtures[fixture_id], registry)
    result = diagnose(request, replay, registry=registry, route="resolver", workflow=workflow)
    graph = result.get("graph", {})
    document = {
        "golden_id": name, "note": "synthetic replay; not a router measurement",
        "input": {"request": request, "workflow": result.get("workflow"), "fixture": fixture_id,
                  "capabilities": replay["capabilities"], "devices": [d["selector"] for d in replay["devices"]],
                  "gateway_functions": sorted(replay["world"])},
        "contract_0": graph.get("contract_0", []), "contract_a": graph.get("contract_a", []),
        "events": graph.get("events", []), "contract_b": graph.get("contract_b", []),
        "contract_c": graph.get("contract_c"), "claims": graph.get("claims"),
        "verdict": {k: result["terminal"][k] for k in ("action", "diagnosis", "evidence_ids")},
        "case_status": result["case_status"],
    }
    text = json.dumps(document, ensure_ascii=False, indent=1, sort_keys=True, default=str)
    case_id = (graph.get("contract_c") or {}).get("case_id")
    if case_id:
        text = text.replace(case_id, f"golden-{name}")
    return text + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if a rebuild differs from the committed files")
    args = parser.parse_args()
    registry = GraphRegistry.from_v01()
    fixtures = {c["id"]: c for c in read_json(ROOT / "data/cases.json")}
    changed = []
    for name in CASES:
        text, path = golden(name, registry, fixtures), OUT / f"{name}.json"
        if args.check:
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                changed.append(name)
        else:
            path.write_text(text, encoding="utf-8", newline="")
    if changed:
        raise SystemExit("golden fixtures differ: " + ", ".join(changed))
    print("ok", len(CASES))


if __name__ == "__main__":
    main()
