"""
The fallback engine. Iterates routes, retries within a route, fails over
between routes, validates schema, and reports per-route telemetry.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from bedrock_fallback_engine.client import BedrockClient, ConverseResult
from bedrock_fallback_engine.exceptions import BedrockRouteExhausted
from bedrock_fallback_engine.regions import DEFAULT_ROUTES, BedrockRoute

logger = logging.getLogger("bedrock_fallback_engine")


@dataclass
class InvocationResult:
    """
    Result of a successful engine invocation.

    Attributes:
        value: Either the validated schema dump, or ``{"text": ...}``.
        route: The route that succeeded.
        input_tokens: Tokens consumed by the prompt on the winning route.
        output_tokens: Tokens generated on the winning route.
        attempts: Number of attempts made across all routes before success.
    """

    value: dict[str, Any]
    route: BedrockRoute
    input_tokens: int
    output_tokens: int
    attempts: int


@dataclass
class _RouteState:
    """Internal per-route attempt tracking."""

    errors: list[tuple[str, Exception]] = field(default_factory=list)
    total_attempts: int = 0


class BedrockFallbackEngine:
    """
    Cross-region, cross-model failover for Amazon Bedrock.

    Args:
        routes: Ordered list of routes to try. Defaults to ``DEFAULT_ROUTES``.
        max_retries: Retries **within a single route** before moving on.
        cooldown: Seconds between retries on the same route.
        schema: Optional Pydantic model to validate the model's JSON output.
        sleep_fn: Injectable sleep function. Pass ``lambda _: None`` in tests.
        client_factory: Optional factory for ``BedrockClient``. Defaults to
            ``lambda region: BedrockClient(region=region)``.
        on_event: Optional observability hook. Events emitted:
            ``route_attempt``, ``route_retry``, ``route_failure``,
            ``route_success``, ``routes_exhausted``.
    """

    def __init__(
        self,
        routes: Iterable[BedrockRoute] | None = None,
        max_retries: int = 2,
        cooldown: float = 1.0,
        schema: type[BaseModel] | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
        client_factory: Callable[[str], BedrockClient] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> None:
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0")
        if cooldown < 0:
            raise ValueError("cooldown must be >= 0")

        self.routes: tuple[BedrockRoute, ...] = tuple(routes or DEFAULT_ROUTES)
        if not self.routes:
            raise ValueError("at least one route is required")

        self.max_retries = max_retries
        self.cooldown = cooldown
        self.schema = schema
        self._sleep = sleep_fn
        self._client_factory = client_factory or (lambda region: BedrockClient(region=region))
        self._on_event = on_event

    # ------------------------------------------------------------------ #
    # Observability
    # ------------------------------------------------------------------ #

    def _emit(self, event: str, payload: dict[str, Any]) -> None:
        if self._on_event is not None:
            try:
                self._on_event(event, payload)
            except Exception:  # noqa: BLE001
                logger.exception("on_event callback raised; ignoring")

    # ------------------------------------------------------------------ #
    # Route execution
    # ------------------------------------------------------------------ #

    def _attempt_route(
        self,
        route: BedrockRoute,
        messages: list[dict[str, Any]],
        converse_kwargs: dict[str, Any],
        state: _RouteState,
    ) -> ConverseResult | None:
        """
        Try a single route up to ``max_retries + 1`` times.

        Returns ``ConverseResult`` on success, or ``None`` if the route failed
        every attempt (errors are appended to ``state.errors``).
        """
        last_exc: Exception | None = None

        for attempt in range(1, self.max_retries + 2):
            state.total_attempts += 1
            self._emit(
                "route_attempt",
                {"route": route.label, "attempt": attempt, "region": route.region},
            )

            try:
                client = self._client_factory(route.region)
                return client.converse(route.model_id, messages, **converse_kwargs)
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "route %s attempt %d/%d failed: %s",
                    route.label,
                    attempt,
                    self.max_retries + 1,
                    exc,
                )
                if attempt <= self.max_retries:
                    self._emit("route_retry", {"route": route.label, "attempt": attempt})
                    self._sleep(self.cooldown)

        if last_exc is not None:
            state.errors.append((route.label, last_exc))
            self._emit(
                "route_failure",
                {"route": route.label, "error": str(last_exc)},
            )
        return None

    def _validate(
        self,
        result: ConverseResult,
        route: BedrockRoute,
        state: _RouteState,
    ) -> dict[str, Any] | None:
        """
        Validate against schema. Returns dumped dict on success, or ``None``
        on validation failure (error appended to ``state.errors``).
        """
        if self.schema is None:
            return {"text": result.text}

        try:
            parsed = json.loads(result.text)
            return self.schema.model_validate(parsed).model_dump()
        except Exception as exc:  # noqa: BLE001
            logger.warning("route %s schema validation failed: %s", route.label, exc)
            state.errors.append((route.label, exc))
            self._emit("route_failure", {"route": route.label, "error": str(exc)})
            return None

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def invoke(
        self,
        messages: list[dict[str, Any]],
        **converse_kwargs: Any,
    ) -> InvocationResult:
        """
        Invoke Bedrock with automatic cross-region / cross-model failover.

        Raises:
            BedrockRouteExhausted: If every route fails.
        """
        state = _RouteState()

        for route in self.routes:
            logger.info("trying route %s (%s)", route.label, route.region)
            result = self._attempt_route(route, messages, converse_kwargs, state)
            if result is None:
                continue

            value = self._validate(result, route, state)
            if value is None:
                continue

            self._emit(
                "route_success",
                {
                    "route": route.label,
                    "region": route.region,
                    "input_tokens": result.input_tokens,
                    "output_tokens": result.output_tokens,
                    "attempts": state.total_attempts,
                },
            )

            return InvocationResult(
                value=value,
                route=route,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                attempts=state.total_attempts,
            )

        self._emit(
            "routes_exhausted",
            {"total_attempts": state.total_attempts, "route_count": len(self.routes)},
        )
        raise BedrockRouteExhausted(
            f"All {len(self.routes)} Bedrock routes failed after "
            f"{state.total_attempts} attempt(s).",
            errors=state.errors,
        )
