"""Fetch the upstream source revisions required by the graph adapters."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parent
REPOS = (
    ("graph-of-skills", "https://github.com/davidliuk/graph-of-skills.git", "203f60a2c689da055ce1ac351eb3cb9912a3bca7"),
    ("SkillDAG", "https://github.com/Ericbai06/SkillDAG.git", "2bd7baffae58854018f75857e5626a4a28a705ae"),
)

for name, url, commit in REPOS:
    dest = ROOT / "third_party" / name
    if dest.exists():
        raise SystemExit(f"{dest} already exists; inspect it before retrying")
    subprocess.run(["git", "clone", "--no-checkout", url, str(dest)], check=True)
    subprocess.run(["git", "-C", str(dest), "checkout", "--detach", commit], check=True)

from gateway_pilot.graph_v3.upstream import kernel
from gateway_pilot.graph_v3.skilldag import backend
kernel()
backend()
print("Pinned upstream source hashes verified.")
