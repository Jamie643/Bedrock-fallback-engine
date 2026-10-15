"""Tests for BedrockClient — error mapping and response parsing."""

from __future__ import annotations

from typing import Any

import pytest
from botocore.exceptions import ClientError

from bedrock_fallback_engine.client import BedrockClient
from bedrock_fallback_engine.exceptions import (
    BedrockEngineError,
    BedrockThrottlingError,
    BedrockTransientError,
)


class _FakeRuntime:
    def __init__(self, behavior: Any) -> None:
        self._behavior = behavior

    def converse(self, **kwargs: Any) -> dict[str, Any]:
        if isinstance(self._behavior, Exception):
            raise self._behavior
        return self._behavior


def _client_with(behavior: Any) -> BedrockClient:
    return BedrockClient(region="us-east-1", client_factory=_FakeRuntime(behavior))


def _converse_ok() -> dict[str, Any]:
    return {
        "output": {"message": {"content": [{"text": "hello"}]}},
        "usage": {"inputTokens": 12, "outputTokens": 34},
    }


def test_parses_text_and_usage() -> None:
    result = _client_with(_converse_ok()).converse("m", [])
    assert result.text == "hello"
    assert result.input_tokens == 12
    assert result.output_tokens == 34


def test_missing_usage_defaults_to_zero() -> None:
    response = {"output": {"message": {"content": [{"text": "hi"}]}}}
    result = _client_with(response).converse("m", [])
    assert result.input_tokens == 0
    assert result.output_tokens == 0


def test_throttling_raises_typed_error() -> None:
    err = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "429"}},
        "converse",
    )
    with pytest.raises(BedrockThrottlingError):
        _client_with(err).converse("m", [])


def test_transient_raises_typed_error() -> None:
    err = ClientError(
        {"Error": {"Code": "ServiceUnavailableException", "Message": "503"}},
        "converse",
    )
    with pytest.raises(BedrockTransientError):
        _client_with(err).converse("m", [])


def test_unknown_client_error_raises_engine_error() -> None:
    err = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "403"}},
        "converse",
    )
    with pytest.raises(BedrockEngineError):
        _client_with(err).converse("m", [])


def test_bad_response_shape_raises_engine_error() -> None:
    with pytest.raises(BedrockEngineError):
        _client_with({"unexpected": "shape"}).converse("m", [])
