"""Local LLM goal proposal evaluation and conservative dev-only calibration.

Input is a labeled JSONL holdout prepared *independently* of the model.
No synthetic examples are reported as production accuracy; no request text,
raw completion, client data, or router identifiers are persisted in results.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from gateway_pilot.core import ROOT, read_json
from gateway_pilot.graph_v3.graphs import GraphRegistry
from gateway_pilot.graph_v3.llm_goals import BoundedGoalProposer
from gateway_pilot.graph_v3.ollama_goal_model import OllamaGoalModel
from gateway_pilot.graph_v3.state import CaseState
from gateway_pilot.graph_v3.task_decomposer import TaskDecomposer

THRESHOLDS = (0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 0.99)


def read_suite(path, registry, fixtures):
    p = Path(path)
    if not p.is_file() or p.stat().st_size > 5_000_000:
        raise ValueError("invalid_goal_suite")
    rows, seen = [], set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or set(row) != {
            "id", "split", "case_id", "group", "request", "expected_goals", "kind"
        }:
            raise ValueError("invalid_goal_suite_row")
        if (row["id"] in seen or not isinstance(row["id"], str)
                or not 1 <= len(row["id"]) <= 128 or
                row["split"] not in {"dev", "test"} or
                not isinstance(row["group"], str) or not 1 <= len(row["group"]) <= 80
                or not isinstance(row["request"], str) or not 1 <= len(row["request"]) <= 2000
                or row["case_id"] not in fixtures or row["kind"] not in
                {"READ", "WRITE", "UNKNOWN"}
                or not isinstance(row["expected_goals"], list)
                or any(not isinstance(g, str) or g not in registry.ports for g in row["expected_goals"])
                or len(set(row["expected_goals"])) != len(row["expected_goals"])
                or (row["kind"] != "READ" and row["expected_goals"])):
            raise ValueError("invalid_goal_suite_row")
        seen.add(row["id"])
        rows.append(row)
    if not {r["split"] for r in rows} >= {"dev", "test"}:
        raise ValueError("goal_suite_needs_dev_and_test")
    if len(rows) > 2000:
        raise ValueError("goal_suite_too_large")
    return rows


class OneShotModel:
    local_only = True

    def __init__(self, output):
        self.output = output

    def propose_goals(self, _request, _catalog):
        return self.output


def assess(rows, outputs, registry, fixtures, threshold):
    correct, wrong, abstained, unsafe, total = 0, 0, 0, 0, 0
    by_group = {}
    for row in rows:
        state = CaseState(fixtures[row["case_id"]], registry)
        proposer = BoundedGoalProposer(
            OneShotModel(outputs[row["id"]]), min_confidence=threshold
        )
        result = proposer.propose(
            row["request"], registry, state, TaskDecomposer(registry)
        )
        total += 1
        group = by_group.setdefault(row["group"], {
            "total": 0, "correct": 0, "wrong": 0, "abstained": 0
        })
        group["total"] += 1
        if result.decision != "READY":
            abstained += 1
            group["abstained"] += 1
        elif row["kind"] == "READ" and set(result.goals) == set(row["expected_goals"]):
            correct += 1
            group["correct"] += 1
        else:
            wrong += 1
            group["wrong"] += 1
            if row["kind"] == "WRITE":
                unsafe += 1
    accepted = correct + wrong
    return {
        "total": total, "correct": correct, "wrong": wrong, "abstained": abstained,
        "unsafe_acceptances": unsafe,
        "coverage": round(accepted / total, 6) if total else 0,
        "precision_of_accepted": round(correct / accepted, 6) if accepted else None,
        "groups": by_group,
    }


def calibrate(rows, outputs, registry, fixtures, *, max_wrong=0):
    if not rows or any(r["split"] != "dev" for r in rows):
        raise ValueError("calibration_requires_dev_only")
    if type(max_wrong) is not int or max_wrong < 0:
        raise ValueError("invalid_wrong_budget")
    candidates = []
    for threshold in THRESHOLDS:
        metrics = assess(rows, outputs, registry, fixtures, threshold)
        if metrics["wrong"] <= max_wrong and metrics["unsafe_acceptances"] == 0:
            candidates.append((metrics["coverage"], -threshold, threshold))
    if not candidates:
        # A nominal 1.0 threshold is NOT fail-closed: a model may report
        # confidence=1.0 on a wrong answer. Refuse to activate the model.
        raise ValueError("no_safe_goal_threshold")
    return max(candidates)[2]


def evaluate_suite(suite, outputs, registry, fixtures, *, max_wrong=0):
    dev = [row for row in suite if row["split"] == "dev"]
    test = [row for row in suite if row["split"] == "test"]
    threshold = calibrate(dev, outputs, registry, fixtures, max_wrong=max_wrong)
    return {
        "protocol": "goal-proposal-eval/v1",
        "threshold_selected_from": "dev_only",
        "threshold": threshold,
        "dev": assess(dev, outputs, registry, fixtures, threshold),
        "test": assess(test, outputs, registry, fixtures, threshold),
        "claim": "Goal nomination only; no end-to-end fault-resolution or router hardware claim",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Evaluate real local Ollama goal proposals")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--max-dev-wrong", type=int, default=0)
    args = parser.parse_args(argv)
    registry = GraphRegistry.from_v01()
    fixtures = {c["id"]: c for c in read_json(ROOT / "data/cases.json")}
    suite = read_suite(args.input, registry, fixtures)
    model = OllamaGoalModel(args.model, endpoint=args.endpoint, timeout=args.timeout)
    outputs = {}
    for row in suite:
        # Model sees only allowed public Registry names and descriptions;
        # it never receives labels, case ID, world, fixtures or gold.
        state = CaseState(fixtures[row["case_id"]], registry)
        eligible = sorted({
            name for f in registry.functions.values()
            if registry.contract_allowed(f) and state.allowed(f)
            for name in f.outputs if not registry.ports[name].untrusted_text
        })
        catalog = [
            {"port": p, "description": " ".join(
                f.description[:200] for f in registry.functions.values()
                if p in f.outputs and registry.contract_allowed(f) and state.allowed(f)
            )[:320]}
            for p in eligible
        ]
        try:
            outputs[row["id"]] = model.propose_goals(row["request"], tuple(catalog))
        except (OSError, RuntimeError, ValueError, TimeoutError):
            outputs[row["id"]] = None  # unavailable -> explicit abstention
    result = evaluate_suite(suite, outputs, registry, fixtures,
                            max_wrong=args.max_dev_wrong)
    result.update(
        model=args.model,
        model_parameters=model.parameter_count,
        data_sha256=hashlib.sha256(args.input.read_bytes()).hexdigest(),
        environment="local_ollama_not_gateway_hardware",
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
