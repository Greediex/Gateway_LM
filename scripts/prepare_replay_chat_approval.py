"""Print the digest an operator must review before enabling replay Skill chat.

Read-only: never writes config/skill_launcher/approvals.json. A human operator
reviews replay.diagnostics.json, then adds the printed value as
approvals["replay"]["diagnostics_digest"] in a separate, attributed commit.
"""
from __future__ import annotations

import json

from gateway_pilot.command_catalog.loader import digest, read_json
from gateway_pilot.core import ROOT


def main() -> int:
    path = ROOT / "config/skill_launcher/replay.diagnostics.json"
    doc = read_json(path)
    approvals = read_json(ROOT / "config/skill_launcher/approvals.json")
    current = approvals.get("replay", {}).get("diagnostics_digest")
    print(json.dumps({
        "file": str(path.relative_to(ROOT)),
        "proposed_diagnostics_digest": digest(doc),
        "currently_approved": current,
        "workflows": sorted(doc["workflows"]),
        "claims": [(c["claim_id"], c["severity"]) for c in doc["claims"]],
        "action": "Human review required; this script does not modify approvals.json.",
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
