# OpenWrt read-only Ubus Adapter integration boundary

**State: executable with an injected transport; only mock-transport tests
have passed. No board/firmware Ubus Function has been verified.**

The existing `OpenWrtUbusAdapter` stays a skeleton with every probe failing;
no object/method names are guessed from product documents.

New `UbusReadAdapter` supports a trusted firmware-specific binding:

```python
from gateway_pilot.adapters import (
    CompositeAdapter, UbusReadAdapter, UbusReadBinding,
)

# Only a trusted service initializer may construct this:
# - registry is a versioned Function Registry with gateway READ-only Function
# - its output Port declares provenance="ubus/"
# - transport implements bounded probe(object_name, method_name) -> bool
#   and read(object_name, method_name, arguments) -> dict
transport = verified_board_transport  # to be supplied by firmware integration
backend = UbusReadAdapter(registry, {
    "firmware-registered-fid": UbusReadBinding(
        "firmware-verified-object", "firmware-verified-method"
    )
}, transport)
adapter = CompositeAdapter({"firmware-registered-fid": backend})
```

The two placeholder names in the example are **not actual board mappings**.
They cannot be shipped as executable configuration.

## Safety gates

1. No arbitrary command or dynamic shell execution; transport is injected.
2. Only registered, gateway-scope, zero-input READ Functions can bind.
3. For versioned v0.1 contracts, Adapter must be `openwrt_ubus` and
   status `PROBED_OK`; historical replay-only contracts are rejected.
4. Each Function's single output must be a Port with `ubus/` provenance.
5. `probe()` advertises `PROBE_OK` only when transport returns exactly
   boolean `True` for the explicitly bound object/method.
6. Every invocation re-probes; transport errors and malformed output fail
   closed before evidence can support a Claim.
7. `GraphRunner` rechecks permission, Function digest and argument schema.
   `EvidenceVerifier` then validates schema/scope/source/TTL/target.

## Hardware acceptance still required

Before a Function is considered implemented on firmware:

- Identify the exact hardware/firmware/ubus object and method from the board.
- Provide a transport with explicit operation deadlines and error mapping.
- Verify object/method exposure and return schema against several real captures.
- Execute negative tests for wrong target, permission, stale time and reboot.
- Check metadata provenance, boot/config revision, privilege boundaries.
- Benchmark end-to-end latency and memory on the target router/NPU.
- Keep `PROBE_OK` false until all board-backed checks pass.

```bash
python -m unittest tests.graph_v3.test_ubus_read -v
```

This boundary is **not** OpenWrt production support, and does not enable WRITE.

## Native Ubus CLI read transport (on-board only)

`gateway_pilot/adapters/ubus_cli.py` implements `UbusCliReadTransport`, a real subprocess transport for native OpenWrt `ubus`. It does `ubus -v list <object>` for exact method discovery and `ubus -S call <object> <method> <validated-JSON>` to read JSON; no shell or dynamic executable path. Transport exceptions/timeout/non-object JSON fail closed. Bind only with trusted, independently verified firmware mapping and the existing `UbusReadAdapter` contract gates. CI uses mocked subprocess, not a router. Do not set Function to `PROBED_OK` without board-backed validation.
