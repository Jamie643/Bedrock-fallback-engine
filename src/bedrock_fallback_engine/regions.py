"""
Route definitions for Bedrock fallback.

A route is a ``(region, model_id)`` pair. The engine tries routes in order.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BedrockRoute:
    """
    A single Bedrock invocation target.

    Attributes:
        region: AWS region name, e.g. ``"us-east-1"``.
        model_id: Bedrock model identifier, e.g.
            ``"anthropic.claude-3-5-sonnet-20241022-v2:0"``.
        label: Human-readable name for logs and metrics. Auto-generated if empty.
    """

    region: str
    model_id: str
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            object.__setattr__(self, "label", f"{self.region}:{self.model_id}")


DEFAULT_ROUTES: tuple[BedrockRoute, ...] = (
    BedrockRoute(
        region="us-east-1",
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        label="primary",
    ),
    BedrockRoute(
        region="us-west-2",
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        label="cross-region",
    ),
    BedrockRoute(
        region="us-east-1",
        model_id="amazon.nova-pro-v1:0",
        label="cross-model",
    ),
    BedrockRoute(
        region="us-west-2",
        model_id="meta.llama3-70b-instruct-v1:0",
        label="cross-provider",
    ),
)
