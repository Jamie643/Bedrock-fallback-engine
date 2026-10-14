"""
The fallback engine itself. Wires BedrockRoute definitions, BedrockClient,
and agent-fallback-sentinel together.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Iterable, Optional

from agent_fallback_sentinel import AgentSentinel, SentinelCircuitBreaker
from pydantic import BaseModel

from bedrock_fallback_engine.client import BedrockClient
from bedrock_fallback_engine.exceptions import (
    BedrockEngineError,
    BedrockRouteExhausted,
)
from bedrock_fallback_engine.regions import BedrockRoute, DEFAULT_ROUTES

logger = logging.getLogger("bedrock_fallback_engine")


class BedrockFallbackEngine:
    """
    Cross-region, cross-model failover for Amazon Bedrock.

    Tries each route in order. On failure, moves to the next. Uses
    ``AgentSentinel`` internally for retries and schema validation.

    Args:
        routes: Ordered list of routes to try. Defaults to ``DEFAULT_ROUTES``.
        max_retries: Retries per route before moving on.
        cooldown: Seconds between retries on a single route.
        schema: Optional Pydantic model to validate the extracted text.
        on_event: Optional observability hook forwarded to AgentSentinel.
    """

    def __init__(
        self,
        routes: Iterable[BedrockRoute] | None = None,
        max_retries: int = 2,
        cooldown: float = 1.0,
        schema: type[BaseModel] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        self.routes: tuple[BedrockRoute, ...] = tuple(routes or DEFAULT_ROUTES)
        if not self.routes:
            raise ValueError("at least one route is required")

        self.schema = schema
        self._sentinel = AgentSentinel(
            max_retries=max_retries,
            cooldown=cooldown,
            fallback_max_retries=0,  # engine handles failover itself
            on_event=on_event,
        )
        self._on_event = on_event

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._on_event is not None:
            try:
                self._on_event(event, payload)
            except Exception:  # noqa: BLE001
                logger.exception("on_event callback raised; ignoring")

    def _call_route(
        self,
        route: BedrockRoute,
        messages: list[dict[str, Any]],
        **converse_kwargs: Any,
    ) -> str:
        client = BedrockClient(region=route.region)
        response = client.converse(route.model_id, messages, **converse_kwargs)
        return BedrockClient.extract_text(response)

    def invoke(
        self,
        messages: list[dict[str, Any]],
        **converse_kwargs: Any,
    ) -> dict[str, Any]:
        """
        Invoke Bedrock with automatic cross-region / cross-model failover.

        Returns a dict. If ``schema`` was provided, the dict is the validated
        and dumped schema. Otherwise it is ``{"text": <model output>}``.

        Raises:
            BedrockRouteExhausted: If every route fails.
        """
        route_errors: list[tuple[str, Exception]] = []

        for route in self.routes:
            self._emit("route_attempt", {"route": route.label, "region": route.region})
            logger.info("trying route %s (%s)", route.label, route.region)

            try:
                text = self._call_route(route, messages, **converse_kwargs)
            except Exception as exc:  # noqa: BLE001
                logger.warning("route %s failed: %s", route.label, exc)
                route_errors.append((route.label, exc))
                self._emit("route_failure", {"route": route.label, "error": str(exc)})
                continue

            # Validate with sentinel schema if provided
            if self.schema is not None:
                try:
                    import json

                    parsed = json.loads(text)
                    validated = self.schema.model_validate(parsed).model_dump()
                except Exception as exc:  # noqa: BLE001
                    logger.warning("route %s produced invalid schema: %s", route.label, exc)
                    route_errors.append((route.label, exc))
                    self._emit("route_failure", {"route": route.label, "error": str(exc)})
                    continue
                self._emit("route_success", {"route": route.label, "validated": True})
                return validated

            self._emit("route_success", {"route": route.label, "validated": False})
            return {"text": text}

        raise BedrockRouteExhausted(
            f"All {len(self.routes)} Bedrock routes failed.",
            errors=route_errors,
        )
