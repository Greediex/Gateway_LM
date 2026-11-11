# Model interface limits and next experiment

Checked 2026-11-07. Read-only review of `gateway_pilot/run.py`; no inference calls, installations, code/data/result changes or changes to the running 48-case x 5-arm protocol. This note records interface limitations, not new benchmark results.

## What the current interface tests

`model_decision` (run.py:105-121) calls Ollama `/api/chat` with `format="json"`, `think=false`, temperature 0, seed fixed, context 8192 and at most 180 generated tokens. It parses only `message.content` with `json.loads`. The request does not supply a `tools` array and does not consume `message.tool_calls`. Thus it tests a custom JSON action protocol in ordinary generated text, rather than Ollama native function calling.

`prompt` (run.py:71-102) rebuilds two messages for each decision: a system instruction and a user message containing the workflow checklist, candidate functions, current normalized evidence and recent Core errors. Previous assistant actions and results are represented through state text; they are not preserved as a native assistant/tool conversation. The module declares `SCHEMA` (run.py:51), but the request passes the string `json`, not that schema. The graph arm may insert prerequisites and Core binds/validates invocation arguments; raw proposal quality and these deterministic interventions must remain separate.

`graph_batch` (run.py:129-169) gives measurement acquisition to Core and asks the model only for a verdict. Its success measures analysis of a supplied evidence bundle, not autonomous model planning. Comparing it with interactive arms changes both orchestration responsibility and evidence availability, not only the presence of graph edges.

## Official interface options

| Option | Official behavior | Consequence for this pilot |
|---|---|---|
| Non-thinking | Ollama `think=false` requests no thinking output when supported. Qwen3 provides a hard `enable_thinking=false` switch in its own chat template. | Current results concern non-thinking execution; they do not test Qwen3 thinking mode. |
| JSON syntax mode | `format="json"` requests structured JSON. | Valid JSON can still use wrong action keys, wrong function names or unsupported conclusions. |
| Schema-constrained output | Pass a JSON Schema object as `format`; validate the returned object in application code. | Could reduce protocol/schema failures; cannot itself prove argument provenance, evidence sufficiency or correct diagnosis. |
| Native tool calling | Supply `tools` with function names, descriptions and parameter schemas; read assistant `message.tool_calls`; append the assistant message and tool results before asking for the next decision. | Tests the model-facing tool template/parser and dialogue path omitted by the custom JSON protocol. Core must still authorize and verify every invocation. |

Sources: [Ollama thinking](https://docs.ollama.com/capabilities/thinking), [structured outputs](https://docs.ollama.com/capabilities/structured-outputs), [native tool calling](https://docs.ollama.com/capabilities/tool-calling). Native calls are proposals to the application, not permission to execute arbitrary operations.

The [official Qwen3-1.7B model card](https://huggingface.co/Qwen/Qwen3-1.7B) documents tool use in both modes and recommends Qwen-Agent for its tool templates/parsers. It distinguishes the hard non-thinking switch from the `/no_think` prompt-level soft switch. Its recommended non-thinking sampling is temperature 0.7, top-p 0.8, top-k 20; for thinking it recommends temperature 0.6, top-p 0.95, top-k 20 and advises against greedy decoding. These recommendations differ from the pilot's deterministic temperature-0 protocol. That is a protocol choice to report, not a reason to alter an experiment already running, and does not establish which setting will work better on Gateway cases.

## Model and hardware interpretation

The main experiment reports the freshly downloaded `qwen3:1.7b`, Q4_K_M, with Ollama `parameter_count=2031739904` (about 2.032B, still strictly below 3B). Preserve both the model tag and observed numeric count; do not silently substitute the tag's 1.7B label for the artifact metadata. The supplied run observation `size_vram=0` indicates no model allocation reported in GPU VRAM. These exact runtime facts were supplied by the main experiment and were not re-queried in this documentation-only review.

This experiment can establish performance of that quantized artifact, custom action interface, prompt/checklist, budgets and Core/graph implementation on the fixed synthetic Gateway cases. It can expose errors in tool selection, prerequisite handling, evidence use and termination under that setup. It cannot establish an intrinsic capability ceiling of every model below 3B, isolate quantization from base-model ability, validate native tool calling or thinking mode, or predict NPU/board latency and effects on packet forwarding. CPU-host results remain distinct from real OpenWrt and Qualcomm deployment evidence.

## Recommended next experiment, after this frozen run

Run a separately versioned paired interface ablation, with the same model digest, synthetic worlds, exposed candidate sets, evidence scope, semantic validator, tool budget and non-thinking settings. Compare: (A) current JSON-text actions, (B) JSON Schema-constrained actions, and (C) native `tools`/`tool_calls` with assistant/tool message history. Encode FINISH/ASK_USER/INCOMPLETE as explicit structured terminal decisions in C; keep them separate from firmware tools. Apply flat/retrieval/graph treatments within each interface so an interface gain is not mislabeled a graph gain. Keep `graph_batch` as a separate Core-orchestration operating point.

Score first-proposal function/argument correctness, JSON/schema failures, rejected and unsupported-FINISH proposals, prerequisite insertions, repeated actions, autonomous end-to-end success, token use, truncation/done_reason and latency. Report each intervention separately; a safe Core rejection is still a bad model proposal. Choose interface/prompt adjustments on development cases, lock them, and use an untouched held-out suite for the next claim. Do not keep tuning against these 48 test outcomes.

Test thinking or Qwen-recommended sampling only as a subsequent, separately labeled factor with an adequate explicit generation/time budget and repeated seeds. Increasing thinking budget and changing decoding simultaneously with native tools would confound the comparison. No such changes or reruns were made here.
