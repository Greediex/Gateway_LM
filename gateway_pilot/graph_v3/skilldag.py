"""UPSTREAM_CALLED: pinned SkillDAG in memory; only vector scoring uses pilot BM25."""

import copy
import hashlib
import importlib.util
import math
import sys
from collections import Counter
from functools import lru_cache
from types import ModuleType

from ..core import ROOT, PlanError, terms


COMMIT = "2bd7baffae58854018f75857e5626a4a28a705ae"
FILES = {
    "search": "5bed3919f5a9676e40ea7ba1d3bf8c06324f867161e0c0e2fb44da9f455795ff",
    "graph": "97a181273002647a97d58628af588b5843e73d9873e6e5b7768eb7315051456b",
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
        # Loading pinned code must not create __pycache__ under third_party/.
        exec(compile((SOURCE / (name + ".py")).read_bytes(), str(SOURCE / (name + ".py")), "exec"), module.__dict__)
    return module.SkillGraph


def call(reader, method, *args, **kwargs):
    """Keep the upstream error code available to all pilot callers."""
    error_type = sys.modules[backend().__module__].GraphCLIError
    try:
        return getattr(reader, method)(*args, **kwargs)
    except error_type as exc:
        raise PlanError(f"{exc.code}: {exc.message}") from exc


@lru_cache(maxsize=1)
def memory_backend():
    class InMemorySkillGraph(backend()):
        def save(self):
            pass

        def _vector_score(self, query):
            # Same k1=1.2, b=.75 BM25 formula as GraphRegistry.retrieve.
            q = sorted(set(terms(query)))
            if not q:
                return []
            docs = {sid: Counter(terms(node.get("name", sid) + " " + node.get("description", "")))
                    for sid, node in self.data["nodes"].items()}
            df = {t: sum(t in d for d in docs.values()) for t in q}
            avg = sum(sum(d.values()) for d in docs.values()) / max(1, len(docs))
            scored = [(sid, sum(math.log(1 + (len(docs) - df[t] + .5) / (df[t] + .5)) * d[t] * 2.2 /
                                (d[t] + 1.2 * (.25 + .75 * sum(d.values()) / max(1, avg))) for t in q))
                      for sid, d in docs.items()]
            return sorted(scored, key=lambda item: (-item[1], item[0]))

    return InMemorySkillGraph


def in_memory_graph(skills, relations):
    kinds = sys.modules[backend().__module__].EDGE_TYPES
    data = {
        "schema_version": "skillgraph.v1",
        "history": [],
        "nodes": copy.deepcopy(skills),
        "edges": [{"source": edge.source, "target": edge.target, "type": edge.kind}
                  | {"weight": edge.weight, "origin": getattr(edge, "origin", "registry"),
                     "reason": getattr(edge, "reason", "")}
                  for edge in relations if edge.kind in kinds],
    }
    reader = memory_backend()(graph_path=SOURCE, skills_dir=SOURCE, data=data)
    call(reader, "validate")
    # Upstream validate checks schema/normalization; its edit guards enforce
    # backbone/polarity. Apply those same guards to an imported registry too.
    for edge in reader.data["edges"]:
        call(reader, "_assert_acyclic", edge["source"], edge["target"], edge["type"])
        call(reader, "_assert_no_contradiction", edge["source"], edge["target"], edge["type"])
    return reader


def check_skills(graph, selected):
    expanded = graph.expand_set(list(selected))
    checked = graph.check_set(expanded["expanded"])
    return {"expanded": expanded["expanded"], "prerequisites": expanded["added"],
            "conflicts": checked["conflicts"], "redundant": checked["redundant"],
            "repair": graph.repair_set(expanded["expanded"])}
