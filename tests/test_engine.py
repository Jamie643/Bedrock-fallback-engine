"""Tests for BedrockFallbackEngine."""

from __future__ import annotations

import json
from typing import Any

import pytest
from botocore.exceptions import ClientError
from pydantic import BaseModel

from bedrock_fallback_engine import (
    BedrockFallbackEngine,
    BedrockRoute,
    BedrockRouteExhausted,
)
from bedrock_fallback_engine.client import ConverseResult


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

class OutputSchema(BaseModel):
    status: str
    action: str


def _ok(text: str, in_tokens: int = 1, out_tokens: int = 1) -> ConverseResult:
    return ConverseResult(text=text, input_tokens=in_tokens, output_tokens=out_tokens)


def _throttled() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "429"}},
        "converse",
    )


def _engine_with(
    behaviors: dict[str, Any],
    routes: list[BedrockRoute],
    **engine_kwargs: Any,
) -> BedrockFallbackEngine:
    """Build an engine whose client factory returns canned behaviors per model_id."""

    class _Stub:
        def __init__(self, model_behaviors: dict[str, Any]) -> None:
            self._b = model_behaviors

        def converse(
            self,
            model_id: str,
            messages: list[dict[str, Any]],
            **kwargs: Any,
        ) -> ConverseResult:
            behavior = self._b[model_id]
            if isinstance(behavior, Exception):
                raise behavior
            return behavior

    return BedrockFallbackEngine(
        routes=routes,
        sleep_fn=lambda _: None,
        client_factory=lambda region: _Stub(behaviors),  # type: ignore[arg-type]
        **engine_kwargs,
    )


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_primary_route_succeeds() -> None:
    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _ok(json.dumps({"status": "ok", "action": "run"}), 10, 20)},
        routes,
        schema=OutputSchema,
    )

    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.value == {"status": "ok", "action": "run"}
    assert result.route.label == "us-east-1:m1"
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    assert result.attempts == 1


# --------------------------------------------------------------------------- #
# Failover
# --------------------------------------------------------------------------- #

def test_fails_over_on_throttling() -> None:
    routes = [
        BedrockRoute(region="us-east-1", model_id="m1"),
        BedrockRoute(region="us-west-2", model_id="m2"),
    ]
    engine = _engine_with(
        {
            "m1": _throttled(),
            "m2": _ok(json.dumps({"status": "ok", "action": "run"})),
        },
        routes,
        schema=OutputSchema,
        max_retries=0,
    )

    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.route.label == "us-west-2:m2"
    assert result.attempts == 2


def test_retries_within_route_before_failover() -> None:
    routes = [
        BedrockRoute(region="us-east-1", model_id="m1"),
        BedrockRoute(region="us-west-2", model_id="m2"),
    ]
    engine = _engine_with(
        {
            "m1": _throttled(),
            "m2": _ok(json.dumps({"status": "ok", "action": "run"})),
        },
        routes,
        schema=OutputSchema,
        max_retries=2,
    )

    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    # m1 tried 3 times, m2 once = 4 total
    assert result.attempts == 4


def test_all_routes_fail_raises_with_structured_errors() -> None:
    routes = [
        BedrockRoute(region="us-east-1", model_id="m1"),
        BedrockRoute(region="us-west-2", model_id="m2"),
    ]
    engine = _engine_with(
        {"m1": _throttled(), "m2": _throttled()},
        routes,
        schema=OutputSchema,
        max_retries=0,
    )

    with pytest.raises(BedrockRouteExhausted) as excinfo:
        engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    labels = [label for label, _ in excinfo.value.errors]
    assert labels == ["us-east-1:m1", "us-west-2:m2"]


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #

def test_invalid_json_fails_over() -> None:
    routes = [
        BedrockRoute(region="us-east-1", model_id="m1"),
        BedrockRoute(region="us-west-2", model_id="m2"),
    ]
    engine = _engine_with(
        {
            "m1": _ok("not json"),
            "m2": _ok(json.dumps({"status": "ok", "action": "run"})),
        },
        routes,
        schema=OutputSchema,
        max_retries=0,
    )

    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.value["status"] == "ok"


def test_valid_json_but_missing_field_fails_over() -> None:
    routes = [
        BedrockRoute(region="us-east-1", model_id="m1"),
        BedrockRoute(region="us-west-2", model_id="m2"),
    ]
    engine = _engine_with(
        {
            "m1": _ok(json.dumps({"status": "ok"})),  # missing 'action'
            "m2": _ok(json.dumps({"status": "ok", "action": "run"})),
        },
        routes,
        schema=OutputSchema,
        max_retries=0,
    )

    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.value["action"] == "run"


# --------------------------------------------------------------------------- #
# No schema
# --------------------------------------------------------------------------- #

def test_no_schema_returns_text_dict() -> None:
    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with({"m1": _ok("hello world")}, routes, schema=None)

    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.value == {"text": "hello world"}


# --------------------------------------------------------------------------- #
# Config validation
# --------------------------------------------------------------------------- #

def test_empty_routes_rejected() -> None:
    with pytest.raises(ValueError):
        BedrockFallbackEngine(routes=[])


def test_negative_max_retries_rejected() -> None:
    with pytest.raises(ValueError):
        BedrockFallbackEngine(max_retries=-1)


def test_negative_cooldown_rejected() -> None:
    with pytest.raises(ValueError):
        BedrockFallbackEngine(cooldown=-0.1)


# --------------------------------------------------------------------------- #
# Observability
# --------------------------------------------------------------------------- #

def test_events_emitted_on_success() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _ok(json.dumps({"status": "ok", "action": "run"}))},
        routes,
        schema=OutputSchema,
        on_event=lambda name, payload: events.append((name, payload)),
    )

    engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    names = [name for name, _ in events]
    assert names == ["route_attempt", "route_success"]


def test_events_emitted_on_failover() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    routes = [
        BedrockRoute(region="us-east-1", model_id="m1"),
        BedrockRoute(region="us-west-2", model_id="m2"),
    ]
    engine = _engine_with(
        {
            "m1": _throttled(),
            "m2": _ok(json.dumps({"status": "ok", "action": "run"})),
        },
        routes,
        schema=OutputSchema,
        max_retries=0,
        on_event=lambda name, payload: events.append((name, payload)),
    )

    engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    names = [name for name, _ in events]
    assert "route_attempt" in names
    assert "route_failure" in names
    assert "route_success" in names


def test_routes_exhausted_event_emitted() -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _throttled()},
        routes,
        schema=OutputSchema,
        max_retries=0,
        on_event=lambda name, payload: events.append((name, payload)),
    )

    with pytest.raises(BedrockRouteExhausted):
        engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    names = [name for name, _ in events]
    assert "routes_exhausted" in names


def test_broken_on_event_handler_does_not_break_pipeline() -> None:
    def bad_handler(_name: str, _payload: dict[str, Any]) -> None:
        raise RuntimeError("telemetry broken")

    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _ok(json.dumps({"status": "ok", "action": "run"}))},
        routes,
        schema=OutputSchema,
        on_event=bad_handler,
    )

    # Should not raise
    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.value["status"] == "ok"

# --------------------------------------------------------------------------- #
# Metrics emission
# --------------------------------------------------------------------------- #

def test_metrics_emitted_on_success() -> None:
    from bedrock_fallback_engine.metrics import CloudWatchMetricsEmitter

    captured: list[tuple[str, float, dict[str, str]]] = []

    class _Capture(CloudWatchMetricsEmitter):
        def emit(
            self,
            name: str,
            value: float,
            unit: str = "Count",
            dimensions: dict[str, str] | None = None,
        ) -> None:
            captured.append((name, value, dict(dimensions or {})))

    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _ok(json.dumps({"status": "ok", "action": "run"}), 5, 7)},
        routes,
        schema=OutputSchema,
        metrics=_Capture(),
    )

    engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    names = [name for name, _, _ in captured]
    assert "InvocationCount" in names
    assert "InvocationLatency" in names
    assert "InputTokens" in names
    assert "OutputTokens" in names


def test_metrics_emitted_on_failover() -> None:
    from bedrock_fallback_engine.metrics import CloudWatchMetricsEmitter

    captured: list[str] = []

    class _Capture(CloudWatchMetricsEmitter):
        def emit(self, name, value, unit="Count", dimensions=None) -> None:  # type: ignore[no-untyped-def]
            captured.append(name)

    routes = [
        BedrockRoute(region="us-east-1", model_id="m1"),
        BedrockRoute(region="us-west-2", model_id="m2"),
    ]
    engine = _engine_with(
        {
            "m1": _throttled(),
            "m2": _ok(json.dumps({"status": "ok", "action": "run"})),
        },
        routes,
        schema=OutputSchema,
        max_retries=0,
        metrics=_Capture(),
    )

    engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    assert "ThrottleCount" in captured
    assert "FallbackTriggered" in captured


def test_metrics_emitted_on_exhaustion() -> None:
    from bedrock_fallback_engine.metrics import CloudWatchMetricsEmitter

    captured: list[str] = []

    class _Capture(CloudWatchMetricsEmitter):
        def emit(self, name, value, unit="Count", dimensions=None) -> None:  # type: ignore[no-untyped-def]
            captured.append(name)

    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _throttled()},
        routes,
        schema=OutputSchema,
        max_retries=0,
        metrics=_Capture(),
    )

    with pytest.raises(BedrockRouteExhausted):
        engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    assert "RouteExhausted" in captured


def test_broken_metrics_do_not_break_pipeline() -> None:
    from bedrock_fallback_engine.metrics import CloudWatchMetricsEmitter

    class _Broken(CloudWatchMetricsEmitter):
        def emit(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
            raise RuntimeError("metrics down")

    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _ok(json.dumps({"status": "ok", "action": "run"}))},
        routes,
        schema=OutputSchema,
        metrics=_Broken(),
    )

    # Should not raise
    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.value["status"] == "ok"


def test_invocation_result_includes_latency() -> None:
    routes = [BedrockRoute(region="us-east-1", model_id="m1")]
    engine = _engine_with(
        {"m1": _ok(json.dumps({"status": "ok", "action": "run"}))},
        routes,
        schema=OutputSchema,
    )

    result = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert result.latency_ms >= 0
