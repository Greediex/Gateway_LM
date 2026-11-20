"""Print the reviewed REPLAY-SIM pin proposal without writing files."""
from __future__ import annotations

import json

from gateway_pilot.skill_expansion.coverage import accepted_skills
from gateway_pilot.skill_expansion.replay_sim import MODE, prepare_profile


def main() -> int:
    # Offline reviewer verifies the original acceptance against its scorer inputs.
    accepted = accepted_skills()
    profile = prepare_profile()
    if set(profile.actions) != accepted:
        raise ValueError('skill_sim_acceptance_mismatch')
    print(json.dumps({'mode': MODE, 'proposed_approval': profile.approval,
                      'skill_count': len(accepted), 'skills': sorted(accepted),
                      'igate_simulated': sorted(profile.igate.actions)}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
