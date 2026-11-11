# Exploratory interface follow-up — native tools v2

This follow-up was designed after observing failures in the primary JSON-text run. It is not a new blinded holdout and must not be pooled into v1 or described as a pure graph ablation. Model weights, quantization, seed, case fixtures, Core gates, graph compiler, budget and outcome scorer are unchanged.

Entry point: `python -m gateway_pilot.native_run`. This separate process replaces the model backend; it does not edit the v1 process or results. No concurrent inference with v1, to avoid latency/resource interference.

Differences: native Ollama `tools/tool_calls`; diagnostic functions advertise empty argument schemas because Core binds target/input; terminal functions `finish_case`, `mark_incomplete`, `ask_for_target` advertise diagnosis enums and evidence ID arrays. Exactly one native call is expected each decision. Native reply is translated to the same internal action contract and still validated by Core. No fallback to raw content JSON or gold/rules answer is allowed.

The interface change is a bundle of native template exposure, parameter-schema exposure, terminal function schemas and protocol wording. Improved results would not prove that native serialization alone caused the improvement. State is still supplied as normalized textual evidence; no assistant/tool history is maintained.

Development check before any follow-up test: same four dev cases `GLM-01-0`, `GLM-06-0`, `GLM-10-0`, `GLM-15-0`. Do not alter model/checklists/Core/fixtures based on follow-up test results. If the native interface cannot produce useful calls on dev, record that failure and do not present an unrun test as completed.

Any follow-up run uses a fresh directory and captures its own raw native calls, model metadata, source/data hashes and source snapshot. Its header is explicitly labelled exploratory. Report it alongside, not instead of, the full primary run.
