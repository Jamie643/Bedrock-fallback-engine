# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2025-10-20

### Added
- **MCP server** — 4 tools for AI agents and Alexa+ skills:
  - `bedrock_resilient_call` — resilient Bedrock call with automatic failover
  - `list_bedrock_routes` — inspect the current route chain
  - `get_fallback_stats` — session stats: attempts, failovers, token usage
  - `health_check` — verify AWS credentials are configured
- `bedrock-fallback-engine-mcp` CLI entry point for MCP clients
- `mcp.json` example config for Claude Desktop
- MCP-compatible badge in README
- Alexa+ framing in README (voice interaction use case)

### Changed
- `version` bumped to `0.3.0`

## [0.2.1] - 2025-10-15

### Added
- CloudWatch metrics emitter (`CloudWatchMetricsEmitter`)
- `InvocationResult.latency_ms` field
- AWS-native emergency routes: cross-region inference profile + Titan fallback
- FastAPI demo app with chaos mode in `demo/`
- Architecture diagram in README

### Changed
- Default route chain expanded from 2 to 5 tiers
- README rewritten for clarity

### Fixed
- Empty routes list now raises `ValueError` instead of silently falling back to defaults

## [0.2.0] - 2025-10-14

### Added
- CloudWatch metrics (8 metrics with buffered flush)
- Lambda packaging CLI (`bedrock-fallback-engine package`)

## [0.1.0] - 2025-10-13

### Added
- Initial release
- `BedrockFallbackEngine` with cross-region and cross-model failover
- `BedrockClient` wrapping the Converse API
- Typed errors: `BedrockThrottlingError`, `BedrockTransientError`, `BedrockRouteExhausted`
- Structured error trail with route labels
- Token accounting per invocation
- `BedrockRoute` dataclass with 5-tier default chain
