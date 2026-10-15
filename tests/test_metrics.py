"""Tests for CloudWatchMetricsEmitter."""

from __future__ import annotations

from typing import Any

import pytest

from bedrock_fallback_engine.metrics import (
    DEFAULT_NAMESPACE,
    CloudWatchMetricsEmitter,
)


class _FakeCloudWatch:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def put_metric_data(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {}


def test_emit_buffers_until_flush_size() -> None:
    fake = _FakeCloudWatch()
    emitter = CloudWatchMetricsEmitter(cloudwatch_client=fake, flush_size=3)

    emitter.emit("A", 1)
    emitter.emit("B", 2)
    assert fake.calls == []  # nothing sent yet

    emitter.emit("C", 3)  # hits flush_size -> auto-flush
    assert len(fake.calls) == 1
    assert len(fake.calls[0]["MetricData"]) == 3


def test_manual_flush() -> None:
    fake = _FakeCloudWatch()
    emitter = CloudWatchMetricsEmitter(cloudwatch_client=fake, flush_size=10)

    emitter.emit("A", 1)
    emitter.emit("B", 2)
    sent = emitter.flush()

    assert sent == 2
    assert len(fake.calls) == 1


def test_flush_when_empty_returns_zero() -> None:
    fake = _FakeCloudWatch()
    emitter = CloudWatchMetricsEmitter(cloudwatch_client=fake)

    assert emitter.flush() == 0
    assert fake.calls == []


def test_namespace_is_configurable() -> None:
    fake = _FakeCloudWatch()
    emitter = CloudWatchMetricsEmitter(
        namespace="MyApp/Bedrock",
        cloudwatch_client=fake,
        flush_size=1,
    )
    emitter.emit("A", 1)
    assert fake.calls[0]["Namespace"] == "MyApp/Bedrock"


def test_default_namespace() -> None:
    fake = _FakeCloudWatch()
    emitter = CloudWatchMetricsEmitter(cloudwatch_client=fake, flush_size=1)
    emitter.emit("A", 1)
    assert fake.calls[0]["Namespace"] == DEFAULT_NAMESPACE


def test_dimensions_are_forwarded() -> None:
    fake = _FakeCloudWatch()
    emitter = CloudWatchMetricsEmitter(cloudwatch_client=fake, flush_size=1)

    emitter.emit("Latency", 42, unit="Milliseconds", dimensions={"Region": "us-east-1"})

    datum = fake.calls[0]["MetricData"][0]
    assert datum["MetricName"] == "Latency"
    assert datum["Value"] == 42.0
    assert datum["Unit"] == "Milliseconds"
    assert datum["Dimensions"] == [{"Name": "Region", "Value": "us-east-1"}]


def test_no_dimensions_key_when_empty() -> None:
    fake = _FakeCloudWatch()
    emitter = CloudWatchMetricsEmitter(cloudwatch_client=fake, flush_size=1)
    emitter.emit("A", 1)
    assert "Dimensions" not in fake.calls[0]["MetricData"][0]


def test_flush_failure_is_swallowed() -> None:
    class _BrokenCloudWatch:
        def put_metric_data(self, **kwargs: Any) -> None:
            raise RuntimeError("CloudWatch is down")

    emitter = CloudWatchMetricsEmitter(
        cloudwatch_client=_BrokenCloudWatch(),
        flush_size=1,
    )
    # Should not raise
    emitter.emit("A", 1)


def test_flush_failure_invokes_callback() -> None:
    errors: list[Exception] = []

    class _BrokenCloudWatch:
        def put_metric_data(self, **kwargs: Any) -> None:
            raise RuntimeError("nope")

    emitter = CloudWatchMetricsEmitter(
        cloudwatch_client=_BrokenCloudWatch(),
        flush_size=1,
        on_flush_error=errors.append,
    )
    emitter.emit("A", 1)

    assert len(errors) == 1
    assert isinstance(errors[0], RuntimeError)


def test_invalid_flush_size_rejected() -> None:
    with pytest.raises(ValueError):
        CloudWatchMetricsEmitter(flush_size=0)
