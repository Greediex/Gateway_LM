"""Metadata discovery and constructive dependency witnesses, never execution."""
from __future__ import annotations

import heapq
from collections import defaultdict
from collections.abc import Iterable
from itertools import islice

from .loader import require


GROUP_KEYS = {"functions": "function_id", "ports": "port_id", "skills": "skill_id"}


def index_documents(catalog: dict) -> dict:
    result = {}
    for group, identity in GROUP_KEYS.items():
        indexed = {}
        for row in catalog[group]:
            key = (row[identity], row["version"])
            require(key not in indexed, "duplicate_" + group + ":" + "@".join(key))
            indexed[key] = row
        result[group] = indexed
    return result


def dependency_witness(functions: dict) -> tuple[list, dict]:
    """AND input ports, OR producers, AND ORDER constraints; no recursive DFS.

    An input becomes available when a producer can be scheduled. Alternative
    producers do not create a false cycle merely because their union has one.
    This proves only a metadata schedule exists, not a successful measurement.
    """
    waiting = defaultdict(set)
    required = {}
    for key, row in functions.items():
        events = {("port", pid, version) for pid, version in row["inputs"].items()}
        events.update(("function", fid) for fid in row["order_after"])
        required[key] = events
        for event in events:
            waiting[event].add(key)
    pending = {key: len(events) for key, events in required.items()}
    ready = [key for key in functions if pending[key] == 0]
    heapq.heapify(ready)
    emitted, ordered, dependencies = {}, [], {}
    while ready:
        key = heapq.heappop(ready)
        ordered.append(key)
        dependencies[key] = {emitted[event] for event in required[key]}
        row = functions[key]
        events = [("function", row["function_id"])]
        events.extend(("port", pid, version) for pid, version in row["outputs"].items())
        for event in events:
            if event in emitted:
                continue
            emitted[event] = key
            for consumer in sorted(waiting[event]):
                pending[consumer] -= 1
                if pending[consumer] == 0:
                    heapq.heappush(ready, consumer)
    require(len(ordered) == len(functions), "dependency_cycle_or_unreachable")
    return ordered, dependencies


def build_indexes(functions: list[dict]) -> dict:
    indexed = {(f["function_id"], f["version"]): f for f in functions}
    order, dependencies = dependency_witness(indexed)
    domains, skills, producers, consumers = (defaultdict(list) for _ in range(4))
    for row in sorted(functions, key=lambda f: f["function_id"]):
        fid = row["function_id"]
        domains[row["domain"]].append(fid)
        for skill in row["skill_refs"]:
            skills[skill["skill_id"]].append(fid)
        for pid in row["outputs"]:
            producers[pid].append(fid)
        for pid in row["inputs"]:
            consumers[pid].append(fid)
    return {
        "by_domain": dict(domains), "by_skill": dict(skills),
        "producers": dict(producers), "consumers": dict(consumers),
        "dependencies": {key[0]: sorted(dep[0] for dep in dependencies[key]) for key in sorted(indexed)},
        "witness_order": [key[0] for key in order],
    }


def discover(indexes: dict, *, domain: str | None = None,
             skill: str | None = None, limit: int = 10) -> list[str]:
    """Bounded metadata candidates. Core must still apply ACL/capability gates."""
    require(type(limit) is int and 1 <= limit <= 1000, "discovery_limit")
    candidates = set(indexes["by_domain"].get(domain, ())) if domain is not None else set(indexes["dependencies"])
    if skill is not None:
        candidates.intersection_update(indexes["by_skill"].get(skill, ()))
    return sorted(candidates)[:limit]


def dependency_closure(indexes: dict, function_ids: Iterable[str]) -> list[str]:
    """Keep witness dependencies across domains; do not compile a runtime DAG."""
    pending = list(islice(function_ids, 10001))
    require(len(pending) <= 10000, "closure_goal_limit")
    chosen = set()
    while pending:
        fid = pending.pop()
        require(fid in indexes["dependencies"], "unknown_discovery_function")
        if fid not in chosen:
            chosen.add(fid)
            pending.extend(indexes["dependencies"][fid])
    return [fid for fid in indexes["witness_order"] if fid in chosen]
