"""CAT-01: validate pinned metadata profile and export coverage; never execute."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from gateway_pilot.core import ROOT
from gateway_pilot.command_catalog.loader import read_json
from gateway_pilot.skill_expansion.profiles import DEFAULT_PROFILE, build_profile, load_bundle


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, default=DEFAULT_PROFILE)
    parser.add_argument('--registry-output', type=Path, default=ROOT/'runs/skill-profiles/wifi_gateway_replay_v1.registry.json')
    args = parser.parse_args(argv)
    try:
        profile = read_json(args.profile, max_bytes=1048576)
        _, report = build_profile(profile, load_bundle(), args.registry_output)
    except (ValueError, OSError, TypeError, KeyError) as exc:
        # Metadata tooling errors must not masquerade as successful execution.
        print(json.dumps({'valid':False, 'error':str(exc), 'execution_enabled':False}))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
