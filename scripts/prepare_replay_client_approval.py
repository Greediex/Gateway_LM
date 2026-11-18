"""Print proposed client replay pins for human review; never write approvals."""
from __future__ import annotations

import json
from gateway_pilot.command_catalog.builder import build_registry
from gateway_pilot.command_catalog.loader import digest, load_catalog, read_json
from gateway_pilot.core import ROOT
from gateway_pilot.skill_expansion.client_replay import normal_fixtures
from gateway_pilot.skill_expansion.replay_backend import StrictSkillReplayBackend


def proposed_approval() -> dict[str, str]:
    config = ROOT / 'config/skill_launcher'
    catalog = load_catalog(ROOT / 'examples/skill_deployments/client_replay_v1')
    artifact = build_registry(catalog, read_json(config / 'replay_client.selection.json'),
                              read_json(config / 'replay_client.policy.json'),
                              ROOT / 'runs/skill-launcher/replay_client.proposed.registry.json')
    fixtures = normal_fixtures()
    StrictSkillReplayBackend(artifact['functions'], artifact['ports'], fixtures)
    return dict(registry_digest=artifact['content_digest'],
                actions_digest=digest(read_json(config / 'replay_client.actions.json')),
                fixtures_digest=digest(fixtures), backend_id='expansion.synthetic_replay',
                backend_revision=StrictSkillReplayBackend.revision,
                source=StrictSkillReplayBackend.source)


def main() -> int:
    print(json.dumps({'mode': 'replay_client', 'proposed_approval': proposed_approval(),
                      'currently_approved': read_json(ROOT / 'config/skill_launcher/approvals.json').get('replay_client'),
                      'action': 'Human review required; does not modify approvals.json. Synthetic only.'}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
