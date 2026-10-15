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
            ``"anthropic.claude-3-5-sonnet-20241022-v2:0"`` or a
            cross-region inference profile like
            ``"us.anthropic.claude-3-5-sonnet-20241022-v2:0"``.
        label: Human-readable name for logs and metrics. Auto-generated if empty.
    """

    region: str
    model_id: str
    label: str = ""

    def __post_init__(self) -> None:
        if not self.label:
            object.__setattr__(self, "label", f"{self.region}:{self.model_id}")


DEFAULT_ROUTES: tuple[BedrockRoute, ...] = (
    # Tier 1 — Primary: Claude 3.5 Sonnet in us-east-1
    BedrockRoute(
        region="us-east-1",
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        label="primary",
    ),
    # Tier 2 — Cross-region: same model, different AWS region
    BedrockRoute(
        region="us-west-2",
        model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
        label="cross-region",
    ),
    # Tier 3 — Cross-region inference profile: Bedrock auto-routes this across
    # multiple regions. This is an AWS-native resilience feature.
    BedrockRoute(
        region="us-east-1",
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        label="cross-region-profile",
    ),
    # Tier 4 — Cross-model: Nova Pro, a different model family
    BedrockRoute(
        region="us-east-1",
        model_id="amazon.nova-pro-v1:0",
        label="cross-model-nova",
    ),
    # Tier 5 — Emergency: Titan Text Premier, Bedrock's cheapest + most
    # available model. Almost never throttled.
    BedrockRoute(
        region="us-east-1",
        model_id="amazon.titan-text-premier-v1:0",
        label="emergency-titan",
    ),
)
