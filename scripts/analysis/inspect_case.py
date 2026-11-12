"""Print decisions, graph plan and evidence for one recorded episode."""
import argparse
import json
import sys
from pathlib import Path


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run", type=Path)
    p.add_argument("--case", required=True)
    p.add_argument("--arm", default="graph")
    a = p.parse_args()
    for line in (a.run / "episodes.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["case_id"] == a.case and r["arm"] == a.arm:
            print(json.dumps(r, ensure_ascii=False, indent=2))
            return
    p.error("Episode not found")


if __name__ == "__main__":
    main()
