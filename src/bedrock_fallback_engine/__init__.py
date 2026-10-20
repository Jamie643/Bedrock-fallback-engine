"""
bedrock-fallback-engine
=======================

AWS-native resilience for Amazon Bedrock: cross-region and cross-model
failover with schema validation and per-route CloudWatch telemetry.

Also ships an MCP server so AI agents (including Alexa+ skills) can invoke
resilient Bedrock calls directly.
"""

from bedrock_fallback_engine.client import BedrockClient
from bedrock_fallback_engine.engine import BedrockFallbackEngine, InvocationResult
from bedrock_fallback_engine.exceptions import (
    BedrockEngineError,
    BedrockRouteExhausted,
    BedrockThrottlingError,
    BedrockTransientError,
)
from bedrock_fallback_engine.metrics import CloudWatchMetricsEmitter
from bedrock_fallback_engine.regions import DEFAULT_ROUTES, BedrockRoute

__version__ = "0.3.0"

__all__ = [
    "BedrockClient",
    "BedrockFallbackEngine",
    "BedrockRoute",
    "CloudWatchMetricsEmitter",
    "DEFAULT_ROUTES",
    "InvocationResult",
    "BedrockEngineError",
    "BedrockRouteExhausted",
    "BedrockThrottlingError",
    "BedrockTransientError",
    "__version__",
]
