"""
CloudWatch metrics emitter for bedrock-fallback-engine.

Buffers metric data points in memory and flushes them in batches via
``PutMetricData``. Designed to be optional — pass ``metrics=None`` to
disable telemetry entirely (zero overhead).

Metric names follow AWS naming conventions: PascalCase, no dots, unit
specified per metric.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("bedrock_fallback_engine.metrics")

DEFAULT_NAMESPACE = "BedrockFallback"


@dataclass
class _DataPoint:
    """A single metric observation awaiting upload."""

    name: str
    value: float
    unit: str
    dimensions: dict[str, str] = field(default_factory=dict)


class CloudWatchMetricsEmitter:
    """
    Buffers Bedrock-related metrics and flushes them to CloudWatch.

    Args:
        namespace: CloudWatch namespace. Defaults to ``"BedrockFallback"``.
        flush_size: Number of buffered data points that triggers an auto-flush.
        cloudwatch_client: Injectable CloudWatch client for testing. When
            ``None``, a real boto3 client is created lazily on first flush.
        on_flush_error: Optional callback invoked if a flush raises.
    """

    def __init__(
        self,
        namespace: str = DEFAULT_NAMESPACE,
        flush_size: int = 20,
        cloudwatch_client: Any = None,
        on_flush_error: Any = None,
    ) -> None:
        if flush_size <= 0:
            raise ValueError("flush_size must be > 0")

        self.namespace = namespace
        self.flush_size = flush_size
        self._client = cloudwatch_client
        self._on_flush_error = on_flush_error
        self._buffer: list[_DataPoint] = []
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def emit(
        self,
        name: str,
        value: float,
        unit: str = "Count",
        dimensions: dict[str, str] | None = None,
    ) -> None:
        """
        Record a metric data point. Auto-flushes when the buffer hits
        ``flush_size``.
        """
        point = _DataPoint(
            name=name,
            value=float(value),
            unit=unit,
            dimensions=dict(dimensions or {}),
        )

        should_flush = False
        with self._lock:
            self._buffer.append(point)
            if len(self._buffer) >= self.flush_size:
                should_flush = True

        if should_flush:
            self.flush()

    def flush(self) -> int:
        """
        Send all buffered data points to CloudWatch.

        Returns the number of data points sent. On failure, logs the error
        and clears the buffer (best-effort telemetry — never breaks the caller).
        """
        with self._lock:
            if not self._buffer:
                return 0
            to_send = self._buffer
            self._buffer = []

        try:
            client = self._get_client()
            client.put_metric_data(
                Namespace=self.namespace,
                MetricData=[self._to_cw_shape(p) for p in to_send],
            )
            return len(to_send)
        except Exception as exc:  # noqa: BLE001
            logger.warning("CloudWatch flush failed (%d points): %s", len(to_send), exc)
            if self._on_flush_error is not None:
                try:
                    self._on_flush_error(exc)
                except Exception:  # noqa: BLE001
                    logger.exception("on_flush_error callback raised; ignoring")
            return 0

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #

    def _get_client(self) -> Any:
        if self._client is None:
            import boto3

            self._client = boto3.client("cloudwatch")
        return self._client

    @staticmethod
    def _to_cw_shape(point: _DataPoint) -> dict[str, Any]:
        """Convert an internal _DataPoint to CloudWatch's MetricDatum shape."""
        dims = [{"Name": k, "Value": v} for k, v in point.dimensions.items()]
        shape: dict[str, Any] = {
            "MetricName": point.name,
            "Value": point.value,
            "Unit": point.unit,
        }
        if dims:
            shape["Dimensions"] = dims
        return shape
