# Bedrock-fallback-engine
# bedrock-fallback-engine

> AWS-native resilience for Amazon Bedrock. Cross-region, cross-model failover with schema validation — built on [agent-fallback-sentinel](https://github.com/Jamie643/agent-fallback-sentinel).

[![CI](https://github.com/Jamie643/bedrock-fallback-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Jamie643/bedrock-fallback-engine/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## The problem

Bedrock throttles. A region goes down. A model hits quota. When that happens mid-agent-workflow, your entire pipeline dies.

`bedrock-fallback-engine` wraps the Converse API in a **route chain**:

- **Cross-region failover** — `us-east-1` throttled? Try `us-west-2`.
- **Cross-model failover** — Claude down? Try Nova.
- **Cross-provider failover** — Bedrock models all sick? Try Llama.
- **Schema validation** — malformed JSON fails over to the next route instead of crashing.
- **Structured errors** — every failed route is captured with its exception.

---

## Install

```bash
pip install bedrock-fallback-engine
```

Requires AWS credentials configured (`aws configure`, env vars, or IAM role).

---

## Quickstart

```python
from pydantic import BaseModel
from bedrock_fallback_engine import BedrockFallbackEngine

class Triage(BaseModel):
    category: str
    urgency: str

engine = BedrockFallbackEngine(schema=Triage)

result = engine.invoke([
    {"role": "user", "content": [{"text": "Classify: dashboard won't load."}]}
])
# -> {"category": "bug", "urgency": "high"}
```

If the primary region or model fails, the next route runs automatically. If **every** route fails, you get a `BedrockRouteExhausted` with the full error trail.

---

## Default routes

`us-east-1` Claude 3.5 Sonnet → `us-west-2` Claude 3.5 Sonnet → `us-east-1` Nova Pro → `us-west-2` Llama 3 70B

Bring your own:

```python
from bedrock_fallback_engine import BedrockRoute, BedrockFallbackEngine

engine = BedrockFallbackEngine(routes=[
    BedrockRoute("eu-west-1", "anthropic.claude-3-5-sonnet-20241022-v2:0"),
    BedrockRoute("eu-central-1", "amazon.nova-pro-v1:0"),
])
```

---

## Why on top of agent-fallback-sentinel?

`agent-fallback-sentinel` solves **generic** retries, circuit breaking, and schema validation for any LLM. `bedrock-fallback-engine` is the **AWS-native** layer: it speaks the Converse API, understands Bedrock error codes, and knows AWS regions. Layered, not duplicated.

---

## Roadmap

- [x] Cross-region / cross-model failover
- [x] Schema validation
- [x] Structured error trail
- [ ] CloudWatch metrics emission (Sprint 2)
- [ ] Token cost tracking per route
- [ ] Local emergency fallback (Ollama)
- [ ] Lambda deployment packaging

---

## License

MIT — see [LICENSE](LICENSE).
