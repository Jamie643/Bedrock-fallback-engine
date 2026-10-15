# bedrock-fallback-engine

> AWS-native resilience for Amazon Bedrock. Cross-region, cross-model failover with schema validation and per-route telemetry.

[![CI](https://github.com/Jamie643/bedrock-fallback-engine/actions/workflows/ci.yml/badge.svg)](https://github.com/Jamie643/bedrock-fallback-engine/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## The problem

Amazon Bedrock throttles. A region goes down. A model hits quota. When that happens mid-agent-workflow, your entire pipeline dies.

`bedrock-fallback-engine` wraps the Converse API in a **route chain**:

- **Cross-region failover** — us-east-1 throttled? Try us-west-2.
- **Cross-model failover** — Claude down? Try Nova.
- **Cross-provider failover** — Bedrock-native models all sick? Try Llama.
- **Schema validation** — malformed JSON fails over to the next route instead of crashing.
- **Token accounting** — every invocation reports input/output tokens and which route served it.

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

print(result.value)          # {"category": "bug", "urgency": "high"}
print(result.route.label)    # "primary"
print(result.input_tokens)   # 42
print(result.output_tokens)  # 11
```

If the primary region or model fails, the next route runs automatically. If **every** route fails, you get a `BedrockRouteExhausted` with the full error trail — each entry tagged with the route label that produced it.

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
## CloudWatch telemetry

Pass a `CloudWatchMetricsEmitter` to get structured metrics on every invocation.

```python
from bedrock_fallback_engine import (
    BedrockFallbackEngine,
    CloudWatchMetricsEmitter,
)

metrics = CloudWatchMetricsEmitter(namespace="MyApp/Bedrock", flush_size=20)
engine = BedrockFallbackEngine(schema=Triage, metrics=metrics)

engine.invoke([...])  # metrics emitted automatically

```

**Metrics emitted:**

| Metric | Unit | Dimensions |
|---|---|---|
| `InvocationCount` | Count | RouteLabel, Region, ModelId, Status |
| `InvocationLatency` | Milliseconds | RouteLabel, Region, ModelId |
| `ThrottleCount` | Count | RouteLabel, Region, ModelId |
| `TransientErrorCount` | Count | RouteLabel, Region, ModelId |
| `FallbackTriggered` | Count | FromRoute, ToRoute |
| `RouteExhausted` | Count | — |
| `InputTokens` | Count | RouteLabel, Region, ModelId |
| `OutputTokens` | Count | RouteLabel, Region, ModelId |

Telemetry is **best-effort** — if CloudWatch is unreachable, the engine keeps working. Buffer auto-flushes at `flush_size` points. Call `metrics.flush()` explicitly at shutdown to drain the buffer.

### Example CloudWatch Insights query

```
fields @timestamp, RouteLabel, FromRoute, ToRoute
| filter MetricName = "FallbackTriggered"
| sort @timestamp desc

```

---

## AWS-native emergency fallback

The default route chain includes **two AWS-native resilience tiers**:

1. **Cross-region inference profile** — `us.anthropic.claude-3-5-sonnet-20241022-v2:0`. Bedrock auto-routes this across any US region with capacity. Platform-level resilience.
2. **Emergency Titan route** — `amazon.titan-text-premier-v1:0`. Amazon's own model. Rarely throttled, always available.

No local AI. No external service. Pure Bedrock → Bedrock → Bedrock failover.

---

## Design principles

1. **Zero surprises.** Route order is explicit; failover is deterministic.
2. **Dependency-light.** Only `boto3` and `pydantic` at runtime.
3. **Two loops, clearly separated.** Retries happen *within* a route; failover happens *between* routes.
4. **Testable.** Inject a fake client factory; no AWS calls in the test suite.
5. **Observable.** Every route attempt, retry, failure, and success emits an event you can hook into CloudWatch, Prometheus, or a logger.

---

## How retries vs. failover work

```
Route 1 (us-east-1, Claude)
 ├─ attempt 1  fail
 ├─ attempt 2  fail  (retry within route)
 └─ attempt 3  fail  → give up on route

Route 2 (us-west-2, Claude)
 └─ attempt 1  success  ← returned
```

Retries (`max_retries`) apply **inside** each route. Failover is **between** routes. When a route can't be saved, the engine doesn't retry it forever — it moves on.

---

## Roadmap

- [x] Cross-region / cross-model failover
- [x] Schema validation with failover
- [x] Structured error trail
- [x] Token usage per invocation
- [ ] CloudWatch metrics emission
- [ ] Local emergency fallback (Ollama)
- [ ] Lambda deployment packaging

---

## License

MIT — see [LICENSE](LICENSE).
