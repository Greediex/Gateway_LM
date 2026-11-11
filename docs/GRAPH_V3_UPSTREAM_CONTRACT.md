# Graph v3: upstream kernel and Gateway contract

Source contract checked 2026-11-07. Documentation/source inspection only; no implementation, inference, installation or benchmark was performed by this audit. Local paths below are relative to the repository root. The supplied HTML remains the product design reference; this contract isolates the graph mechanisms proposed for v3.

## 1. What is actually reusable from pinned GoS

Pin: `third_party/graph-of-skills`, commit `203f60a2c689da055ce1ac351eb3cb9912a3bca7`, MIT. The standalone file `gos/core/retrieval.py` imports NumPy and standard typing only. Importing that file through a tightly scoped loader avoids executing the full engine/package initialization; preserve upstream code and record its file hash rather than copying/modifying it invisibly. Fail explicitly if the expected file/hash or NumPy dependency is unavailable. Source: [GoS repository](https://github.com/davidliuk/graph-of-skills), [pinned kernel](https://github.com/davidliuk/graph-of-skills/blob/203f60a2c689da055ce1ac351eb3cb9912a3bca7/gos/core/retrieval.py). The pinned file was inspected locally; the web fetch for that exact kernel URL returned a cache miss.

Exact public calls in the pinned file:

| Call | Input contract | Result |
|---|---|---|
| `build_rank_distribution(count)` | Integer count; nonpositive returns empty. | Normalized reciprocal-rank vector, weights proportional to `1/(rank+1)`. |
| `build_transition_matrix(nodes, edges, reverse_weights=None)` | Nodes expose `.name`; edges expose `.source`, `.target`, `.type`, `.weight`. | Dense row-stochastic NumPy matrix and `name_to_index` map. |
| `build_personalization(node_count, seed_indices, seed_weights=None)` | Seed indices refer to the exact node order. Optional weights normalized by their sum. | Personalization vector; absent/mismatched/nonpositive-total weights fall back to reciprocal rank. Repeated indices accumulate. |
| `personalized_pagerank(transition, personalization, damping=0.2, max_iter=50, tol=1e-6)` | Compatible matrix/vector. | Normalized score vector after bounded iteration or L1 convergence. |

The integration call sequence is `T,index = build_transition_matrix(...)`, then `p = build_personalization(...)`, then `scores = personalized_pagerank(T,p,damping=restart_probability,max_iter=...,tol=...)`. This is also the sequence used by upstream `gos/core/engine.py:3565-3577`.

**Damping convention matters:** upstream computes `next = damping*p + (1-damping)*T.T@scores`. Thus 0.2 is restart/teleport probability, and propagation probability is 0.8. It is not NetworkX's usual `alpha=0.2` propagation convention; a NetworkX cross-check would use `alpha=0.8`, with matching dangling-node handling. Upstream gives zero-outdegree nodes self-loops, rather than redistributing their mass globally.

Default reverse factors are dependency=1.0, workflow=0.5, semantic=0.2, alternative=0.1. A forward edge adds its full positive weight; the reverse edge adds that weight multiplied by the factor before row normalization. Duplicate edges add mass. Unknown endpoints are skipped by the kernel.

Adapter guards must be stricter than kernel assumptions: unique node names; finite nonnegative seed weights; finite strictly positive included diffusion edge weights; valid endpoints; compatible array shapes and bounded restart/iterations. Two pinned quirks must have explicit regression coverage: `weight=0` becomes 1 because of upstream `or 1.0`, and `reverse_weights={}` selects defaults because of `or DEFAULT_REVERSE_WEIGHTS`. Filter excluded/zero-weight edges before calling the kernel; to disable reversals pass an explicit nonempty map with zero values. Do not send conflicts or exclusion edges to diffusion as zero/negative pseudo-weights.

## 2. Edge mapping and four separate structures

| Source relation / structure | Canonical meaning | GoS diffusion projection | Hard execution consequence |
|---|---|---|---|
| Skill `A depends_on B` (HTML/SkillDAG) | A consumes a capability supplied by B. | `B -> A`, type `dependency`; keep source relation metadata separately. | Only an explicit validated prerequisite contract can force execution. |
| Skill `produces_for` | Producer -> consumer when declared and verified. | Same direction, `dependency`. | Requires typed I/O/state proof. |
| `composes_with` | Soft complementary capability. | Explicit `workflow` projection, with declared symmetry policy; avoid accidental double-counting. | Never invent a hard prerequisite. |
| `similar_to` / `specializes` | Semantic relation / child-parent capability hierarchy. | Deliberate `semantic` projection, retaining original type and direction in trace. | Not a data dependency by itself. |
| `alternative_to` | Potential substitute. | `alternative` for ranking only. | Substitute only after compatible scope/output/preconditions and policy are checked. |
| `conflicts_with` | Exclusion/scheduling constraint. | Excluded from PPR graph. | Reject, serialize or choose compatible branch; remain a hard gate. |
| `G_SF` membership | Many-to-many Skill <-> Function association. | If projected into PPR, use explicitly named membership edges/weights; this is a Gateway extension. | Membership grants no permission and creates no mandatory action. |
| `H_F` schema dependency | Function hyperedge consumes all required typed ports/guards and produces ports/effects. | A separate ranking projection may be producer -> consumer. | Backward deficit expansion finds a safe producer for each unsatisfied input. |
| `G_run` invocation DAG | Concrete calls with bound target/arguments. | Do not confuse with static retrieval graph. | DATA/STATE/ORDER edges, verifier and invocation states control execution. |

Direction evidence: pinned GoS `engine.py:2027-2048` constructs dependency edges from producer outputs to consumer inputs. Pinned SkillDAG `src/skilldag/graph.py:829-843` follows outgoing `depends_on` from consumer to prerequisite. Its relation enum and symmetric types are at `:43-73`, and conflict edges are excluded from neighbor walks. [Pinned SkillDAG source](https://github.com/Ericbai06/SkillDAG/blob/2bd7baffae58854018f75857e5626a4a28a705ae/src/skilldag/graph.py). Do not reuse unconverted adjacency between these formats.

A projection is an adaptation: GoS's kernel has no native Skill/Function bipartite semantics, ACL, firmware probe or typed execution planner. Record original edges and projected edges so direction, weights and skipped conflicts are inspectable.

## 3. Minimum Gateway-specific graph behavior from the HTML

The HTML Architecture Deep Dive sections 04-07 require the following behavior, distinct from upstream PPR:

- Query reflects request plus outstanding goals and current verified state. New evidence/failures trigger bounded reretrieval; already satisfied inputs are not reacquired solely because a static dependency edge exists.
- Capability, actor permission, target/scope and version are hard filters. Ranking score cannot authorize a forbidden call. Cross-skill retrieval is allowed within these gates and is recorded in a plan revision.
- Producer compatibility checks input/output type, target scope, provenance and freshness, plus conjunctive prerequisites. Having a FALSE-valued observation is not the same as satisfying a guard requiring TRUE. UNKNOWN stays unresolved.
- A producer search compares safe alternatives using declared cost/latency/risk/quality inputs and bounded search; it must not silently choose alphabetical ID. Preserve the objective and rejection reason in trace. This cost selection is Gateway logic, not an optimization guaranteed by the GoS kernel.
- Compiler emits concrete invocation nodes, typed DATA/STATE/ORDER edges, bound arguments, verifier and bounded resource requirements. Validate no hard cycle, missing input or conflict before execution. Node states distinguish pending/ready/running/succeeded/failed/blocked/inconclusive/skipped.
- Node verification updates Case State. Failed evidence invalidates only genuinely affected descendants; bounded retry/rebind/whitelisted substitution creates an audited plan revision. This remains a limited adaptation of GraSP, not its complete five-operator runtime.

Primary mechanisms: [GraSP typed DAG and repair](https://arxiv.org/html/2604.17870), [HyperAgent state-conditioned typed producer expansion](https://arxiv.org/html/2608.02650). The supplied HTML explicitly presents the combined design as a Gateway proposal needing its own evaluation, not a combined algorithm already proven by those papers.

## 4. Reference fixtures for meaningful parity and semantic tests

These are recommended fixtures, **not executed results**. Check raw arrays/scores from the pinned kernel against an independent small reference where feasible; rank-only or wrapper-vs-itself assertions are insufficient.

1. **Hand-computed transition matrix:** nodes A,B,C; edges A->B dependency weight2, A->C semantic weight1, B->C workflow weight3. Defaults yield rows `[0,2/3,1/3]`, `[2/5,0,3/5]`, `[2/17,15/17,0]`. This detects reverse-factor, orientation and normalization mistakes.
2. **Direction recovery:** producer A->consumer B, dependency weight1. Seed B. With default reverse factor the matrix swaps A/B; converged PPR is `[4/9,5/9]` at restart0.2. Use max_iter>=500/tol<=1e-12 for the analytic-limit assertion. The default 50 iterations need not equal the analytic limit to 1e-12; separately compare default settings with upstream output.
3. **Disabled reverse:** same graph, explicit `{"dependency":0.0}`. Seed B stays `[0,1]`; A receives no mass. Passing `{}` must be recognized as upstream defaults, not “reverse disabled.”
4. **Personalization:** `node_count=3`, indices `[0,2]`, weights `[3,1]` gives `[.75,0,.25]`; indices `[0,0,2]` without weights accumulate reciprocal ranks to `[9/11,0,2/11]`. Also test mismatched weight lengths, empty seeds and singleton/dangling nodes using documented upstream fallback behavior.
5. **Excluded-edge safety:** adapter filters/rejects zero, negative and nonfinite diffusion weights and conflicts before kernel invocation; invalid original endpoints fail clearly. Verify it does not turn a weight-zero conflict into a positive edge through the upstream quirk.
6. **Independent graph semantics:** consumer `depends_on` prerequisite becomes producer->consumer for diffusion, while execution is prerequisite-before-consumer. Composition/similarity cannot force extra calls. Include a conjunctive two-input consumer and an already-satisfied prerequisite.
7. **Decision-changing state:** a newly verified observation changes a deficit/query; repeat retrieval must not repeat a completed usable producer. Stale/wrong-target/UNKNOWN observations do not satisfy guards. A guard requiring TRUE remains blocked by a verified FALSE value.
8. **Alternative/cost and failure repair:** two compatible producers with different declared cost; choose the admissible lower-cost plan, then reject it under a changed capability/scope or recorded failure and choose the remaining safe producer. Confirm unrelated verified branches survive local revision.
9. **Fairness and boundedness:** apply equal final candidate/context and tool/time budgets across comparable retrieval arms. Test failure when indispensable prerequisite closure cannot fit, rather than silently truncating dependencies and executing an invalid plan.

Pin and hash the reference fixture inputs, mapping policy and upstream file alongside source/model/data identities. A passing kernel parity test establishes the reused diffusion computation; it does not establish a faithful full GoS pipeline, optimal retrieval quality or better diagnostic outcomes.

## 5. Claim boundary

Upstream GoS engine also performs skill parsing/indexing, query rewrite, hybrid seed generation, score reranking, hydration and context packing (`engine.py:3490-3679`). Using its three NumPy functions with custom BM25 seeds, Skill/Function projections and a new planner should be labeled **Gateway graph adaptation reusing pinned GoS PPR kernel**. It does not reproduce full GoS, SkillDAG's embedding/BFS plus propose-edit interface, SE-GoS evolution, GraSP benchmarks or all HTML product modules. Keep the frozen earlier pilot and its reports unchanged; any v3 result needs a new versioned run and appropriate held-out evaluation.
