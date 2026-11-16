"""Explicit local laptop/replay Skill launcher: python -m scripts.skills."""
import argparse
import json
from gateway_pilot.application.skill_launcher import SkillLauncher


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('list', 'run'))
    parser.add_argument('skill_id', nargs='?')
    parser.add_argument('--mode', choices=('live', 'replay'), default='live')
    args = parser.parse_args()
    launcher = SkillLauncher()
    if args.command == 'list':
        result = launcher.catalog(args.mode)
    else:
        if not args.skill_id:
            parser.error('run requires a skill_id')
        session = launcher.create_session(args.mode)
        try:
            result = launcher.run(session['session_id'], args.skill_id)
        finally:
            launcher.close(session['session_id'])
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
