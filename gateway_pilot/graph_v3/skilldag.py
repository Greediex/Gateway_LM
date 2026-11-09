"""Read-only adapter for the pinned SkillDAG set expansion and conflict checks."""

import hashlib
import importlib.util
import sys
from functools import lru_cache
from types import ModuleType

from ..core import ROOT


COMMIT = "2bd7baffae58854018f75857e5626a4a28a705ae"
FILES = {
    "search": "248b5b7a6e201bbc10ccdecb10655da1ccb49087228e27895f68ba813998153b",
    "graph": "da73c98ef43246ac21da9acc7ede5a2b3c4d9817b16b07d73e52e9c41df7392e",
}
SOURCE = ROOT / "third_party" / "SkillDAG" / "src" / "skilldag"


@lru_cache(maxsize=1)
def backend():
    for name, digest in FILES.items():
        path = SOURCE / (name + ".py")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError("Pinned SkillDAG source missing or modified: " + path.name)
    package = ModuleType("_gateway_pinned_skilldag")
    package.__path__ = []
    sys.modules[package.__name__] = package
    for name in FILES:
        qualified = package.__name__ + "." + name
        spec = importlib.util.spec_from_file_location(qualified, SOURCE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
    return module.SkillGraph


def check_skills(graph, selected):
    data = {
        "nodes": graph.skills,
        "edges": [{"source": edge.source, "target": edge.target, "type": edge.kind}
                  for edge in graph.edges],
    }
    # In-memory constructor only. SkillDAG.load() may initialize or persist a graph.
    reader = backend()(graph_path=SOURCE, skills_dir=SOURCE, data=data)
    expanded = reader.expand_set(list(selected))
    checked = reader.check_set(expanded["expanded"])
    return {"expanded": expanded["expanded"], "prerequisites": expanded["added"],
            "conflicts": checked["conflicts"]}
