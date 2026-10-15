"""
FastAPI demo app for bedrock-fallback-engine.

Run locally:
    pip install -r demo/requirements.txt
    pip install -e .
    BEDROCK_DEMO_DRY_RUN=1 uvicorn demo.app:app --reload

Then:
    curl -i -X POST http://localhost:8000/triage \\
      -H 'content-type: application/json' \\
      -d '{"text": "My dashboard is broken"}'

Force failover:
    curl -i -X POST 'http://localhost:8000/triage?simulate_throttle=true' \\
      -H 'content-type: application/json' \\
      -d '{"text": "My dashboard is broken"}'
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from bedrock_fallback_engine import (
    BedrockFallbackEngine,
    BedrockRoute,
    BedrockRouteExhausted,
)
from bedrock_fallback_engine.metrics import CloudWatchMetricsEmitter
from demo.chaos import ChaosBedrockClient, active_failures, clear_failures, force_failure
from demo.schemas import HealthResponse, TriageRequest, TriageResponse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bedrock_demo")


# --------------------------------------------------------------------------- #
# Bedrock output schema
# --------------------------------------------------------------------------- #

class _TriageOutput(BaseModel):
    """Shape the LLM must return for this endpoint."""

    category: str = Field(..., description="Short label like 'bug', 'billing'.")
    urgency: str = Field(..., description="One of 'low', 'medium', 'high'.")
    suggested_action: str = Field(..., description="A short, actionable next step.")


# --------------------------------------------------------------------------- #
# Demo routes
# --------------------------------------------------------------------------- #

_DEMO_ROUTES: list[BedrockRoute] = [
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
        model_id="us.anthropic.claude-3-5-sonnet-20241022-v2:0",
        label="cross-region-profile",
    ),
    BedrockRoute(
        region="us-east-1",
        model_id="amazon.nova-pro-v1:0",
        label="cross-model-nova",
    ),
    BedrockRoute(
        region="us-east-1",
        model_id="amazon.titan-text-premier-v1:0",
        label="emergency-titan",
    ),
]


# --------------------------------------------------------------------------- #
# Engine setup
# --------------------------------------------------------------------------- #

def _build_engine() -> BedrockFallbackEngine:
    """
    Build the engine. Honors two env vars:

    - ``BEDROCK_DEMO_DRY_RUN=1`` — use canned responses, no AWS calls.
    - ``BEDROCK_DEMO_METRICS=1`` — emit CloudWatch metrics.
    """
    dry_run = os.environ.get("BEDROCK_DEMO_DRY_RUN") == "1"
    if dry_run:
        logger.info("DRY RUN: no AWS calls will be made")

    # Engine tells us only the region, so we look up the route label by region.
    def _factory(region: str) -> ChaosBedrockClient:
        for route in _DEMO_ROUTES:
            if route.region == region:
                return ChaosBedrockClient(
                    region=region,
                    route_label=route.label,
                    dry_run=dry_run,
                )
        return ChaosBedrockClient(
            region=region,
            route_label=f"unknown:{region}",
            dry_run=dry_run,
        )

    metrics = None
    if os.environ.get("BEDROCK_DEMO_METRICS") == "1":
        logger.info("CloudWatch metrics enabled")
        metrics = CloudWatchMetricsEmitter(
            namespace="BedrockFallback/Demo",
            flush_size=5,
        )

    return BedrockFallbackEngine(
        routes=_DEMO_ROUTES,
        schema=_TriageOutput,
        max_retries=1,
        cooldown=0.5,
        client_factory=_factory,  # type: ignore[arg-type]
        metrics=metrics,
    )


app = FastAPI(
    title="bedrock-fallback-engine demo",
    description="Live failover demo for Amazon Bedrock resilience.",
    version="0.2.0",
)

_engine = _build_engine()


# --------------------------------------------------------------------------- #
# Endpoints
# --------------------------------------------------------------------------- #

@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        version="0.2.0",
        routes=[r.label for r in _DEMO_ROUTES],
    )


@app.post("/triage", response_model=TriageResponse)
def triage(
    req: TriageRequest,
    response: Response,
    simulate_throttle: bool = Query(
        False,
        description="Force the primary route to fail so judges can see failover live.",
    ),
    clear_chaos: bool = Query(
        False,
        description="Reset the chaos set before handling this request.",
    ),
) -> TriageResponse:
    """Classify a support ticket via Bedrock with automatic cross-region failover."""
    if clear_chaos:
        clear_failures()

    if simulate_throttle:
        force_failure("primary")
        logger.warning("CHAOS: primary route forced to fail for this demo")

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "text": (
                        "Classify this support ticket and respond as JSON with keys "
                        "'category' (string), 'urgency' ('low'|'medium'|'high'), "
                        "and 'suggested_action' (string).\n\n"
                        f"Ticket: {req.text}"
                    )
                }
            ],
        }
    ]

    try:
        result = _engine.invoke(messages)
    except BedrockRouteExhausted as exc:
        logger.error("All routes exhausted: %s", exc)
        raise HTTPException(
            status_code=503,
            detail={
                "error": "all_bedrock_routes_exhausted",
                "routes_tried": [label for label, _ in exc.errors],
                "detail": str(exc),
            },
        ) from exc

    response.headers["X-Route-Served-By"] = result.route.label
    response.headers["X-Route-Region"] = result.route.region
    response.headers["X-Route-Model"] = result.route.model_id
    response.headers["X-Input-Tokens"] = str(result.input_tokens)
    response.headers["X-Output-Tokens"] = str(result.output_tokens)
    response.headers["X-Latency-Ms"] = f"{result.latency_ms:.2f}"
    response.headers["X-Attempts"] = str(result.attempts)

    return TriageResponse(
        category=result.value.get("category", "unknown"),
        urgency=result.value.get("urgency", "unknown"),
        suggested_action=result.value.get("suggested_action", ""),
        served_by_route=result.route.label,
        served_by_region=result.route.region,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        latency_ms=round(result.latency_ms, 2),
        attempts=result.attempts,
    )


@app.get("/chaos/status")
def chaos_status() -> dict[str, Any]:
    """Inspect which routes are currently forced to fail."""
    return {"forced_failures": active_failures()}


@app.post("/chaos/clear")
def chaos_clear() -> dict[str, str]:
    """Reset the chaos set."""
    clear_failures()
    return {"status": "cleared"}
