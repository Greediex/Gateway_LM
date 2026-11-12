"""Structured adapter results: explicit observation batch or explicit tool failure.

Inspired by MCP structured output / is_error separation. This is an internal
contract only; it does not implement MCP transport. An LLM cannot construct
these objects to bypass Function ACL or the evidence verifier.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolResult:
    """Typed response from an assigned Adapter.

    A successful result must contain exactly the outputs declared by the
    Function; EvidenceVerifier checks the exact port set, schema and trust
    boundary. Errors never carry observations.
    """

    observations: tuple[dict, ...] = ()
    is_error: bool = False
    error_code: str | None = None

    def __post_init__(self):
        if not isinstance(self.observations, tuple) or any(
            not isinstance(e, dict) for e in self.observations
        ):
            raise ValueError("tool_result_invalid_observations")
        if type(self.is_error) is not bool:
            raise ValueError("tool_result_invalid_status")
        if self.is_error:
            if self.observations:
                raise ValueError("tool_error_must_not_claim_observations")
            if not isinstance(self.error_code, str) or not (
                1 <= len(self.error_code) <= 128
            ):
                raise ValueError("tool_error_requires_code")
        elif self.error_code is not None or not self.observations:
            raise ValueError("tool_success_requires_observations")
