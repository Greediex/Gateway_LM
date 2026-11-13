"""Preview trusted Feature metadata without connecting runtime capabilities."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from gateway_pilot.core import ROOT, PlanError
from gateway_pilot.command_catalog.builder import read_registry
from gateway_pilot.command_catalog.loader import read_json, digest
from gateway_pilot.adapters.bindings import TargetContext
from gateway_pilot.features.registry import FeatureRegistry, read_feature_manifests, read_feature_flags
from gateway_pilot.application.feature_availability import AvailabilityService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--policy", type=Path, default=ROOT / "config/catalog_policy.example.json")
    parser.add_argument("--manifests", type=Path, default=ROOT / "examples/features.replay.json")
    parser.add_argument("--flags", type=Path, default=ROOT / "config/feature_flags.example.json")
    parser.add_argument("--scope", choices=("client", "gateway"), default="client")
    args = parser.parse_args(argv)
    try:
        policy = read_json(args.policy, max_bytes=1048576)
        registry = FeatureRegistry(read_registry(args.registry, policy), policy,
                                   read_feature_manifests(args.manifests), read_feature_flags(args.flags))
        service = AvailabilityService(registry)
        context = TargetContext(args.scope, "metadata-preview", "0" * 64)
        reports = [service.evaluate(feature["feature_id"], context=context,
                                    permissions=frozenset({"network.read", "system.read"}),
                                    policy_context_id=digest("metadata-preview")) for feature in registry.describe()]
        print(json.dumps({"protocol": "feature-preview/v1", "mode": "metadata_preview",
                          "runtime_connected": False, "features": reports}, ensure_ascii=False, indent=2))
        return 0
    except (PlanError, OSError) as exc:
        print(json.dumps({"validation": "FAIL", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
