"""Synthetic catalog scale benchmark. No adapters, firmware or runtime plans."""
from __future__ import annotations

import argparse
import copy
import json
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from gateway_pilot.core import ROOT
from gateway_pilot.command_catalog.builder import build_registry, read_registry
from gateway_pilot.command_catalog.loader import canonical_bytes, load_catalog, read_json
from gateway_pilot.command_catalog.validator import validate_catalog
from gateway_pilot.command_catalog.indexes import dependency_closure, discover


BUDGETS = {"validate_ms": 30000, "build_ms": 60000, "read_ms": 30000,
           "peak_rss_mib": 512, "closure_p95_ms": 100}


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(value))


def generate_catalog(root: Path, count: int) -> tuple[dict, dict]:
    """Independent chain with alternating domains, not 1,000 real commands."""
    template = read_json(ROOT / "catalog/functions/clients/clients.resolve.json")
    base_port = read_json(ROOT / "catalog/ports/client.identity.json")
    skill = read_json(ROOT / "catalog/skills/client.identity.inspect.json")
    # Keep each Skill within its 64-reference contract limit.
    selection = {"schema_version": "0.2.0", "kind": "selection", "functions": {}, "ports": {}}
    for number in range(count):
        fid, pid = f"synthetic.read_{number:04}", f"synthetic.port_{number:04}"
        sid = f"synthetic.skill_{number:04}"
        previous = f"synthetic.port_{number - 1:04}"
        function = copy.deepcopy(template)
        function.update(function_id=fid, domain="alpha" if number % 2 == 0 else "beta",
                        description="Synthetic catalog benchmark metadata only.", version="1.0.0",
                        skill_refs=[{"skill_id": sid, "version": "1.0.0"}],
                        inputs={previous: "1.0.0"} if number else {}, outputs={pid: "1.0.0"})
        port = copy.deepcopy(base_port)
        port.update(port_id=pid, version="1.0.0")
        member = copy.deepcopy(skill)
        member.update(skill_id=sid, requires=copy.deepcopy(function["inputs"]), produces={pid: "1.0.0"},
                      completion_ports={pid: "1.0.0"}, function_refs={fid: "1.0.0"})
        _write(root / "functions" / function["domain"] / f"{fid}.json", function)
        _write(root / "ports" / f"{pid}.json", port)
        _write(root / "skills" / f"{sid}.json", member)
        selection["functions"][fid] = "1.0.0"
        selection["ports"][pid] = "1.0.0"
    return selection, read_json(ROOT / "config/catalog_policy.example.json")


def _timed(call):
    start = time.perf_counter()
    result = call()
    return result, (time.perf_counter() - start) * 1000


def measure(count: int) -> dict:
    import resource  # Linux/macOS measurement; catalog APIs also work on Windows.
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        selection, policy = generate_catalog(root / "catalog", count)
        catalog, load_ms = _timed(lambda: load_catalog(root / "catalog"))
        _, validate_ms = _timed(lambda: validate_catalog(catalog, policy))
        output = root / "registry.json"
        artifact, build_ms = _timed(lambda: build_registry(catalog, selection, policy, output))
        _, read_ms = _timed(lambda: read_registry(output, policy))
        discovery, closure = [], []
        for _ in range(25):
            _, elapsed = _timed(lambda: discover(artifact["indexes"], domain="beta"))
            discovery.append(elapsed)
            result, elapsed = _timed(lambda: dependency_closure(artifact["indexes"], [f"synthetic.read_{count-1:04}"]))
            assert len(result) == count and result[0] == "synthetic.read_0000"
            closure.append(elapsed)
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        rss_mib = peak / (1048576 if sys.platform == "darwin" else 1024)
        metrics = {"function_count": count, "source_documents": count * 3,
                   "load_ms": load_ms, "validate_ms": validate_ms, "build_ms": build_ms, "read_ms": read_ms,
                   "artifact_bytes": output.stat().st_size, "peak_rss_mib": rss_mib,
                   "discovery_p50_ms": statistics.median(discovery),
                   "discovery_p95_ms": sorted(discovery)[23], "closure_p50_ms": statistics.median(closure),
                   "closure_p95_ms": sorted(closure)[23], "dependency_closure_correct": True,
                   "runtime_compile_measured": False, "target_verified_executable_count": 0}
        metrics["budgets_met"] = all(metrics[key] <= bound for key, bound in BUDGETS.items())
        return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sizes", type=int, nargs="+", default=[10, 100, 1000])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=int, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if sys.platform == "win32":
        parser.error("peak RSS benchmark requires Linux/macOS resource.getrusage")
    sizes = [args.worker] if args.worker is not None else args.sizes
    if not sizes or any(not 1 <= n <= 1000 for n in sizes):
        parser.error("sizes must be between 1 and 1000")
    if args.worker is not None:
        result = measure(args.worker)
    else:
        cases = []
        with tempfile.TemporaryDirectory() as temporary:
            for count in sizes:
                target = Path(temporary) / f"{count}.json"
                completed = subprocess.run([sys.executable, "-m", "scripts.analysis.benchmark_catalog", "--worker", str(count),
                                            "--output", str(target)], check=False, timeout=180)
                if completed.returncode not in (0, 1) or not target.is_file():
                    raise RuntimeError("synthetic_catalog_worker_failed")
                cases.append(json.loads(target.read_text()))
                print(f"Synthetic catalog {count}: budgets_met={cases[-1]['budgets_met']}", flush=True)
        result = {"protocol": "catalog-scale/v1", "data_kind": "synthetic_metadata_only",
                  "host": {"system": platform.system(), "machine": platform.machine(),
                           "python": platform.python_version()},
                  "measurement": "One fresh subprocess per size; 25 warm discovery/closure samples; OS cache uncontrolled.",
                  "budgets": BUDGETS, "cases": cases, "budgets_met": all(c["budgets_met"] for c in cases)}
    _write(args.output, result)
    return 0 if result["budgets_met"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
