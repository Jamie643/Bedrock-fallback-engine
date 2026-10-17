# AWS Bedrock Resilience - CI & DX Friction Log

**Project:** bedrock-fallback-engine  
**Target Services:** GitHub Actions (CI), pre-commit/flake8, mypy, pytest, boto3-related test harness  
**Data Source:** Analysis of initial CI pipeline iterations (143 workflow runs in total to reach 100% green builds across Python 3.10–3.12).

---

### Overview
This friction log documents the primary developer-experience bottlenecks, testing challenges, and CI pipeline failures observed across 143 workflow runs during the development of `bedrock-fallback-engine`. Each entry outlines the steps triggered, expected vs. actual outcomes, severity, and the actionable engineering resolution used to achieve green builds and 93%+ test coverage.

---

### Issue 1 — Linting & Style Failures (E501 "Line too long" and formatting)
* **Steps that triggered it:**
  1. Automated `pre-commit` and `flake8` checks executed during CI push/PR triggers.
  2. Files checked reported line-length and style compliance errors.
* **Expected vs. Actual:**
  * *Expected:* Code passes style checks seamlessly in CI.
  * *Actual:* Multiple early runs failed with `E501 (Line too long)` errors (e.g., "Found 11 errors", "4 fixable with `--fix`"), causing jobs to exit non-zero.
* **Impact & Severity:**
  * *Severity:* Low → Moderate (blocked PR merges and generated noisy CI status badges).
* **Actionable Suggestion & Workaround:**
  * Configured local `pre-commit` hooks to auto-fix formatting prior to commits.
  * Re-wrapped long docstrings and configuration dictionary lines to maintain strict PEP 8 compliance without disabling lint rules.

---

### Issue 2 — Standalone `pre-commit` Workflow Execution Failures
* **Steps that triggered it:**
  1. A dedicated GitHub Actions workflow referencing `.pre-commit-config.yaml` executed as a isolated check.
* **Expected vs. Actual:**
  * *Expected:* `pre-commit` workflow runs independently and completes successfully.
  * *Actual:* The workflow repeatedly failed on environment setup and cached hook initialization before running tests.
* **Impact & Severity:**
  * *Severity:* Low → Moderate (developer friction and redundant failure notifications).
* **Actionable Suggestion & Workaround:**
  * Consolidated linting, static typing, and formatting checks into a single matrix CI job to streamline pipeline feedback and reduce redundant container setups.

---

### Issue 3 — `mypy` Static Type Checking Incompatibilities
* **Steps that triggered it:**
  1. `mypy` type checker step running in CI against core client code (`src/bedrock_fallback_engine/client.py`).
* **Expected vs. Actual:**
  * *Expected:* Strict type checks pass with zero errors.
  * *Actual:* Reported return type mismatches and incompatible argument types:
    * `client.py:71: error: Returning Any from function declared to return "dict[str, Any]"`
    * `client.py:81: error: Argument "response" to "BedrockThrottlingError" has incompatible type`
    * `client.py:108: error: Returning Any from function declared to return "str"`
* **Impact & Severity:**
  * *Severity:* Moderate (type loose-ends risk runtime bugs when handling dynamic AWS API payloads).
* **Actionable Suggestion & Workaround:**
  * Replaced implicit `Any` returns with explicit typing and custom `TypedDict` schemas for Bedrock responses.
  * Tightened exception parameter definitions to explicitly accept `dict[str, Any] | None`.

---

### Issue 4 — Pytest AttributeErrors: Missing `boto3` Module Seam
* **Steps that triggered it:**
  1. Running `pytest` unit test suite (~13 initial tests) in CI.
  2. Test cases attempted to `monkeypatch` or mock `bedrock_fallback_engine.client.boto3`.
* **Expected vs. Actual:**
  * *Expected:* Tests can inject mocked `boto3` client responses to test HTTP 429 throttling without calling live AWS endpoints.
  * *Actual:* Tests failed across Python versions with `AttributeError: module 'bedrock_fallback_engine.client' has no attribute 'boto3'`.
* **Impact & Severity:**
  * *Severity:* High (prevented offline verification of cross-region and cross-model failover logic).
* **Actionable Suggestion & Workaround:**
  * Refactored client instantiation to support dependency injection and clear factory seams for `boto3` clients.
  * Updated test fixtures to patch the client factory rather than unexposed top-level imports.

---

### Issue 5 — Test Expectation Regressions (`DID NOT RAISE`)
* **Steps that triggered it:**
  1. Executing negative test cases in `tests/test_engine.py`.
  2. Testing invalid engine initialization configurations.
* **Expected vs. Actual:**
  * *Expected:* `test_engine_requires_at_least_one_route` raises `ValueError` when initialized with empty route lists.
  * *Actual:* Test failed with `Failed: DID NOT RAISE ValueError`.
* **Impact & Severity:**
  * *Severity:* Moderate (masked missing input validation in early refactoring).
* **Actionable Suggestion & Workaround:**
  * Re-implemented strict validation guards in `BedrockFallbackEngine.__init__` to throw explicit `ValueError` instances on empty route configurations.

---

### Issue 6 — Low Initial Code Coverage Baseline (47%)
* **Steps that triggered it:**
  1. Coverage report generation (`pytest-cov`) during initial CI runs.
* **Expected vs. Actual:**
  * *Expected:* High test coverage for a mission-critical resilience library.
  * *Actual:* Initial coverage sat at ~47%, leaving fallback error handlers and CloudWatch telemetry buffering unverified.
* **Impact & Severity:**
  * *Severity:* Moderate (low confidence in edge-case recovery and network timeout behavior).
* **Actionable Suggestion & Workaround:**
  * Added 27+ comprehensive unit tests targeting transient network errors, HTTP 429 throttles, and CloudWatch buffer flushes.
  * Raised final coverage to **93%+ across Python 3.10, 3.11, and 3.12**.

---

### Summary of Resolutions
1. **Testing Seams:** Refactored `boto3` client creation to support clean mocking seams without network dependencies.
2. **Type Safety:** Eliminated `Any` type leaks across Bedrock response wrappers.
3. **Pipeline Velocity:** Unified linting, static typing (`mypy`), and multi-python version testing into a single green matrix workflow on run #143.
