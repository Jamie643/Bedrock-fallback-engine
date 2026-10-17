# AWS Bedrock Resilience - Friction Log

**Project:** bedrock-fallback-engine  
**Target Services:** Amazon Bedrock, AWS CloudWatch, boto3  

---

### Task Attempted
Simulating regional Bedrock rate limits (HTTP 429 throttles) and network outages to verify fallback behavior without triggering unnecessary live API costs.

### Steps Taken
1. Configured cross-region failover routes in `boto3`.
2. Attempted to test rate-limit conditions using standard AWS SDK mocks.
3. Built a FastAPI demo server with a chaos route (`?simulate_throttle=true`) to force fallback logic for live demonstrations.

### Expected vs. Actual Result
* **Expected:** An official offline Bedrock mocking or local emulator utility provided within `boto3` to test throttle responses and fallback handling natively.
* **Actual:** Required writing custom unit test stubs and mock response wrappers from scratch to test HTTP 429 exceptions reliably.

### Impact & Severity
* **Severity:** Moderate
* **Workaround Used:** Built custom `pytest` fixtures for offline test coverage and added a explicit `simulate_throttle` parameter to the FastAPI demo app.

### Actionable Suggestion
Provide an official offline Bedrock mocking helper or sandbox simulator within `boto3` so developers can build and test resilience middleware effortlessly.
