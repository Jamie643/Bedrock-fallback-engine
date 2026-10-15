"""Exception hierarchy for bedrock-fallback-engine."""

from __future__ import annotations

from typing import Any


class BedrockEngineError(Exception):
    """Base class for all bedrock-fallback-engine errors."""


class BedrockThrottlingError(BedrockEngineError):
    """
    Raised when Bedrock returns a throttling response.

    Kept distinct because throttling is *regional* — a 429 in us-east-1
    does not imply us-west-2 is also throttled.
    """

    def __init__(
        self,
        message: str,
        response: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.response: dict[str, Any] = response or {}


class BedrockTransientError(BedrockEngineError):
    """
    Raised on retryable, non-throttling Bedrock failures.

    Examples: ModelTimeoutException, InternalServerException,
    ServiceUnavailableException.
    """


class BedrockRouteExhausted(BedrockEngineError):
    """
    Raised when every route in the chain has failed.

    Attributes:
        errors: Ordered list of ``(route_label, exception)`` tuples.
                Preserves which route failed with what — invaluable for
                CloudWatch dashboards and incident reports.
    """

    def __init__(
        self,
        message: str,
        errors: list[tuple[str, Exception]] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors: list[tuple[str, Exception]] = errors or []

    def __str__(self) -> str:
        base = super().__str__()
        if not self.errors:
            return base
        detail = "\n".join(f"  - {label}: {exc}" for label, exc in self.errors)
        return f"{base}\n{detail}"
