# Hybrid semantic–lexical–graph retrieval (experimental)

**Status: implemented with an injected local encoder and mock-vector tests.**
No real embedding model was benchmarked in CI. This is not evidence of better
retrieval recall, faster RCA or QNN/NPU readiness.

## Architecture

```text
Trusted Registry metadata ──> Local encoder ──> in-memory normalized vectors
                                    │
Request + verified, non-log facts ───┴──> query embedding
                                    │
BM25 (lexical) ────────────> seed fusion <──── thresholded cosine similarities
                                    │
                           eligibility/ACL gate before seeding
                                    │
                      pinned GoS personalized PageRank
                                    │
                         field + vector reranking
                                    │
                  allowed Function candidates only
                                    │
                  typed Compiler → Runner → Verifier
```

The original `bm25` and `gos` methods have not changed; `hybrid` is an
opt-in third method. Graph scores **never** grant Function permission. A
`CATALOG_ONLY` or WRITE workflow cannot seed an executable Function;
unprobed/unauthorized Functions remain excluded from results.

Semantic embeddings can be supplied by any trusted **local** encoder that
implements `model_id: str`, `local_only=True`, and
`encode_many(list[str]) -> list[list[float]]`. Core validates dimensions,
finite values, nonzero norms and cosine threshold. On malformed vectors or a
missing provider, `hybrid` fails explicitly; it **does not** silently switch
to lexical retrieval.

## Running with a local model (optional)

Install a compatible `sentence-transformers` version in a **separate,
trusted** host environment, and provide a fully downloaded local model
directory. The default project requirements do not download or install an
embedding model. The model path is supplied by trusted CLI/startup, never
user input to `/api/goals`.

```bash
python -m gateway_pilot.graph_v3.goal_agent \
  --registry v01 --fixture GLM-04-0 \
  --request "Kiểm tra trạng thái WAN" \
  --goals wan.status \
  --method hybrid \
  --semantic-model-dir /trusted/local/embedding-model
```

Or configure an in-process encoder:

```python
from gateway_pilot.graph_v3.graphs import GraphRegistry
registry = GraphRegistry.from_v01()
registry.configure_semantic(approved_local_encoder, min_similarity=0.62)
result = registry.retrieve(
    "WAN status", ("wan.status",), trusted_case_state,
    method="hybrid", seed_top_k=4, top_n=5
)
```

**Do not** route production traffic through an unvalidated threshold or
embedder. `min_similarity=0.62` is a conservative starting configuration, not
a measured optimal threshold. Select the threshold and vector model on an
isolated development set, freeze it, then measure held-out families of faults.
Track recall@k, precision@k, function-call budget, cost, false resolution,
unsafe execution, memory and latency; include Vietnamese/English queries and
unseen synonym/fault-family splits.

## Validation and limitations

- `tests/graph_v3/test_hybrid_retrieval.py`: mock vectors, cache invalidation,
  baseline parity, ACL/WRITE gates, bad vector rejection, goal path.
- Real sentence-transformers/e5/QNN model quality, VRAM/RAM and latency
  have **not** been checked. Local encoder code is an optional integration,
  not a hard dependency of the Edge product.
- Catalog metadata is embedded; raw log observations are never part of the
  static catalog. The query can contain verified state facts, so restrict
  embedding to approved local models with appropriate data controls.
- Offline Registry/SkillGraph mutations invalidate the cached index.
- Only the original `gos` and `bm25` methods are available in the Web API;
  `hybrid` requires trusted server-side encoder configuration first.

References: [pinned GoS contract](GRAPH_V3_UPSTREAM_CONTRACT.md) and
[task status](TASK_STATUS.md).

## Offline Function Retrieval Benchmark v1

`scripts/analysis/evaluate_retrieval.py` so sánh các phương thức trên **cùng JSONL gán nhãn** (mỗi dòng gồm `id, case_id, request, goals, expected_functions, group, split`). Script kiểm tra Function được gán nhãn có thực sự đủ điều kiện trong fixture, không chuyển gold hay world cho retriever, và báo cáo Recall@K, Precision@K, MRR@K, thời gian trung bình/P95 và kết quả theo nhóm.

```bash
python -m scripts.analysis.evaluate_retrieval \\
  --input examples/evaluation/illustrative_retrieval.jsonl \\
  --split illustrative --methods bm25 gos --top-k 5 \\
  --output runs/retrieval-eval-smoke.json
```

Đây là **illustrative smoke suite**, không phải holdout. Để đo mô hình thực, chuẩn bị tập riêng biệt và dùng `--methods bm25 gos hybrid --semantic-model-dir /trusted/local/model`, sau đó báo cáo chênh lệch và intervals trên tập lỗi unseen. Giữ kết quả trong `runs/` và không cập nhật lại các bảng benchmark lịch sử.

**Independent held-out requirement:** `evaluate_retrieval.py` accepts a real local model directory, but the repository does not include a verified downloaded embedding or a private held-out dataset. No model-quality numbers may be quoted until the operator runs the test split independently; see [acceptance](ACCEPTANCE_9_TASKS.md).
