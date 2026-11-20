# contracts/

JSON Schemas (draft 2020-12) of every message the agent receives or sends. Validate your producer or
consumer against them (for example with Python `jsonschema`) instead of relying on prose.

| File | Validates | Direction |
|---|---|---|
| `stt-transcript-v1.schema.json` | `stt.transcript` event payload | into the agent |
| `firmware-command-v1.schema.json` | The 5-field command envelope (`ubus call router_display llm_command <envelope>`) | out of the agent |
| `llm-command-ack-v1.schema.json` | The executor's synchronous acknowledgement of that call | back to the agent |
| `agent-router-result-v1.schema.json` | `agent_router.result` event (the fields an executor reads) | out of the agent |
| `agent-router-stage-v1.schema.json` | `agent_router.stage` progress event; also describes `agent_router.cancel` (opposite direction) | out of / into the agent |
| `agent-router-partial-v1.schema.json` | `agent_router.partial` answer-so-far event | out of the agent |
| `router-context-registry-v1.json` | **Not a schema**: the registry `router-contextd` loads (19 record kinds, fields, roles, issuers, storage budget) | data publisher |
| `router-context-record-v1.schema.json` | One publisher record (generated from the registry) | data publisher |
| `router-context-query-v1.schema.json` | A read query to the publisher | agent → publisher |
| `router-context-view-v1.schema.json` | The publisher's answer | publisher → agent |
| `router-context-manifest-v1.schema.json`, `router-context-live-v1.schema.json` | Files the publisher writes in `/tmp/router_context/` | data publisher |

Descriptions inside the schemas may refer to documents of the original project by file name; the
documentation of this package (`docs/03_inputs.md`, `docs/04_outputs.md`) is the reference here. Schemas
describe what the executor **accepts**; `ubus call router_display status` lists what it actually
implements (`commands` vs `commands_planned`).
