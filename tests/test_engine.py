"""Tests for BedrockFallbackEngine with a fake Bedrock client."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from bedrock_fallback_engine import (
    BedrockFallbackEngine,
    BedrockRoute,
    BedrockRouteExhausted,
)


# --------------------------------------------------------------------------- #
# Fixtures & helpers
# --------------------------------------------------------------------------- #

class OutputSchema(BaseModel):
    status: str
    action: str


def _converse_response(text: str) -> dict:
    """Shape the Converse API returns."""
    return {"output": {"message": {"content": [{"text": text}]}}}


def _fake_client_factory(behaviors: dict[str, dict | Exception]):
    """
    behaviors maps model_id -> (response dict OR Exception to raise).
    Returns a factory that BedrockClient will use instead of boto3.
    """

    class FakeClient:
        def converse(self, modelId, messages, **kwargs):
            behavior = behaviors[modelId]
            if isinstance(behavior, Exception):
                raise behavior
            return behavior

    return lambda region: FakeClient()


# --------------------------------------------------------------------------- #
# Happy path
# --------------------------------------------------------------------------- #

def test_primary_route_succeeds(monkeypatch):
    behaviors = {
        "claude-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    monkeypatch.setattr(
        "bedrock_fallback_engine.client.boto3",
        type("M", (), {"client": lambda *a, **k: _fake_client_factory(behaviors)(k["region_name"])}),
    )

    routes = [BedrockRoute(region="us-east-1", model_id="claude-model")]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out == {"status": "ok", "action": "run"}


# --------------------------------------------------------------------------- #
# Failover
# --------------------------------------------------------------------------- #

def test_fails_over_to_second_route(monkeypatch):
    from botocore.exceptions import ClientError

    throttled = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "429"}}, "converse"
    )

    behaviors = {
        "claude-model": throttled,
        "nova-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    monkeypatch.setattr(
        "bedrock_fallback_engine.client.boto3",
        type("M", (), {"client": lambda *a, **k: _fake_client_factory(behaviors)(k["region_name"])}),
    )

    routes = [
        BedrockRoute(region="us-east-1", model_id="claude-model"),
        BedrockRoute(region="us-west-2", model_id="nova-model"),
    ]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out["status"] == "ok"


def test_all_routes_fail_raises_route_exhausted(monkeypatch):
    from botocore.exceptions import ClientError

    throttled = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "429"}}, "converse"
    )
    behaviors = {
        "claude-model": throttled,
        "nova-model": throttled,
    }
    monkeypatch.setattr(
        "bedrock_fallback_engine.client.boto3",
        type("M", (), {"client": lambda *a, **k: _fake_client_factory(behaviors)(k["region_name"])}),
    )

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

def test_invalid_json_triggers_failover(monkeypatch):
    behaviors = {
        "claude-model": _converse_response("not json at all"),
        "nova-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    monkeypatch.setattr(
        "bedrock_fallback_engine.client.boto3",
        type("M", (), {"client": lambda *a, **k: _fake_client_factory(behaviors)(k["region_name"])}),
    )

    routes = [
        BedrockRoute(region="us-east-1", model_id="claude-model"),
        BedrockRoute(region="us-west-2", model_id="nova-model"),
    ]
    engine = BedrockFallbackEngine(routes=routes, schema=OutputSchema)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out["status"] == "ok"


# --------------------------------------------------------------------------- #
# No schema
# --------------------------------------------------------------------------- #

def test_no_schema_returns_text_dict(monkeypatch):
    behaviors = {"claude-model": _converse_response("hello world")}
    monkeypatch.setattr(
        "bedrock_fallback_engine.client.boto3",
        type("M", (), {"client": lambda *a, **k: _fake_client_factory(behaviors)(k["region_name"])}),
    )

    routes = [BedrockRoute(region="us-east-1", model_id="claude-model")]
    engine = BedrockFallbackEngine(routes=routes, schema=None)

    out = engine.invoke([{"role": "user", "content": [{"text": "hi"}]}])
    assert out == {"text": "hello world"}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def test_engine_requires_at_least_one_route():
    with pytest.raises(ValueError):
        BedrockFallbackEngine(routes=[])


def test_engine_emits_route_events(monkeypatch):
    events: list[tuple[str, dict]] = []
    behaviors = {
        "claude-model": _converse_response('{"status": "ok", "action": "run"}'),
    }
    monkeypatch.setattr(
        "bedrock_fallback_engine.client.boto3",
        type("M", (), {"client": lambda *a, **k: _fake_client_factory(behaviors)(k["region_name"])}),
    )

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
