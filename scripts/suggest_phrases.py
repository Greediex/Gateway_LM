"""WP-S3: suggest routing phrases for catalog Skills; a person reviews and adds them.

Usage: python -m scripts.suggest_phrases B04 [B05 ...]

Candidates are 1-3 word n-grams of the Skill's Vietnamese name, normalized like
runtime questions. Each candidate lists the existing phrases it would collide
with (same word sequence on either side), because a shared phrase routes one
question to two Skills. Nothing is written and no phrase grants execution.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from gateway_pilot.skill_expansion.catalog import SkillCatalog
from gateway_pilot.workflow import normalize

ROOT = Path(__file__).resolve().parents[1]
CONFIGS = ("live", "replay")
STOP = frozenset("""cua va la co khong tren cho mot cac nhung nao thi ve voi tu den trong
theo bang khi neu hay duoc dang se da do nay kia ra vao len xuong""".split())
# Catalog names open with a generic action verb that no user would use as a topic.
GENERIC_LEAD = ("danh gia", "kiem tra", "chan doan", "theo doi", "phan tich", "xac dinh", "do luong")


def existing_phrases() -> dict[str, list[str]]:
    """phrase -> owners (`intent:<name>` or `skill:<id>`), from reviewed diagnostics."""
    owners: dict[str, list[str]] = {}
    for mode in CONFIGS:
        path = ROOT / f"config/skill_launcher/{mode}.diagnostics.json"
        if not path.is_file():
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        for name, meta in doc.get("question_intents", {}).items():
            for phrase in meta["phrases"]:
                owners.setdefault(phrase, []).append(f"intent:{name}")
        for sid, phrases in doc.get("required_skill_phrases", {}).items():
            for phrase in phrases:
                owners.setdefault(phrase, []).append(f"skill:{sid}")
    return owners


def _contains(text: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", text) is not None


def candidates(text: str, owners: dict[str, list[str]], own: str) -> list[dict]:
    text = normalize(text)
    for lead in GENERIC_LEAD:
        if text.startswith(lead + " "):
            text = text[len(lead) + 1:]
            break
    words = text.split()
    seen, rows = set(), []
    for size in (3, 2, 1):
        for i in range(len(words) - size + 1):
            gram = words[i:i + size]
            if gram[0] in STOP or gram[-1] in STOP or (size == 1 and len(gram[0]) < 4):
                continue
            phrase = " ".join(gram)
            if phrase in seen:
                continue
            seen.add(phrase)
            clashes = sorted({o for existing, who in owners.items()
                              if _contains(existing, phrase) or _contains(phrase, existing)
                              for o in who if o != own})
            rows.append({"phrase": phrase, "collides_with": clashes})
    return rows


def suggest(skill_ids: list[str]) -> list[dict]:
    skills = SkillCatalog.load().skills
    owners = existing_phrases()
    out = []
    for sid in skill_ids:
        if sid not in skills:
            raise KeyError(sid)
        out.append({"skill_id": sid, "name": skills[sid].name_vi,
                    "candidates": candidates(skills[sid].name_vi, owners, f"skill:{sid}")})
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("skills", nargs="+")
    args = parser.parse_args()
    try:
        print(json.dumps(suggest(args.skills), ensure_ascii=False, indent=2))
    except KeyError as exc:
        print(f"unknown Skill {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
