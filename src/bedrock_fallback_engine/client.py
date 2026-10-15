"""
Thin wrapper around boto3's Bedrock Runtime client.

Handles the Converse API shape, extracts text and token usage, and normalizes
AWS errors into our exception hierarchy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from botocore.exceptions import BotoCoreError, ClientError

from bedrock_fallback_engine.exceptions import (
    BedrockEngineError,
    BedrockThrottlingError,
    BedrockTransientError,
)

THROTTLING_CODES = frozenset({
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceQuotaExceededException",
})

TRANSIENT_CODES = frozenset({
    "ModelTimeoutException",
    "ModelNotReadyException",
    "InternalServerException",
    "ServiceUnavailableException",
})


@dataclass(frozen=True)
class ConverseResult:
    """Parsed result of a Bedrock Converse call."""

    text: str
    input_tokens: int
    output_tokens: int


class BedrockClient:
    """
    Minimal Bedrock Runtime client using the Converse API.

    Args:
        region: AWS region the underlying client targets.
        client_factory: Optional override for testing. When ``None``,
            ``boto3.client("bedrock-runtime", region_name=region)`` is used.
    """

    def __init__(
        self,
        region: str,
        client_factory: Any = None,
    ) -> None:
        self.region = region
        if client_factory is not None:
            self._client = client_factory
        else:
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=region)

    def converse(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> ConverseResult:
        """
        Call Bedrock's Converse API and return a parsed result.

        Raises:
            BedrockThrottlingError: On 429-class throttling errors.
            BedrockTransientError: On retryable AWS failures.
            BedrockEngineError: On any other AWS failure.
        """
        try:
            raw = self._client.converse(
                modelId=model_id,
                messages=messages,
                **kwargs,
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            response_dict = cast("dict[str, Any]", exc.response)
            if code in THROTTLING_CODES:
                raise BedrockThrottlingError(
                    f"Bedrock throttled in {self.region}: {code}",
                    response=response_dict,
                ) from exc
            if code in TRANSIENT_CODES:
                raise BedrockTransientError(
                    f"Bedrock transient error in {self.region}: {code}"
                ) from exc
            raise BedrockEngineError(
                f"Bedrock call failed in {self.region}: {code}"
            ) from exc
        except BotoCoreError as exc:
            raise BedrockEngineError(
                f"Bedrock transport error in {self.region}: {exc}"
            ) from exc

        response = cast("dict[str, Any]", raw)
        return self._parse_response(response)

    @staticmethod
    def _parse_response(response: dict[str, Any]) -> ConverseResult:
        """Extract assistant text and token usage from a Converse response."""
        try:
            text = response["output"]["message"]["content"][0]["text"]
            usage = response.get("usage", {}) or {}
            return ConverseResult(
                text=cast("str", text),
                input_tokens=int(usage.get("inputTokens", 0)),
                output_tokens=int(usage.get("outputTokens", 0)),
            )
        except (KeyError, IndexError, TypeError) as exc:
            raise BedrockEngineError(
                f"Unexpected Converse response shape: {response!r}"
            ) from exc
