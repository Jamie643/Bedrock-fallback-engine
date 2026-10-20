"""Tests for the Bedrock MCP tools — no real AWS calls."""

from __future__ import annotations

from typing import Any

import pytest

from bedrock_fallback_engine.mcp.state import SESSION
from bedrock_fallback_engine.mcp.tools import _make_dynamic_model


@pytest.fixture(autouse=True)
def _reset_session() -> Any:
    SESSION.reset_to_defaults()
    SESSION.reset_stats()
    yield
    SESSION.reset_to_defaults()
    SESSION.reset_stats()


def test_make_dynamic_model_valid() -> None:
    schema = {
        "type": "object",
        "properties": {"region": {"type": "string"}, "count": {"type": "integer"}},
        "required": ["region"],
    }
    model = _make_dynamic_model(schema)
    instance = model.model_validate({"region": "us-east-1", "count": 5})
    assert instance.model_dump() == {"region": "us-east-1", "count": 5}


def test_make_dynamic_model_rejects_non_object() -> None:
    with pytest.raises(ValueError, match="only 'object'"):
        _make_dynamic_model({"type": "array"})


def test_make_dynamic_model_rejects_bad_property() -> None:
    with pytest.raises(ValueError, match="unsupported type"):
        _make_dynamic_model(
            {"type": "object", "properties": {"x": {"type": "nonsense"}}}
        )


def test_session_default_routes_loaded() -> None:
    routes = SESSION.get_routes()
    assert len(routes) > 0


def test_session_set_custom_routes() -> None:
    from bedrock_fallback_engine.regions import BedrockRoute

    custom = [BedrockRoute(region="eu-west-1", model_id="custom-model")]
    SESSION.set_routes(custom)
    assert SESSION.get_routes() == custom


def test_session_stats_recording() -> None:
    SESSION.stats.record_attempt("primary")
    SESSION.stats.record_success("primary", 10, 20)
    SESSION.stats.record_attempt("cross-region")
    SESSION.stats.record_failure("cross-region")

    d = SESSION.stats.to_dict()
    assert d["route_attempts"] == {"primary": 1, "cross-region": 1}
    assert d["route_successes"] == {"primary": 1}
    assert d["route_failures"] == {"cross-region": 1}
    assert d["total_input_tokens"] == 10
    assert d["total_output_tokens"] == 20
