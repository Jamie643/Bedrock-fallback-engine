"""
Chaos engineering hooks for the demo.

Lets us force specific routes to fail at runtime via query parameters,
so the audience can *see* failover happen.
"""

from __future__ import annotations

import threading
from typing import Any

from bedrock_fallback_engine.client import BedrockClient, ConverseResult
from bedrock_fallback_engine.exceptions import BedrockThrottlingError

# Thread-safe set of route labels currently forced to fail.
_forced_failures: set[str] = set()
_lock = threading.Lock()


def force_failure(route_label: str) -> None:
    with _lock:
        _forced_failures.add(route_label)


def clear_failures() -> None:
    with _lock:
        _forced_failures.clear()


def is_forced_failure(route_label: str) -> bool:
    with _lock:
        return route_label in _forced_failures


def active_failures() -> list[str]:
    with _lock:
        return sorted(_forced_failures)


class ChaosBedrockClient(BedrockClient):
    """
    A BedrockClient that honors the chaos-module's forced-failure set.

    When a route is marked as failing, this client raises
    ``BedrockThrottlingError`` before ever calling AWS. This means the demo
    works without a real AWS account — and judges can force failover on
    demand even against a live deployment.
    """

    def __init__(self, region: str, route_label: str) -> None:
        super().__init__(region=region)
        self._route_label = route_label

    def converse(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ConverseResult:
        if is_forced_failure(self._route_label):
            raise BedrockThrottlingError(
                f"[CHAOS] forced throttling on route '{self._route_label}'"
            )
        return super().converse(model_id, messages, **kwargs)
