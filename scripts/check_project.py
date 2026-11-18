"""Small, deterministic checks for tracked project hygiene and active docs.

This script does not delete or modify any files. Historical reports and
replay outputs are deliberately excluded from active-document link checking.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_DOCS = (
    "README.md",
    "docs/WEB_UI.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/INDEX.md",
    "docs/DEVELOPER_GUIDE.md",
)
REQUIRED = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "docs/INDEX.md",
    "docs/DEVELOPER_GUIDE.md",
    "data/frozen_manifest.json",
    "gateway_pilot/graph_v3/contracts.py",
    "gateway_pilot/adapters/composite.py",
    "tests/graph_v3/test_composite_adapter.py",
    "tests/web/test_adapter.py",
)
GENERATED_TOP = {"runs", "third_party", "models", "captures", "logs"}
GENERATED_DIRS = {
    "__pycache__", ".venv", ".venv-graph", "venv", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", ".tox", ".nox",
}
# Owner-locked AI criteria in CLAUDE.md. Changing the block or this hash
# requires an explicit human-owner commit; agents must not update it.
LOCKED_CRITERIA_SHA256 = "4dfebbc69df8f386ad840464476e215dfbc2ba4707c4e050afd951feb7759d9f"
LOCKED_RE = re.compile(
    r"<!-- LOCKED-CRITERIA:BEGIN -->\n(.*?)<!-- LOCKED-CRITERIA:END -->", re.S)
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")


def suspicious_tracked(paths: list[str]) -> list[str]:
    """Return tracked outputs/caches that must stay local, not versioned."""
    bad = []
    for raw in paths:
        item = Path(raw)
        parts = item.parts
        if not parts:
            continue
        if (parts[0] in GENERATED_TOP or any(p in GENERATED_DIRS for p in parts)
                or item.suffix in {".pyc", ".pyo", ".pem", ".key", ".p12"}
                or item.name in {".env", ".netrc"}):
            bad.append(raw)
    return bad


def broken_links(root: Path, doc_paths: tuple[str, ...] = ACTIVE_DOCS) -> list[str]:
    """Verify only local Markdown links in maintained entry-point documents."""
    errors = []
    for name in doc_paths:
        source = root / name
        if not source.is_file():
            errors.append(f"Missing active document: {name}")
            continue
        for match in LINK_RE.finditer(source.read_text(encoding="utf-8")):
            raw = match.group(1).strip().strip("<>")
            if (not raw or raw.startswith(("#", "/", "//"))
                    or re.match(r"^[a-z][a-z0-9+.-]*:", raw, flags=re.IGNORECASE)):
                continue
            # Fragment links are not checked here; a separate docs build may
            # validate Markdown anchors. Ignore the optional link title.
            destination = unquote(raw.split()[0]).split("#", 1)[0].split("?", 1)[0]
            if destination and not (source.parent / destination).exists():
                errors.append(f"{name}: broken local link {raw}")
    return errors


def locked_criteria_errors(root: Path) -> list[str]:
    """Fail closed if the owner-locked CLAUDE.md criteria block was altered."""
    source = root / "CLAUDE.md"
    if not source.is_file():
        return ["Missing CLAUDE.md with locked AI criteria"]
    blocks = LOCKED_RE.findall(source.read_text(encoding="utf-8"))
    if len(blocks) != 1:
        return ["CLAUDE.md must contain exactly one LOCKED-CRITERIA block"]
    digest = hashlib.sha256(blocks[0].encode("utf-8")).hexdigest()
    if digest != LOCKED_CRITERIA_SHA256:
        return ["CLAUDE.md locked criteria changed (sha256 mismatch); owner approval required"]
    return []


def check_project(root: Path = ROOT) -> list[str]:
    errors = [f"Missing required project path: {name}" for name in REQUIRED
              if not (root / name).exists()]
    errors.extend(broken_links(root))
    errors.extend(locked_criteria_errors(root))
    try:
        tracked = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"], check=True, capture_output=True,
        ).stdout.decode("utf-8", errors="replace").split("\0")
    except (OSError, subprocess.CalledProcessError) as exc:
        errors.append(f"git ls-files unavailable: {exc}")
    else:
        errors.extend(f"Generated/private file tracked: {path}"
                      for path in suspicious_tracked(tracked))
    return errors


def main() -> int:
    errors = check_project()
    if errors:
        for error in errors:
            print("ERROR:", error)
        return 1
    print("Repository hygiene: PASS (active links, required paths, tracked artifacts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
