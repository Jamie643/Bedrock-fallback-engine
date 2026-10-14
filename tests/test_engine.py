"""Tests for BedrockFallbackEngine with a fake Bedrock client."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from botocore.exceptions import ClientError
from pydantic import BaseModel

from bedrock_fallback_engine import (
    BedrockFallbackEngine,
    BedrockRoute,
    BedrockRouteExhausted,
)


# --------------------------------------------------------------------------- #
# Test schema
# --------------------------------------------------------------------------- #

class OutputSchema(BaseModel):
    status: str
    action: str


# --------------------------------------------------------------------------- #
# Fake Bedrock client helpers
# --------------------------------------------------------------------------- #

def _converse_response(text: str) -> dict[str, Any]:
    """Return a response shaped like the Bedrock Converse API."""
    return {"output": {"message": {"content": [{"text": text}]}}}


def _throttled_error() -> ClientError:
    return ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "429"}},
        "converse",
    )


class _FakeBedrockRuntimeClient:
    """Stand-in for boto3.client('bedrock-runtime', region_name=...)."""

    def __init__(self, behaviors: dict[str, Any]) -> None:
        self._behaviors = behaviors

    def converse(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        model_id = kwargs.get("modelId") or args[0]
        behavior = self._behaviors[model_id]
        if isinstance(behavior, Exception):
            raise behavior
        return behavior


def _install_fake_boto3(monkeypatch: pytest.MonkeyPatch, behaviors: dict[str, Any]) -> None:
    """Patch bedrock_fallback_engine.client.boto3 with a fake that returns our client."""

    def fake_client(service: str, region_name: str) -> _FakeBedrockRuntimeClient:
        return _FakeBedrockRuntimeClient(behaviors)

    fake_boto3 = SimpleNamespace(client=fake_client)
    monkeypatch.setattr("bedrock_fallback_engine.client.boto3", fake_boto3)


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_primary_route_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    behaviors = {
        "claude-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    _install_fake_boto3(monkeypatch, behaviors)

    routes = [BedrockRoute(region="us-east-1", model_id="claude-model")]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out == {"status": "ok", "action": "run"}


# --------------------------------------------------------------------------- #
# Failover
# --------------------------------------------------------------------------- #

def test_fails_over_to_second_route(monkeypatch: pytest.MonkeyPatch) -> None:
    behaviors = {
        "claude-model": _throttled_error(),
        "nova-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    _install_fake_boto3(monkeypatch, behaviors)

    routes = [
        BedrockRoute(region="us-east-1", model_id="claude-model"),
        BedrockRoute(region="us-west-2", model_id="nova-model"),
    ]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out["status"] == "ok"


def test_all_routes_fail_raises_route_exhausted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    behaviors = {
        "claude-model": _throttled_error(),
        "nova-model": _throttled_error(),
    }
    _install_fake_boto3(monkeypatch, behaviors)

    routes = [
        BedrockRoute(region="us-east-1", model_id="claude-model"),
        BedrockRoute(region="us-west-2", model_id="nova-model"),
    ]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    with pytest.raises(BedrockRouteExhausted) as excinfo:
        engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    assert len(excinfo.value.errors) == 2


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #

def test_invalid_json_triggers_failover(monkeypatch: pytest.MonkeyPatch) -> None:
    behaviors = {
        "claude-model": _converse_response("not json at all"),
        "nova-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    _install_fake_boto3(monkeypatch, behaviors)

    routes = [
        BedrockRoute(region="us-east-1", model_id="claude-model"),
        BedrockRoute(region="us-west-2", model_id="nova-model"),
    ]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out["status"] == "ok"


def test_schema_valid_but_missing_field_triggers_failover(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    behaviors = {
        "claude-model": _converse_response(json.dumps({"status": "ok"})),
        "nova-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    _install_fake_boto3(monkeypatch, behaviors)

    routes = [
        BedrockRoute(region="us-east-1", model_id="claude-model"),
        BedrockRoute(region="us-west-2", model_id="nova-model"),
    ]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out["action"] == "run"


# --------------------------------------------------------------------------- #
# No schema
# --------------------------------------------------------------------------- #

def test_no_schema_returns_text_dict(monkeypatch: pytest.MonkeyPatch) -> None:
    behaviors = {"claude-model": _converse_response("hello world")}
    _install_fake_boto3(monkeypatch, behaviors)

    routes = [BedrockRoute(region="us-east-1", model_id="claude-model")]
    engine = BedrockFallbackEngine(routes=routes, schema=None)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out == {"text": "hello world"}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def test_engine_requires_at_least_one_route() -> None:
    with pytest.raises(ValueError):
        BedrockFallbackEngine(routes=[])


def test_engine_emits_route_events(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    behaviors = {
        "claude-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    _install_fake_boto3(monkeypatch, behaviors)

    routes = [BedrockRoute(region="us-east-1", model_id="claude-model")]
    engine = BedrockFallbackEngine(
        routes=routes,
        schema=OutputSchema,
        on_event=lambda name, payload: events.append((name, payload)),
    )

    engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])

    event_names = [e[0] for e in events]
    assert "route_attempt" in event_names
    assert "route_success" in event_names
