"""Tests for BedrockRoute definitions."""

from __future__ import annotations

import dataclasses

import pytest

from bedrock_fallback_engine.regions import DEFAULT_ROUTES, BedrockRoute


def test_route_autogenerates_label() -> None:
    route = BedrockRoute(region="us-east-1", model_id="model-x")
    assert route.label == "us-east-1:model-x"


def test_route_keeps_custom_label() -> None:
    route = BedrockRoute(region="us-east-1", model_id="model-x", label="primary")
    assert route.label == "primary"


def test_default_routes_span_multiple_regions() -> None:
    regions = {r.region for r in DEFAULT_ROUTES}
    assert len(regions) >= 2


def test_default_routes_span_multiple_models() -> None:
    models = {r.model_id for r in DEFAULT_ROUTES}
    assert len(models) >= 2


def test_routes_are_immutable() -> None:
    route = BedrockRoute(region="us-east-1", model_id="model-x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        route.region = "us-west-2"  # type: ignore[misc]
