"""Clone and verify exact upstream source revisions used by graph adapters.

Existing pinned checkouts are verified in place and never silently removed,
reset or modified. The pinned code hash checks remain fail-closed.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPOS = (
    ("graph-of-skills", "https://github.com/davidliuk/graph-of-skills.git",
     "203f60a2c689da055ce1ac351eb3cb9912a3bca7"),
    ("SkillDAG", "https://github.com/Ericbai06/SkillDAG.git",
     "2bd7baffae58854018f75857e5626a4a28a705ae"),
)


def _head(checkout: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def ensure_checkout(root: Path, name: str, url: str, pinned_commit: str) -> Path:
    """Fetch once; on subsequent runs only verify the existing source revision.

    A bad or partial checkout is reported, not deleted or auto-reset, to avoid
    surprising loss of a developer's local work.
    """
    checkout = root / "third_party" / name
    if checkout.exists():
        if not checkout.is_dir() or not (checkout / ".git").exists():
            raise RuntimeError(f"Upstream path exists but is not a Git checkout: {checkout}")
    else:
        checkout.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "--no-checkout", "--", url, str(checkout)], check=True)
        subprocess.run(["git", "-C", str(checkout), "checkout", "--detach", pinned_commit], check=True)

    actual = _head(checkout)
    if actual != pinned_commit:
        raise RuntimeError(
            f"Upstream checkout mismatch: {name} has {actual}, expected {pinned_commit}. "
            "Inspect the checkout manually; refusing automatic reset."
        )
    return checkout


def main() -> None:
    for name, url, pinned_commit in REPOS:
        ensure_checkout(ROOT, name, url, pinned_commit)

    # Both loaders verify SHA-256 of their selected source files. Keep them as
    # the single authority rather than accepting Git commit IDs alone.
    from gateway_pilot.graph_v3.upstream import kernel
    from gateway_pilot.graph_v3.skilldag import backend

    kernel()
    backend()
    print("Pinned upstream commits and source hashes verified.")


if __name__ == "__main__":
    main()
