# Paper sources and code for Gateway LM v0.1

Checked: 2026-11-07. The audit covers all 19 distinct arXiv papers in the supplied HTML. Six attributable public author repositories were shallow-cloned; twelve author implementations were not located in the reviewed primary text and targeted title/author searches. One additional classical distillation reference appears in embedded reference metadata and is recorded as reference-only. This does not prove the unlocated code is unpublished.

Source download and inspection only. No upstream installation, cloud call, Docker topology or paper benchmark was run. Gateway pilot results are separate from reproducing these papers.

## Pinned clones

| Paper | Repository | Commit | License |
|---|---|---|---|
| [GoS](https://arxiv.org/abs/2604.05333) | [third_party/graph-of-skills](https://github.com/davidliuk/graph-of-skills) | `203f60a2c689da055ce1ac351eb3cb9912a3bca7` | MIT |
| [SkillDAG](https://arxiv.org/abs/2606.03056) | [third_party/SkillDAG](https://github.com/Ericbai06/SkillDAG) | `2bd7baffae58854018f75857e5626a4a28a705ae` | MIT |
| [SE-GoS](https://arxiv.org/abs/2609.08228) | [third_party/SEGoS](https://github.com/PKUfudawei/SEGoS) | `0efac764c94380d1bbf741189b814547eb6679b6` | Apache-2.0 |
| [SkillSeek](https://arxiv.org/abs/2609.38822) | [third_party/SkillSeek](https://github.com/guanqun-yang/SkillSeek) | `573a98be7ae4ee537463d1759f09e4511d333f66` | NO_ROOT_LICENSE_FOUND |
| [JitSkill](https://arxiv.org/abs/2611.01701) | [third_party/JitSkill](https://github.com/XMUDeepLIT/JitSkill) | `a6b1945fe96dc17c53f8442ad735b55fceff5d1f` | MIT |
| [FaulT-Bench](https://arxiv.org/abs/2608.27021) | [third_party/FaulT-Bench](https://github.com/Overlxrd-uwu/FaulT-Bench) | `ab8c45f808fb0c2a1ae5c029bcfe0194617c36f2` | MIT |

Clone command: `git -c credential.helper= clone --depth 1 <verified-url> gateway_lm_pilot/third_party/<name>`. All six successful clones returned exit code 0. Sandbox network attempts failed; authorized network-enabled retries succeeded. Commit, shallow status, file count and root license hashes are recorded in `paper_sources.json`.

SkillSeek has no root LICENSE/COPYING at its pinned commit; source inspection does not grant permission to redistribute it. SE-GoS retains upstream licenses for its SkillsBench harness; the root Apache license is not a blanket license for every third-party file.

### Community reproductions cloned on 2026-11-09

| Paper | Repository | Commit | Use in Gateway |
|---|---|---|---|
| GraSP | [third_party/grasp-reproduction](https://github.com/luyu020816-droid/skill-dag) | `e8eaf48522950a9148cb30b9672e1aeca0ba82e6` | Reference for typed DAG and bounded repair |
| HyperAgent | [third_party/auto-research](https://github.com/daiwk/auto-research) | `d93821a6883cf29e1b69c6686665f4848aa1ba9d` | Reference for the independent mini-suite and its deficit-expansion model |

Both clones are shallow. The GraSP README and Auto Research package metadata declare MIT, and neither checkout has a root LICENSE file at the pinned commit. Gateway uses its own implementations for these mechanisms. Graph v3 still calls the pinned GoS kernel.

### Runtime use in WF-067 and WF-069

| Checkout | Current use or candidate for reuse |
|---|---|
| GoS | Gateway calls `build_transition_matrix`, `build_personalization` and `personalized_pagerank` from the pinned kernel. It ranks ready execution nodes and is an optional RAG comparison arm. |
| SkillDAG | WF-067 calls the pinned `expand_set` and `check_set` with an in-memory adapter. The Gateway compiler owns execution eligibility and typed bindings. |
| SE-GoS | Offline trace-to-delta experiments are relevant once a Gateway trace adapter and held-out evaluation exist. The released harness expects Harbor data. |
| SkillSeek | Its lexical and semantic baselines are a reference for catalog retrieval evaluation. The pinned checkout lacks a root license file. |
| JitSkill | The explicit progress record is a candidate for an adapter around verified observations. The learned navigator and latent projection use separate training and serving artifacts. |
| FaulT-Bench | Its tickets, injected failures and scorer are relevant to a separate network benchmark. The released topologies and licenses have their own scope. |
| GraSP reproduction / Auto Research | Design references for typed DAG repair and producer expansion. Current Gateway implementations are local. |

## Source-by-source notes

### GoS

[Dependency-Aware Structural Retrieval for Massive Agent Skills](https://arxiv.org/abs/2604.05333) ([primary full text](https://arxiv.org/html/2604.05333)).

Lexical/semantic seeds and prerequisite recovery; use deterministic closure first, optional reverse-aware PPR later.

Code: CLONED_PINNED. Supplied HTML code link plus author repository README/citation identifies matching arXiv paper. [Repository](https://github.com/davidliuk/graph-of-skills).

### GraSP

[GraSP: Graph-Structured Skill Compositions for LLM Agents](https://arxiv.org/abs/2604.17870) ([primary full text](https://arxiv.org/html/2604.17870)).

Typed DATA/STATE/ORDER DAG; per-node verifier and bounded local repair. A Gateway adaptation is not a reproduction of original benchmarks.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. The arXiv appendix names `src/esg.py` but does not link a repository for it. The public [GraSP plugin specification](https://github.com/luyu020816-droid/skill-dag/blob/main/grasp-spec.md) explicitly describes itself as an unofficial reproduction. Gateway implements its own diagnostic adaptation.

### SkillDAG

[SkillDAG: Self-Evolving Typed Skill Graphs for LLM Skill Selection at Scale](https://arxiv.org/abs/2606.03056) ([primary full text](https://arxiv.org/html/2606.03056)).

Typed dependency/conflict edges; version graph changes and keep them reviewed during initial pilot.

Code: CLONED_PINNED. Supplied HTML code link plus author repository README/citation identifies matching arXiv paper. [Repository](https://github.com/Ericbai06/SkillDAG).

### SE-GoS

[SE-GoS: Self-Evolving Graph-of-Skills for Skill Library at Scale](https://arxiv.org/abs/2609.08228) ([primary full text](https://arxiv.org/html/2609.08228)).

Offline topology/weight/description evolution from verified traces; defer learning until reliable verifier and separate training split exist.

Code: CLONED_PINNED. Supplied HTML code link plus author repository README/citation identifies matching arXiv paper. [Repository](https://github.com/PKUfudawei/SEGoS).

### HyperAgent

[HyperAgent: Planning and Acting over Tool-Schema Hypergraphs for Tool-Use LLM Agents](https://arxiv.org/abs/2608.02650) ([primary full text](https://arxiv.org/html/2608.02650)).

Typed output-to-input producer expansion for deficits in current state; lightweight explicit contracts can implement this without graph database.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. The reviewed arXiv full text does not link an implementation repository. The public [Auto Research HyperAgent adapter](https://github.com/daiwk/auto-research/blob/main/docs/agent-research/2608.02650-hyperagent/README.md) describes an independent mini-suite reproduction. Gateway implements its own typed producer expansion.

### TGR

[Tool Graph Retriever: Exploring Dependency Graph-based Tool Retrieval for Large Language Models](https://arxiv.org/abs/2508.05152) ([primary full text](https://arxiv.org/html/2508.05152)).

Dependency recovery addresses prerequisite omission; deterministic closure does not reproduce the trained discriminator/graph-convolution method.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### Tool-to-Agent Retrieval

[Tool-to-Agent Retrieval: Bridging Tools and Agents for Scalable LLM Multi-Agent Systems](https://arxiv.org/abs/2511.01854) ([primary full text](https://arxiv.org/html/2511.01854)).

Joint Skill/Function candidates linked many-to-many; avoid hard filtering to only the first selected Skill.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### SkillTrace

[SkillTrace: Traversing a Query-Skill Graph for Composable LLM Agents](https://arxiv.org/abs/2608.02356) ([primary full text](https://arxiv.org/html/2608.02356)).

Query decomposition and prerequisite recovery. Unrelated security scanners and provenance-auditing projects with same name are not this paper.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### SkillSeek

[SkillSeek: Revisiting Agent Skill Retrieval at Marketplace Scale](https://arxiv.org/abs/2609.38822) ([primary full text](https://arxiv.org/html/2609.38822)).

Include lexical/BM25 baseline before adding dense retrieval or a cross-encoder. No root license at pinned commit: inspection only; do not vendor-copy into product.

Code: CLONED_PINNED. Direct paper link. [Repository](https://github.com/guanqun-yang/SkillSeek).

### SkillBrowser

[SkillBrowser: Selective Skill Exposure for Scalable Skill-Using Agents](https://arxiv.org/abs/2610.23554) ([primary full text](https://arxiv.org/html/2610.23554)).

Expose small relevant context on demand as evidence changes; measure extra latency and missed useful skills.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### JitSkill

[Just-in-Time Skill Retrieval via Long-Horizon State Tracking](https://arxiv.org/abs/2611.01701) ([primary full text](https://arxiv.org/html/2611.01701)).

Track completed/failed operations and reuse verified state. Original learned runtime requires CUDA and larger models; this is not reproduced on a sub-3B model.

Code: CLONED_PINNED. Direct paper link. [Repository](https://github.com/XMUDeepLIT/JitSkill).

### FaulT-Bench

[FaulT-Bench: Towards Benchmarking Network Troubleshooting LLM Agents under Unreliable User Tickets](https://arxiv.org/abs/2608.27021) ([primary full text](https://arxiv.org/html/2608.27021)).

Test healthy false-premise, wrong-device, wrong-cause and vague tickets. Original environment is Kathara/NIKA, distinct from OpenWrt replay.

Code: CLONED_PINNED. Direct paper link. [Repository](https://github.com/Overlxrd-uwu/FaulT-Bench).

### Workflow-Aware Scheduling

[Workflow-Aware Communication and Computation Scheduling for Mobile Edge AI Agents](https://arxiv.org/abs/2610.29337) ([primary full text](https://arxiv.org/html/2610.29337)).

Future resource scheduling over partly revealed workflows; no wireless allocation experiment in this pilot.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### APEX

[APEX: A Network-Native Time-Series Foundation Model for Forecasting and Anomaly Detection for Wireless Edge Operations](https://arxiv.org/abs/2606.11553) ([primary full text](https://arxiv.org/html/2606.11553)).

Telemetry forecasting/anomaly model is distinct from instruction LLM orchestration; do not claim reproduction without data/weights.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### PLUME

[PLUME: Building a Network-Native Foundation Model for Wireless Traces via Protocol-Aware Tokenization](https://arxiv.org/abs/2603.13647) ([primary full text](https://arxiv.org/html/2603.13647)).

Protocol-aware packet modeling is separate from Skill Graph diagnosis orchestration; model, tokenizer and packet dataset required.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### QoEReasoner

[QoEReasoner: An Agentic Reasoning Framework for Automated and Explainable QoE Diagnosis in RANs](https://arxiv.org/abs/2606.01925) ([primary full text](https://arxiv.org/html/2606.01925)).

Normalize numerical observations into evidence; constrain hypotheses with network knowledge, not skill-dependency edges.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### RCA Copilot

[RCA Copilot: Transforming Network Data into Actionable Insights via Large Language Models](https://arxiv.org/abs/2507.03224) ([primary full text](https://arxiv.org/html/2507.03224)).

Separate measured features/statistical tests from generated explanations; unrelated similarly named projects are not this paper.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

### NetOps Safety

[Large Language Models for Agentic NetOps and AIOps: Architectures, Evaluation, and Safety](https://arxiv.org/abs/2605.12729) ([primary full text](https://arxiv.org/html/2605.12729)).

Independent policy gates, budgets, invariants, recovery and audit. Survey/evidence-audit dataset is not an executable router-agent runtime.

Code: AUTHOR_REPOSITORY_NOT_LOCATED. No attributable implementation repo located in reviewed arXiv full text and targeted title/author searches. Not proof none exists..

## Transfer to the current pilot

Compare identical sub-3B model, decoding, cases and prompt policy across flat candidates, lexical/BM25 retrieval and graph/schema-aware candidates. Score raw model decisions separately from Core compiler/policy/validator interventions. A blocked bad decision remains a model error even when Core safety succeeds.

Use WF-018 WAN, WF-023 DNS, WF-024 DHCP and WF-039 system health first. Preserve target, measurement point, timestamp/TTL, provenance and UNKNOWN. Include healthy false-premise tickets, stale/missing evidence, unsupported capability, wrong target, absent producer and unapproved write cases.

Useful inspected code entry point: `third_party/graph-of-skills/gos/core/retrieval.py` implements transition matrix and personalized PageRank using NumPy. `third_party/SkillDAG/src/skilldag/graph.py` implements typed graph operations. These files were inspected, not run by this audit.

JitSkill original [README](https://github.com/XMUDeepLIT/JitSkill) documents CUDA, Qwen3-8B navigator and a larger frozen executor. Reusing explicit case-state ideas does not reproduce its learned latent-state mechanism on a 1.5B model.

OpenWrt ubus/UCI/netifd/iwinfo, LangGraph and edge-agents links in the HTML are infrastructure references rather than author implementations of these papers; this paper-code audit did not clone them.

## Embedded classical reference

[Distilling the Knowledge in a Neural Network](https://arxiv.org/abs/1503.02531) appears in embedded reference metadata for future compression/training. Its primary arXiv metadata was verified. No author implementation was linked there; no generic third-party distillation repo was substituted. The pilot uses an existing small model without distillation.
