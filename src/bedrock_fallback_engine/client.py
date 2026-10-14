"""
Thin wrapper around boto3's Bedrock Runtime client.

Handles the Converse API call shape, extracts text output, and normalizes
AWS errors into our own exception hierarchy.
"""

from __future__ import annotations

from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from bedrock_fallback_engine.exceptions import (
    BedrockEngineError,
    BedrockThrottlingError,
)

# AWS error codes that indicate a transient, region-local failure.
THROTTLING_CODES = {
    "ThrottlingException",
    "TooManyRequestsException",
    "ServiceQuotaExceededException",
}

RETRYABLE_CODES = {
    "ModelTimeoutException",
    "ModelNotReadyException",
    "InternalServerException",
    "ServiceUnavailableException",
}


class BedrockClient:
    """
    Minimal Bedrock Runtime client using the Converse API.

    Args:
        region: AWS region the underlying client targets.
        client_factory: Optional override for testing. Defaults to
            ``boto3.client("bedrock-runtime", region_name=region)``.
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
            import boto3  # local import so tests don't need boto3 at import time

            self._client = boto3.client("bedrock-runtime", region_name=region)

    def converse(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Call Bedrock's Converse API and return the raw response dict.

        Raises:
            BedrockThrottlingError: On 429-class throttling errors.
            BedrockEngineError: On any other AWS failure.
        """
        try:
            return self._client.converse(
                modelId=model_id,
                messages=messages,
                **kwargs,
            )
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code", "Unknown")
            if code in THROTTLING_CODES:
                raise BedrockThrottlingError(
                    f"Bedrock throttled in {self.region}: {code}",
                    response=exc.response,
                ) from exc
            if code in RETRYABLE_CODES:
                raise BedrockEngineError(
                    f"Bedrock transient error in {self.region}: {code}"
                ) from exc
            raise BedrockEngineError(
                f"Bedrock call failed in {self.region}: {code}"
            ) from exc
        except BotoCoreError as exc:
            raise BedrockEngineError(
                f"Bedrock transport error in {self.region}: {exc}"
            ) from exc

    @staticmethod
    def extract_text(response: dict[str, Any]) -> str:
        """
        Pull the assistant's text out of a Converse API response.

        Converse returns::

            {
              "output": {"message": {"content": [{"text": "..."}]}},
              ...
            }
        """
        try:
            return response["output"]["message"]["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise BedrockEngineError(
                f"Unexpected Converse response shape: {response!r}"
            ) from exc
