"""Optional local semantic embedding boundary for Gateway LM retrieval.

This augments lexical+GoS ranking; it does NOT authorize Function calls.
Only trusted startup code may attach a local embedder. No dependency on
sentence-transformers, remote APIs or a particular NPU is required by Core.
"""
from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from collections.abc import Sequence

from ..core import PlanError


class LocalSemanticIndex:
    """Cache normalized Function/Skill/Workflow catalog vectors in memory.

    Encoder contract:
      model_id: stable nonempty identifier
      local_only: literal True (remote embedding is forbidden by this pilot)
      encode_many(texts: list[str]) -> list[list[float]]

    The encoder is trusted server configuration, never an HTTP parameter.
    """

    def __init__(self, encoder, *, min_similarity=0.62, max_dimension=4096):
        model_id = getattr(encoder, "model_id", None)
        if (not isinstance(model_id, str)
                or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,128}", model_id)
                or getattr(encoder, "local_only", None) is not True
                or not callable(getattr(encoder, "encode_many", None))):
            raise ValueError("semantic_encoder_must_be_trusted_local")
        if (not isinstance(min_similarity, (float, int)) or isinstance(min_similarity, bool)
                or not math.isfinite(min_similarity) or not 0 < min_similarity <= 1):
            raise ValueError("invalid_semantic_threshold")
        if type(max_dimension) is not int or not 1 <= max_dimension <= 8192:
            raise ValueError("invalid_semantic_dimension")
        self.encoder = encoder
        self.model_id = model_id
        self.min_similarity = float(min_similarity)
        self.max_dimension = max_dimension
        self._cache_key = None
        self._normalized = ()

    def _encode(self, texts):
        try:
            vectors = self.encoder.encode_many(list(texts))
        except Exception as exc:
            raise PlanError("semantic_encoder_failed") from exc
        if not isinstance(vectors, Sequence) or len(vectors) != len(texts):
            raise PlanError("semantic_vector_count_mismatch")
        normalized = []
        dimension = None
        for vector in vectors:
            if isinstance(vector, (str, bytes)):
                raise PlanError("semantic_vector_invalid_type")
            try:
                values = tuple(float(n) for n in vector)
            except (ValueError, TypeError, OverflowError) as exc:
                raise PlanError("semantic_vector_invalid_type") from exc
            if not values or len(values) > self.max_dimension:
                raise PlanError("semantic_vector_invalid_dimension")
            if dimension is None:
                dimension = len(values)
            elif dimension != len(values):
                raise PlanError("semantic_vector_dimension_mismatch")
            if not all(math.isfinite(x) for x in values):
                raise PlanError("semantic_vector_nonfinite")
            length = math.sqrt(math.fsum(x * x for x in values))
            if not math.isfinite(length) or length <= 0:
                raise PlanError("semantic_vector_zero_or_overflow")
            normalized.append(tuple(x / length for x in values))
        return tuple(normalized)

    @staticmethod
    def document(field):
        # ONLY trusted registry metadata, never observations, user-provided
        # logs or model-composed instructions.
        return " ".join([
            field["name"], field["description"],
            *field["tags"], *field["ports"],
        ])

    def score(self, graph_key, names, fields, query):
        """Cosine similarities for all catalog nodes, with a safety threshold.

        A changed Registry or SkillGraph revision forces document re-encoding.
        Query vectors are intentionally not cached: case state may contain
        private verified facts, and query caching is unnecessary for correctness.
        """
        if not isinstance(query, str) or not 0 < len(query) <= 16000:
            raise PlanError("semantic_query_invalid")
        key = (graph_key, self.model_id, id(self.encoder))
        if self._cache_key != key:
            docs = [self.document(fields[name]) for name in names]
            vectors = self._encode(docs)
            # Cache only after complete successful encoding (no partial index).
            self._normalized, self._cache_key = vectors, key
        query_vector = self._encode([query])[0]
        if len(query_vector) != len(self._normalized[0]):
            raise PlanError("semantic_query_dimension_mismatch")
        scores = {}
        for name, vector in zip(names, self._normalized):
            raw = math.fsum(x * y for x, y in zip(query_vector, vector))
            if raw >= self.min_similarity:
                scores[name] = min(1.0, raw)
        return scores


class LocalSentenceTransformerEncoder:
    """Opt-in local-only model directory; dependency is NOT installed by Core.

    Usage requires `sentence-transformers` separately on a trusted host.
    Hardware QNN/HTP deployment is not implied by this host implementation.
    """

    local_only = True

    def __init__(self, model_directory: str | Path):
        directory = Path(model_directory).expanduser()
        if not directory.is_dir():
            raise ValueError("semantic_model_must_be_local_directory")
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(str(directory.resolve()), trust_remote_code=False)
        # The model ID is an opaque local path fingerprint, not a network URL.
        self.model_id = "local/" + hashlib.sha256(
            str(directory.resolve()).encode("utf-8")
        ).hexdigest()[:20]

    def encode_many(self, texts):
        result = self._model.encode(
            list(texts),
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return result.tolist()
