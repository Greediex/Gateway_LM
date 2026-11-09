"""Load the actual pinned MIT GoS kernel, never a silent local substitute."""
import hashlib
import importlib.util
import math
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

PILOT = Path(__file__).resolve().parents[2]
COMMIT = "203f60a2c689da055ce1ac351eb3cb9912a3bca7"
KERNEL_SHA256 = "3c03db37774949b67d03e5da2852bbc694ae9a8d38593bdd7d17d6f7a03d072c"
SOURCE = PILOT / "third_party/graph-of-skills/gos/core/retrieval.py"
_kernel = None


def kernel():
    global _kernel
    if _kernel is None:
        if not SOURCE.is_file() or hashlib.sha256(SOURCE.read_bytes()).hexdigest() != KERNEL_SHA256:
            raise RuntimeError("Pinned GoS kernel missing/modified; restore recorded commit, no fallback")
        spec = importlib.util.spec_from_file_location("gateway_pinned_gos_retrieval", SOURCE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _kernel = module
    return _kernel


def _transition(names, edges, reverse):
    module = kernel()
    nodes = [SimpleNamespace(name=name) for name in names]
    items = [SimpleNamespace(source=a, target=b, type=kind, weight=weight)
             for a, b, kind, weight in edges]
    weights = None if reverse else {key: 0.0 for key in module.DEFAULT_REVERSE_WEIGHTS}
    return module.build_transition_matrix(nodes, items, reverse_weights=weights)


_cached_transition = lru_cache(maxsize=16)(_transition)


def rank(names, edges, seeds, *, restart=.2, reverse=True):
    """GoS convention: dependency producer -> consumer; restart is not alpha."""
    if not 0 < restart <= 1:
        raise ValueError("restart must be in (0,1]")
    module = kernel()
    if len(set(names)) != len(names):
        raise ValueError("duplicate graph node")
    if any(a not in names or b not in names or not math.isfinite(w) for a,b,_,w in edges):
        raise ValueError("invalid graph endpoint/weight")
    if any(name not in names or not math.isfinite(weight) or weight < 0 for name,weight in seeds.items()):
        raise ValueError("invalid personalization seed")
    # Avoid upstream's zero-weight `or 1.0` behavior; no conflict diffusion.
    safe_edges = tuple(sorted((a, b, t, w) for a, b, t, w in edges if t != "conflict" and w > 0))
    # Limit memory retained by the dense upstream matrix. State still affects every seed vector.
    build = _cached_transition if len(names) <= 128 else _transition
    transition, index = build(tuple(names), safe_edges, reverse)
    seed_items = [(name, weight) for name, weight in seeds.items() if name in index and weight > 0]
    p = module.build_personalization(len(names), [index[n] for n, _ in seed_items], [w for _, w in seed_items])
    scores = module.personalized_pagerank(transition, p, damping=restart, max_iter=500, tol=1e-12)
    return {name: float(scores[index[name]]) for name in names}
