"""
The MCP tools exposed by bedrock-fallback-engine.

Four tools:

- ``bedrock_resilient_call`` — resilient Bedrock call with automatic failover
- ``list_bedrock_routes`` — return the current route chain
- ``get_fallback_stats`` — session statistics
- ``health_check`` — verify AWS credentials and Bedrock access
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from bedrock_fallback_engine import (
    BedrockFallbackEngine,
    BedrockRouteExhausted,
)
from bedrock_fallback_engine.mcp.state import SESSION

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


# --------------------------------------------------------------------------- #
# Internal schema
# --------------------------------------------------------------------------- #

class _StructuredOutput(BaseModel):
    """Placeholder — actual schema built dynamically per request."""


# --------------------------------------------------------------------------- #
# Tool registration
# --------------------------------------------------------------------------- #

def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools on the given FastMCP instance."""

    @mcp.tool()  # type: ignore[untyped-decorator]
    def bedrock_resilient_call(
        prompt: str,
        max_retries: int = 2,
        cooldown: float = 1.0,
        schema_json: str = "",
    ) -> dict[str, Any]:
        """
        Make a resilient Amazon Bedrock call with cross-region, cross-model failover.

        This is the tool an AI agent (or Alexa+ skill) uses when it needs a
        Bedrock response but cannot afford a regional outage to interrupt the user.

        Args:
            prompt: The user-facing prompt to send to Bedrock.
            max_retries: Retries per route before moving to the next route.
            cooldown: Seconds between retries on the same route.
            schema_json: Optional JSON-encoded schema for structured output.

        Returns:
            Dict with `status`, `text` or `structured`, `served_by`, and `stats`.
        """
        routes = SESSION.get_routes()
        if not routes:
            return {
                "status": "error",
                "message": "No routes configured. Call list_bedrock_routes to inspect defaults.",
            }

        schema_model: type[BaseModel] | None = None
        if schema_json:
            try:
                schema_dict = json.loads(schema_json)
                schema_model = _make_dynamic_model(schema_dict)
            except (json.JSONDecodeError, ValueError) as exc:
                return {
                    "status": "error",
                    "message": f"invalid schema_json: {exc}",
                }

        SESSION.stats.total_calls += 1

        engine = BedrockFallbackEngine(
            routes=routes,
            schema=schema_model,
            max_retries=max_retries,
            cooldown=cooldown,
        )

        messages = [
            {
                "role": "user",
                "content": [{"text": prompt}],
            }
        ]

        try:
            result = engine.invoke(messages)
        except BedrockRouteExhausted as exc:
            for label, _ in exc.errors:
                SESSION.stats.record_failure(label)
            return {
                "status": "error",
                "message": "All Bedrock routes exhausted",
                "routes_tried": [label for label, _ in exc.errors],
                "captured_errors": [str(e) for _, e in exc.errors],
                "stats": SESSION.stats.to_dict(),
            }

        # Record success statistics.
        SESSION.stats.record_attempt(result.route.label)
        SESSION.stats.record_success(
            result.route.label,
            result.input_tokens,
            result.output_tokens,
        )
        if result.attempts > 1:
            SESSION.stats.failovers += 1

        response: dict[str, Any] = {
            "status": "ok",
            "served_by": {
                "label": result.route.label,
                "region": result.route.region,
                "model": result.route.model_id,
            },
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "latency_ms": round(result.latency_ms, 2),
            "attempts": result.attempts,
            "stats": SESSION.stats.to_dict(),
        }

        if schema_model is not None:
            response["structured"] = result.value
        else:
            response["text"] = result.value.get("text", "")

        return response

    @mcp.tool()  # type: ignore[untyped-decorator]
    def list_bedrock_routes() -> dict[str, Any]:
        """
        List the current Bedrock route chain in fallback order.

        Returns the ordered list of (region, model) pairs that will be tried
        when a call is made.
        """
        routes = SESSION.get_routes()
        return {
            "status": "ok",
            "route_count": len(routes),
            "routes": [
                {
                    "label": r.label,
                    "region": r.region,
                    "model": r.model_id,
                }
                for r in routes
            ],
        }

    @mcp.tool()  # type: ignore[untyped-decorator]
    def get_fallback_stats() -> dict[str, Any]:
        """
        Return accumulated statistics for the current MCP server session.

        Includes total calls, successes, failures, failover count,
        token usage, and per-route breakdowns.
        """
        return SESSION.stats.to_dict()

    @mcp.tool()  # type: ignore[untyped-decorator]
    def health_check() -> dict[str, Any]:
        """
        Verify AWS credentials are configured and Bedrock is reachable.

        Returns credentials status, current region, and the route count.
        Does not make a real Bedrock call — fast and free.
        """
        import os

        has_key = bool(
            os.environ.get("AWS_ACCESS_KEY_ID")
            or os.environ.get("AWS_PROFILE")
        )
        region = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        routes = SESSION.get_routes()

        return {
            "status": "ok" if has_key else "warning",
            "credentials_configured": has_key,
            "default_region": region,
            "route_count": len(routes),
            "message": (
                "AWS credentials detected — ready to call Bedrock."
                if has_key
                else "No AWS credentials found. Set AWS_ACCESS_KEY_ID or AWS_PROFILE."
            ),
        }


# --------------------------------------------------------------------------- #
# Dynamic schema builder (shared pattern with agent-fallback-sentinel)
# --------------------------------------------------------------------------- #

def _make_dynamic_model(schema_dict: dict[str, Any]) -> type[BaseModel]:
    """
    Build a Pydantic model from a JSON-schema-like dict using create_model.
    """
    from pydantic import create_model

    if schema_dict.get("type") != "object":
        raise ValueError("only 'object' schemas are supported")

    properties = schema_dict.get("properties")
    if not isinstance(properties, dict) or not properties:
        raise ValueError("schema must have a non-empty 'properties' object")

    required = set(schema_dict.get("required", []))

    type_map: dict[str, type] = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
    }

    fields: dict[str, Any] = {}
    for field_name, spec in properties.items():
        if not isinstance(spec, dict):
            raise ValueError(f"property '{field_name}' must be an object")
        type_name = spec.get("type")
        if type_name not in type_map:
            raise ValueError(
                f"property '{field_name}' has unsupported type '{type_name}'"
            )
        if field_name in required:
            fields[field_name] = (type_map[type_name], ...)
        else:
            fields[field_name] = (type_map[type_name] | None, None)

    model = create_model("DynamicModel", **fields)
    return model
