"""Tests for BedrockRoute definitions."""

from __future__ import annotations

from bedrock_fallback_engine.regions import DEFAULT_ROUTES, BedrockRoute


def test_route_autogenerates_label():
    route = BedrockRoute(region="us-east-1", model_id="model-x")
    assert route.label == "us-east-1:model-x"


def test_route_keeps_custom_label():
    route = BedrockRoute(region="us-east-1", model_id="model-x", label="primary")
    assert route.label == "primary"


def test_default_routes_include_cross_region():
    regions = {r.region for r in DEFAULT_ROUTES}
    assert len(regions) >= 2, "expected routes spanning multiple regions"


def test_default_routes_include_cross_model():
    models = {r.model_id for r in DEFAULT_ROUTES}
    assert len(models) >= 2, "expected routes using multiple models"


def test_routes_are_immutable():
    route = BedrockRoute(region="us-east-1", model_id="model-x")
    import dataclasses
    import pytest

    with pytest.raises(dataclasses.FrozenInstanceError):
        route.region = "us-west-2"  # type: ignore[misc]
