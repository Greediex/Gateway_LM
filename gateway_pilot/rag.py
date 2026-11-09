"""WF-069 local runbooks. Documentation context and live evidence stay separate."""

import argparse
import hashlib
import json
import math
import sys
import unicodedata
from collections import Counter
from graphlib import TopologicalSorter
from pathlib import Path

from .core import ROOT, terms
from .graph_v3.upstream import rank


DEFAULT_CATALOG = ROOT / "data" / "runbooks_replay_v1.json"
REPLAY_PRODUCT = "gateway-lm-pilot"
REPLAY_FIRMWARE = "synthetic-replay-v1"
STOP = {"the", "for", "and", "with", "mot", "cua", "va", "de", "khi", "voi", "cho", "giup", "toi"}
TECH_TERMS = {"dns", "dhcp", "wan", "uplink", "qos", "conntrack", "ota", "servfail", "refused",
              "rssi", "firmware", "sha256"}


def tokens(text):
    folded = unicodedata.normalize("NFKD", text.casefold().replace("đ", "d"))
    return [word for word in terms("".join(ch for ch in folded if not unicodedata.combining(ch)))
            if word not in STOP]


def json_bytes(rows):
    return len(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def lexical_scores(query, documents):
    words = set(tokens(query))
    index = {name: Counter(tokens(text)) for name, text in documents.items()}
    average = sum(map(Counter.total, index.values())) / max(1, len(index))
    if not average:
        return {}
    df = {word: sum(word in counts for counts in index.values()) for word in words}
    scores = {}
    for name, counts in index.items():
        matched = words & counts.keys()
        # One normalized Vietnamese word can collide with an unrelated meaning after accent folding.
        if len(matched) < 2 and not matched.intersection(TECH_TERMS):
            continue
        norm = 1.2 * (.25 + .75 * counts.total() / average)
        score = sum(math.log1p((len(index) - df[word] + .5) / (df[word] + .5))
                    * counts[word] * 2.2 / (counts[word] + norm)
                    for word in sorted(matched))
        if score:
            scores[name] = score
    return scores


class RunbookIndex:
    def __init__(self, path=DEFAULT_CATALOG):
        path = Path(path).resolve()
        contents = path.read_bytes()
        rows = json.loads(contents)
        if not isinstance(rows, list):
            raise ValueError("Runbook catalog must be a list")
        self.source = {"path": str(path), "sha256": hashlib.sha256(contents).hexdigest()}
        self.docs = {}
        fields = ("id", "product", "firmware", "title", "keywords", "text")
        for row in rows:
            if (not isinstance(row, dict) or any(not isinstance(row.get(k), str) or not row[k].strip() for k in fields)
                    or not isinstance(row.get("requires"), list)
                    or any(not isinstance(dep, str) for dep in row["requires"])
                    or len(set(row["requires"])) != len(row["requires"])):
                raise ValueError("Invalid runbook record")
            if row["id"] in self.docs:
                raise ValueError("Duplicate runbook ID: " + row["id"])
            self.docs[row["id"]] = row
        for row in self.docs.values():
            for dep in row["requires"]:
                if (dep == row["id"] or dep not in self.docs or
                        any(row[key] != self.docs[dep][key] for key in ("product", "firmware"))):
                    raise ValueError("Invalid cross-profile runbook dependency: " + dep)
        TopologicalSorter({key: row["requires"] for key, row in self.docs.items()}).prepare()

    def retrieve(self, request, *, product, firmware, permissions, method="closure", k=3, max_bytes=1600):
        if (method not in {"gos", "bm25", "closure"} or type(k) is not int or not 1 <= k <= 12
                or type(max_bytes) is not int or not 2 <= max_bytes <= 32_000):
            raise ValueError("Invalid retrieval method or context budget")
        result = {"workflow_id": "WF-069", "product": product, "firmware": firmware, "method": method,
                  "documents": [], "context_bytes": 2, "reason": None}
        if "docs.read" not in permissions:
            return {**result, "status": "BLOCKED", "reason": "docs_read_denied"}
        docs = {key: row for key, row in self.docs.items()
                if row["product"] == product and row["firmware"] == firmware}
        if not docs:
            return {**result, "status": "INCOMPLETE", "reason": "no_exact_firmware_profile"}
        scored = lexical_scores(request, {key: row["title"] + " " + row["keywords"] + " " + row["text"]
                                          for key, row in docs.items()})
        if not scored:
            return {**result, "status": "INCOMPLETE", "reason": "no_matching_runbook"}
        ordered = sorted(scored, key=lambda name: (-scored[name], name))
        if method != "bm25":
            primary = ordered[0]
            ordered = [primary]
            neighborhood = {primary}
            for key in ordered:
                for dep in docs[key]["requires"]:
                    if dep not in neighborhood:
                        neighborhood.add(dep)
                        ordered.append(dep)
            if method == "gos" and len(neighborhood) > 1:
                # Anchor the topic first. Expand only declared prerequisites, with GoS producer -> consumer edges.
                edges = [(dep, key, "dependency", 1.0) for key in neighborhood for dep in docs[key]["requires"]]
                scores = rank(sorted(neighborhood), edges, {primary: 1})
                ordered = [primary, *sorted(neighborhood - {primary}, key=lambda name: (-scores[name], name))]
        for key in ordered:
            if len(result["documents"]) == k:
                break
            row = docs[key]
            card = {"id": key, "title": row["title"], "text": row["text"]}
            pending = [*result["documents"], card]
            size = json_bytes(pending)
            if size <= max_bytes:
                result.update(documents=pending, context_bytes=size)
            elif not result["documents"]:
                break
        if not result["documents"]:
            return {**result, "status": "INCOMPLETE", "reason": "context_budget"}
        return {**result, "status": "FOUND", "source": self.source}


def explain(guide, diagnosis=None):
    """Assemble a response from two separately cited sources."""
    terminal = diagnosis["terminal"] if diagnosis else None
    measurement = None if terminal is None else {
        "response": terminal["response"], "evidence_ids": terminal["evidence_ids"],
        "status": diagnosis["case_status"],
    }
    lines = []
    if measurement:
        ids = ", ".join(measurement["evidence_ids"])
        suffix = f" [{ids}]" if ids else ""
        lines.append(measurement["response"] + suffix)
    if guide["documents"]:
        lines.append("Tài liệu tham khảo")
        lines.extend(f"- {doc['text']} [{doc['id']}]" for doc in guide["documents"])
    else:
        lines.append("Chưa có tài liệu phù hợp trong phạm vi tra cứu.")
    return {"measurement": measurement, "guide": guide, "response": "\n".join(lines)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", required=True)
    parser.add_argument("--product", required=True)
    parser.add_argument("--firmware", required=True)
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--method", choices=("gos", "closure", "bm25"), default="closure")
    args = parser.parse_args()
    guide = RunbookIndex(args.catalog).retrieve(args.request, product=args.product, firmware=args.firmware,
                                              permissions={"docs.read"}, method=args.method)
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(explain(guide), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
