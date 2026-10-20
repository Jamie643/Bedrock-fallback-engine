"""
MCP server entry point for bedrock-fallback-engine.

Run directly:
    bedrock-fallback-engine-mcp

Or via MCP clients (Claude Desktop, Cursor, etc.) using the config
in ``mcp.json``.
"""

from __future__ import annotations

import logging
import sys

from bedrock_fallback_engine.mcp.tools import register_tools

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("bedrock_fallback_engine.mcp")


def build_server() -> object:
    """Construct the MCP server with all tools registered."""
    from mcp.server.fastmcp import FastMCP  # imported lazily — optional dep

    mcp = FastMCP(
        "bedrock-fallback-engine",
        instructions=(
            "AWS-native resilience for Amazon Bedrock. "
            "Use `bedrock_resilient_call` for Bedrock calls with automatic "
            "cross-region and cross-model failover. "
            "Inspect the current route chain with `list_bedrock_routes`. "
            "Check session stats with `get_fallback_stats`. "
            "Verify AWS credentials with `health_check`."
        ),
    )
    register_tools(mcp)
    return mcp


def main() -> None:
    """Run the MCP server over stdio."""
    logger.info("Starting bedrock-fallback-engine MCP server")
    server = build_server()
    server.run()  # type: ignore[attr-defined]


if __name__ == "__main__":
    main()
