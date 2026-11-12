"""Bounded on-device Ubus CLI transport; never invokes a shell.

An approved Function mapping is configured separately in UbusReadAdapter.
This transport only implements object/method discovery and JSON reads.
Run on OpenWrt with ubus installed; CI mocks subprocess, not firmware.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess

from ..core import PlanError
from .ubus_read import UbusReadBinding


class UbusCliReadTransport:
    def __init__(self, *, executable="ubus", timeout_s=2, max_output=32768):
        if executable != "ubus":  # no user-supplied binaries or command paths
            raise ValueError("only_system_ubus_binary_allowed")
        if (type(timeout_s) not in (int, float) or not 0 < timeout_s <= 10
                or type(max_output) is not int or not 256 <= max_output <= 1048576):
            raise ValueError("invalid_ubus_transport_limits")
        resolved = shutil.which("ubus")
        if not resolved:
            raise ValueError("ubus_not_installed_on_host")
        self.executable = resolved
        self.timeout_s, self.max_output = timeout_s, max_output

    def _run(self, args):
        # All arguments are previously validated names, or JSON serialized
        # from an allowed Function contract. Never interpolate a shell string.
        try:
            result = subprocess.run(
                [self.executable, *args], shell=False,
                capture_output=True, check=False,
                text=True, encoding="utf-8",
                timeout=self.timeout_s,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PlanError("ubus_transport_unavailable") from exc
        if result.returncode != 0:
            raise PlanError("ubus_nonzero_status")
        if len(result.stdout.encode("utf-8")) > self.max_output:
            raise PlanError("ubus_output_too_large")
        return result.stdout

    def probe(self, object_name, method_name):
        UbusReadBinding(object_name, method_name)
        try:
            # Exact method parsing of ubus -v list output, not a guessed
            # object-wide probe. A firmware-specific conformance test still
            # validates the response schema before enabling PROBED_OK.
            output = self._run(["-v", "list", object_name])
        except PlanError:
            return False
        pattern = r"(?m)^[ \t]*['\"]" + re.escape(method_name) + r"['\"]\s*:\s*\{"
        return re.search(pattern, output) is not None

    def read(self, object_name, method_name, arguments):
        UbusReadBinding(object_name, method_name)
        if not isinstance(arguments, dict):
            raise PlanError("ubus_args_must_be_object")
        try:
            request = json.dumps(arguments, ensure_ascii=False, allow_nan=False,
                                 separators=(",", ":"), sort_keys=True)
        except (ValueError, TypeError) as exc:
            raise PlanError("ubus_invalid_arguments") from exc
        if len(request.encode("utf-8")) > 4096:
            raise PlanError("ubus_request_too_large")
        output = self._run(["-S", "call", object_name, method_name, request])
        try:
            payload = json.loads(output)
        except ValueError as exc:
            raise PlanError("ubus_invalid_json_result") from exc
        if not isinstance(payload, dict):
            raise PlanError("ubus_response_must_be_object")
        return payload
