"""Bounded advisory context for laptop chat; never execution or evidence.

Only trusted startup code constructs this object. Request/model data can select
neither an encoder nor a documentation product/firmware profile.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from dataclasses import replace
from pathlib import Path
from itertools import islice
from typing import Iterable

from ..core import PlanError
from ..graph_v3.semantic import LocalOllamaEncoder, LocalSemanticIndex
from ..rag import RunbookIndex
from ..skill_expansion.catalog import SkillCatalog
from ..skill_expansion.retrieval import SearchHit

LAPTOP_PRODUCT = "linux-laptop"
LAPTOP_DOC_PROFILE = "linux-read-docs-v1"
RUNBOOKS = Path(__file__).resolve().parents[2] / "data" / "runbooks_laptop_v1.json"


class ChatContext:
    """Ranking suggestions and static documentation, with no tool authority."""

    def __init__(self, *, encoder=None, runbook_index: RunbookIndex | None = None,
                 product: str = LAPTOP_PRODUCT, firmware: str = LAPTOP_DOC_PROFILE,
                 semantic_reason: str = "not_configured", min_similarity: float = .30):
        if any(not isinstance(x, str) or not 0 < len(x) <= 128 for x in (product, firmware)):
            raise ValueError("invalid_runbook_profile")
        self._lock = threading.RLock()
        # Fixed advisory relevance threshold; not calibrated on a holdout.
        self.semantic = LocalSemanticIndex(encoder, min_similarity=min_similarity) if encoder is not None else None
        self.semantic_reason = semantic_reason
        self.index = runbook_index if runbook_index is not None else RunbookIndex(RUNBOOKS)
        self.product, self.firmware = product, firmware

    @classmethod
    def trusted_default(cls) -> "ChatContext":
        """Read process environment only at startup; never pull a model."""
        encoder = None
        reason = "local_embedding_model_unavailable"
        try:
            encoder = LocalOllamaEncoder(os.environ.get("GATEWAY_EMBED_MODEL", "embeddinggemma"))
        except (OSError, ValueError, TypeError, KeyError):
            pass
        return cls(encoder=encoder, semantic_reason=reason,
                   product=os.environ.get("GATEWAY_RUNBOOK_PRODUCT", LAPTOP_PRODUCT),
                   firmware=os.environ.get("GATEWAY_RUNBOOK_FIRMWARE", LAPTOP_DOC_PROFILE))

    @staticmethod
    def _request(request: str) -> None:
        if not isinstance(request, str) or not 0 < len(request) <= 4000:
            raise ValueError("chat_context_request_budget")

    def search(self, request: str, catalog: SkillCatalog,
               lexical_hits: Iterable[SearchHit]) -> dict:
        with self._lock:
            return self._search(request, catalog, lexical_hits)

    def _search(self, request: str, catalog: SkillCatalog,
                lexical_hits: Iterable[SearchHit]) -> dict:
        self._request(request)
        if not 1 <= len(catalog.skills) <= 128:
            raise ValueError("chat_context_catalog_budget")
        hits = list(islice(lexical_hits, 129))
        if len(hits) > 128 or any(not isinstance(h, SearchHit) or h.skill_id not in catalog.skills for h in hits):
            raise ValueError("chat_context_invalid_hits")
        base = {hit.skill_id: hit for hit in hits}
        metadata = {"status": "UNAVAILABLE", "reason": self.semantic_reason,
                    "model_id": None, "source": "trusted_catalog_metadata", "grants_execution": False}
        candidates = []
        if self.semantic is not None:
            metadata["model_id"] = self.semantic.model_id
            fields = {s.id: {"name": s.name_vi, "description": s.notes[:2000],
                              "tags": [s.domain, s.domain_name, s.kind, s.scope], "ports": []}
                      for s in catalog.skills.values()}
            fingerprint = hashlib.sha256(json.dumps(fields, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            try:
                scores = self.semantic.score(fingerprint, sorted(fields), fields, request)
                candidates = [{"skill_id": key, "similarity": round(score, 6)}
                              for key, score in sorted(scores.items(), key=lambda item: (-item[1], item[0]))[:6]]
                metadata.update(status="READY", reason=None, catalog_sha256=fingerprint)
                # Existing lexical/graph scores remain relevance only. Semantic
                # candidates may include NOT_BOUND design skills, never new rights.
                selected = {item["skill_id"]: item["similarity"] for item in candidates}
                for sid in base.keys() | selected.keys():
                    skill = catalog.skills[sid]
                    original = base.get(sid, SearchHit(sid, skill.name_vi, 0, 0, 0,
                                                      skill.catalog_status, skill.priority, skill.runtime_status))
                    base[sid] = replace(original, score=round(.7 * original.score + .3 * selected.get(sid, 0), 6))
            except PlanError as exc:
                metadata.update(status="ERROR", reason=str(exc))
        ranked = sorted(base.values(), key=lambda h: (-h.score, h.skill_id))[:6]
        return {"hits": ranked, "semantic": metadata, "semantic_candidates": candidates}

    def runbooks(self, request: str) -> dict:
        self._request(request)
        result = self.index.retrieve(request, product=self.product, firmware=self.firmware,
                                     permissions={"docs.read"}, method="closure", k=3, max_bytes=1600)
        return {**result, "provenance": self.index.source,
                "profile_kind": "documentation_compatibility_profile",
                "live_firmware_verified": False, "is_observation": False,
                "untrusted_data": True, "grants_execution": False}


_default_context = None
_default_context_lock = threading.Lock()

def trusted_context() -> ChatContext:
    global _default_context
    with _default_context_lock:
        if _default_context is None:_default_context=ChatContext.trusted_default()
        return _default_context
