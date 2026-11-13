"""Developer CLI for READ metadata catalogs; does not start a device runtime."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gateway_pilot.core import ROOT, PlanError
from gateway_pilot.command_catalog.builder import build_registry, read_registry, report_registry
from gateway_pilot.command_catalog.loader import load_catalog, read_json
from gateway_pilot.command_catalog.validator import select_catalog, validate_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "build", "report"):
        command = commands.add_parser(name)
        command.add_argument("--policy", type=Path, default=ROOT / "config/catalog_policy.example.json",
                             help="Trusted probe-name vocabulary, not probe approval")
        if name == "report":
            command.add_argument("--registry", type=Path, required=True)
        else:
            command.add_argument("--source", type=Path, default=Path("catalog"))
            command.add_argument("--selection", type=Path,
                                 default=ROOT / "config/catalog_selection.example.json" if name == "build" else None)
        if name == "build":
            command.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        policy = read_json(args.policy, max_bytes=1048576)
        if args.command == "report":
            result = report_registry(read_registry(args.registry, policy))
        else:
            catalog = load_catalog(args.source)
            selection = read_json(args.selection, max_bytes=1048576) if args.selection else None
            if args.command == "validate":
                indexed = validate_catalog(catalog, policy)
                if selection is not None:
                    validate_catalog(select_catalog(selection, indexed), policy)
                result = {"protocol": "catalog-validation/v1", "validation": "PASS",
                          "counts": {key: len(catalog[key]) for key in ("functions", "ports", "skills")},
                          "selection_checked": selection is not None, "execution_enabled": False}
            else:
                result = report_registry(build_registry(catalog, selection, policy, args.output))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except (PlanError, OSError) as exc:
        print(json.dumps({"validation": "FAIL", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
