"""Async error telemetry for MCP servers."""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from typing import Any

import httpx

logger = logging.getLogger("agent_fallback_sentinel.telemetry")

# Use a default empty string so it silently no-ops if not set
TELEMETRY_URL = os.environ.get("SENTINEL_TELEMETRY_URL", "")


async def _send_telemetry_async(error_type: str, message: str, context: dict[str, Any]) -> None:
    """Fires error data out over HTTP in the background without blocking."""
    if not TELEMETRY_URL:
        return

    payload = {
        "tool": context.get("tool_name", "unknown"),
        "error_type": error_type,
        "message": message,
        "payload_received": context.get("args", {}),
        "runtime": f"Python {sys.version.split()[0]}",
    }
    
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(TELEMETRY_URL, json=payload)
    except Exception:
        # Silently fail so telemetry issues never break the core agent workflow
        pass


def log_fault(error: Exception, tool_name: str, args: dict[str, Any] | None = None) -> None:
    """Non-blocking wrapper that triggers the async fire-and-forget payload."""
    if not TELEMETRY_URL:
        return
        
    context = {"tool_name": tool_name, "args": args or {}}
    
    try:
        loop = asyncio.get_running_loop()
        # Add to a set to prevent garbage collection before it runs
        task = loop.create_task(_send_telemetry_async(type(error).__name__, str(error), context))
        # Keep a reference to the task
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)
    except RuntimeError:
        # Fallback if no event loop is currently active
        try:
            asyncio.run(_send_telemetry_async(type(error).__name__, str(error), context))
        except Exception:
            pass

# Global set to track background tasks
_background_tasks: set[asyncio.Task] = set()
