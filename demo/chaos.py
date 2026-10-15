"""
Chaos engineering hooks for the demo.

Two independent features:

1. **Forced failure** — flag specific routes as failing via a query param.
   Used to *demonstrate* failover.
2. **Dry-run mode** — return canned responses for every route, so the demo
   runs without AWS credentials or a live Bedrock account.
"""

from __future__ import annotations

import json
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


def _fake_triage_payload(route_label: str) -> str:
    """Return a plausible JSON triage result for dry-run mode."""
    return json.dumps(
        {
            "category": "bug",
            "urgency": "high",
            "suggested_action": f"Escalate to on-call. (served by {route_label})",
        }
    )


class ChaosBedrockClient(BedrockClient):
    """
    A BedrockClient that supports two demo-only behaviors:

    - **Forced failure**: raises ``BedrockThrottlingError`` if the route label
      is in the global failure set.
    - **Dry-run**: returns a canned ConverseResult without calling AWS.

    Args:
        region: AWS region for the real client (unused in dry-run).
        route_label: Label used for chaos lookups.
        dry_run: When True, no AWS calls are made.
    """

    def __init__(self, region: str, route_label: str, dry_run: bool = False) -> None:
        if dry_run:
            self.region = region
            self._client = None
        else:
            super().__init__(region=region)
        self._route_label = route_label
        self._dry_run = dry_run

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

        if self._dry_run:
            return ConverseResult(
                text=_fake_triage_payload(self._route_label),
                input_tokens=42,
                output_tokens=18,
            )

        return super().converse(model_id, messages, **kwargs)
