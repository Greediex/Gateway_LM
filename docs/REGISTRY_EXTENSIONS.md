# Declarative read-only Function/Skill extensions (opt-in)

**Status:** manifest loader and mock transport tests are implemented. This
does not turn the 270 requirements into executable Functions or validate new
firmware APIs. The existing versioned Registry and frozen benchmark data are
unchanged; extensions are **in-memory overlays**.

## What can be declared

A trusted startup process may load a JSON manifest containing:

- New typed **gateway output ports** with closed, primitive JSON schemas.
- New **Skills** with declared output ports and dependencies.
- New **READ-only gateway Functions** with one output, no input arguments,
  versioned metadata, timeout and a preexisting read permission.

Example: `examples/extensions/gateway_temperature_read.json`.

```python
from gateway_pilot.graph_v3.extension_loader import install_extension
from gateway_pilot.graph_v3.graphs import GraphRegistry

registry = GraphRegistry.from_v01()
receipt = install_extension(
    registry, "examples/extensions/gateway_temperature_read.json"
)
# The extension starts PROPOSED_NOT_VERIFIED on the v0.1 Registry.
# It is NOT callable until separately approved firmware provisioning,
# a trusted backend assignment and real device capability probe.
```

The loader never runs Python code from a manifest, never imports arbitrary
plugins, and never takes its manifest path from a user request. It rejects
unknown/new permission names, WRITE, schema references, open JSON objects,
duplicate IDs, wrong scopes, input arguments and unsupported return types.

**Transactional behavior:** the extension is validated on a separate staged
Registry, then the typed port/function/skill tables and retrieval indexes are
published together. A failed schema, permission or Skill DAG cycle does not
mutate the original Registry. The returned receipt includes a SHA-256 digest
of the manifest bytes *as normalized JSON* and the installed identifiers.

## Runtime safety and firmware promotion

- On v0.1 the new Function status is **PROPOSED_NOT_VERIFIED**, regardless of
  the manifest. Neither the loader nor mocked tests grant PROBED_OK.
- The existing pilot `GraphRegistry()` can run mock transport READ probes
  once an Adapter is deliberately assigned, for interface conformance tests.
- On actual firmware, separately verify Ubus object/method names, schema,
  deadline, permission, boot/config revision, target and provenance. Only
  trusted provisioning may promote an approved Function status.
- `UbusReadAdapter` still requires explicit assignments and checks the
  probed transport before each call. Unknown Functions cannot fall back to
  synthetic replay when a real Adapter is configured.

## Intentional limitations

This first manifest version is **only gateway READ, zero-input,
single-output**; client-target functions, multi-output contracts and
parameterized Function declarations need a separate versioned contract.
The original Core argument allowlist still limits dynamic typed arguments.
No WRITE actions, arbitrary LLM-generated tools or remote schema loads
are permitted.

```bash
python -m unittest tests.graph_v3.test_extension_loader -v
python -m unittest discover -s tests -v
```

Related: [OpenWrt Adapter](OPENWRT_ADAPTER.md),
[Runtime Stages](RUNTIME_STAGES.md), [Task Status](TASK_STATUS.md).
