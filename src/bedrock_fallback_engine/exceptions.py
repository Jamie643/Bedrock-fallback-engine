"""Exception hierarchy for bedrock-fallback-engine."""

from __future__ import annotations

from typing import Any


class BedrockEngineError(Exception):
    """Base class for all bedrock-fallback-engine errors."""


class BedrockRouteExhausted(BedrockEngineError):
    """
    Raised when every Bedrock route (region + model pair) has failed.

    Attributes:
        errors: List of (route, exception) tuples in the order they failed.
    """

    def __init__(
        self,
        message: str,
        errors: list[tuple[str, Exception]] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors: list[tuple[str, Exception]] = errors or []


class BedrockThrottlingError(BedrockEngineError):
    """
    Raised when Bedrock returns a throttling (429) response.

    Kept distinct so the engine can decide whether to fail over to another
    region (throttling is regional) or retry in-place.
    """

    def __init__(self, message: str, response: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.response: dict[str, Any] = response or {}
