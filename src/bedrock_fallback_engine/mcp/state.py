"""
Session state for the Bedrock MCP server.

Tracks the configured route chain and accumulated call statistics
across the current server session.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from bedrock_fallback_engine.regions import BedrockRoute, DEFAULT_ROUTES


@dataclass
class CallStats:
    """Accumulated call statistics for the current server session."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    failovers: int = 0
    route_attempts: dict[str, int] = field(default_factory=dict)
    route_successes: dict[str, int] = field(default_factory=dict)
    route_failures: dict[str, int] = field(default_factory=dict)
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    def record_attempt(self, route_label: str) -> None:
        self.route_attempts[route_label] = self.route_attempts.get(route_label, 0) + 1

    def record_success(self, route_label: str, input_tokens: int, output_tokens: int) -> None:
        self.route_successes[route_label] = self.route_successes.get(route_label, 0) + 1
        self.successful_calls += 1
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

    def record_failure(self, route_label: str) -> None:
        self.route_failures[route_label] = self.route_failures.get(route_label, 0) + 1
        self.failed_calls += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "failovers": self.failovers,
            "route_attempts": dict(self.route_attempts),
            "route_successes": dict(self.route_successes),
            "route_failures": dict(self.route_failures),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
        }


class SessionState:
    """Thread-safe, process-scoped state for the MCP server."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._routes: list[BedrockRoute] = list(DEFAULT_ROUTES)
        self._stats = CallStats()

    def set_routes(self, routes: list[BedrockRoute]) -> None:
        with self._lock:
            self._routes = list(routes)

    def get_routes(self) -> list[BedrockRoute]:
        with self._lock:
            return list(self._routes)

    def reset_to_defaults(self) -> None:
        with self._lock:
            self._routes = list(DEFAULT_ROUTES)

    @property
    def stats(self) -> CallStats:
        return self._stats

    def reset_stats(self) -> None:
        with self._lock:
            self._stats = CallStats()


SESSION = SessionState()
