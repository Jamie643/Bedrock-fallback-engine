"""
bedrock-fallback-engine
=======================

AWS-native resilience for Amazon Bedrock: cross-region and cross-model
failover with schema validation and per-route telemetry.
"""

from bedrock_fallback_engine.client import BedrockClient
from bedrock_fallback_engine.engine import BedrockFallbackEngine, InvocationResult
from bedrock_fallback_engine.exceptions import (
    BedrockEngineError,
    BedrockRouteExhausted,
    BedrockThrottlingError,
    BedrockTransientError,
)
from bedrock_fallback_engine.regions import DEFAULT_ROUTES, BedrockRoute

__version__ = "0.1.0"

__all__ = [
    "BedrockClient",
    "BedrockFallbackEngine",
    "BedrockRoute",
    "DEFAULT_ROUTES",
    "InvocationResult",
    "BedrockEngineError",
    "BedrockRouteExhausted",
    "BedrockThrottlingError",
    "BedrockTransientError",
    "__version__",
]
