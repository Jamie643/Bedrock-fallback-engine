# bedrock-fallback-engine — Live Demo

A FastAPI app that demonstrates cross-region Bedrock failover in real time.

---

## Run locally (dry-run — no AWS creds needed)

```bash
# From the repo root:
pip install -e .
pip install -r demo/requirements.txt

BEDROCK_DEMO_DRY_RUN=1 uvicorn demo.app:app --reload
```

Then hit the endpoint:

```bash
curl -i -X POST http://localhost:8000/triage \
  -H 'content-type: application/json' \
  -d '{"text": "My dashboard is broken"}'
```

Look at the response headers. `X-Route-Served-By: primary` — the primary route handled it.

---

## Run the failover demo

Add `?simulate_throttle=true`:

```bash
curl -i -X POST 'http://localhost:8000/triage?simulate_throttle=true' \
  -H 'content-type: application/json' \
  -d '{"text": "My dashboard is broken"}'
```

**Watch the headers change:** `X-Route-Served-By: cross-region`. The primary route was forced to fail. The engine failed over. Response is still 200 OK.

---

## Run with real Bedrock

```bash
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_DEFAULT_REGION=us-east-1
unset BEDROCK_DEMO_DRY_RUN

uvicorn demo.app:app --reload
```

Same commands. Same behavior. Real AWS calls.

---

## Run with Docker

```bash
docker build -t bedrock-demo -f demo/Dockerfile .
docker run -p 8000:8000 bedrock-demo
```

---

## The demo script for judges

> *"Here's an endpoint that classifies support tickets using Bedrock. Watch the response headers."*

```bash
curl -i -X POST http://localhost:8000/triage \
  -H 'content-type: application/json' \
  -d '{"text": "My dashboard is broken"}' | grep X-Route
# X-Route-Served-By: primary
```

> *"Now I'm going to kill us-east-1. Watch what happens."*

```bash
curl -i -X POST 'http://localhost:8000/triage?simulate_throttle=true' \
  -H 'content-type: application/json' \
  -d '{"text": "My dashboard is broken"}' | grep X-Route
# X-Route-Served-By: cross-region
```

> *"Same response. Same latency. User never knew. That's what the engine does — it turns Bedrock throttling from an outage into a non-event."*

---

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Service health + route list |
| `POST` | `/triage` | Classify a ticket (with failover) |
| `GET` | `/chaos/status` | Which routes are currently forced to fail |
| `POST` | `/chaos/clear` | Reset the chaos set |

### Query params on `/triage`

| Param | Type | Effect |
|---|---|---|
| `simulate_throttle` | bool | Force `primary` route to raise throttling error |
| `clear_chaos` | bool | Reset chaos state before handling this request |

### Response headers

| Header | Meaning |
|---|---|
| `X-Route-Served-By` | Which route label answered |
| `X-Route-Region` | AWS region that answered |
| `X-Route-Model` | Bedrock model that answered |
| `X-Input-Tokens` | Prompt token count |
| `X-Output-Tokens` | Response token count |
| `X-Latency-Ms` | Route call latency |
| `X-Attempts` | Total attempts before success |

---

## Interactive API docs

FastAPI auto-generates Swagger UI:

**http://localhost:8000/docs**

Great for judges to poke around manually.
