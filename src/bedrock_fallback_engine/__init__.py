"""
bedrock-fallback-engine
=======================

AWS-native resilience layer for Amazon Bedrock: cross-region and cross-model
failover with schema validation, built on agent-fallback-sentinel.
"""

from bedrock_fallback_engine.client import BedrockClient
from bedrock_fallback_engine.engine import BedrockFallbackEngine
from bedrock_fallback_engine.exceptions import (
    BedrockEngineError,
    BedrockRouteExhausted,
)
from bedrock_fallback_engine.regions import BedrockRoute, DEFAULT_ROUTES

__version__ = "0.1.0"

__all__ = [
    "BedrockClient",
    "BedrockFallbackEngine",
    "BedrockRoute",
    "DEFAULT_ROUTES",
    "BedrockEngineError",
    "BedrockRouteExhausted",
    "__version__",
]
