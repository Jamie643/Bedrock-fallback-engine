"""Pydantic schemas for the demo API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TriageRequest(BaseModel):
    """Request body for the /triage endpoint."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Support ticket text to classify.",
        examples=["My dashboard won't load and it's blocking my whole team."],
    )


class TriageResponse(BaseModel):
    """Response from a successful engine invocation."""

    category: str = Field(..., description="Issue category, e.g. 'bug', 'billing'.")
    urgency: str = Field(..., description="Urgency level: 'low', 'medium', 'high'.")
    suggested_action: str = Field(..., description="Recommended next step.")

    # Demo-only fields — not part of the LLM output.
    served_by_route: str = Field(..., description="Which Bedrock route answered.")
    served_by_region: str = Field(..., description="Which AWS region answered.")
    input_tokens: int = Field(..., description="Prompt tokens consumed.")
    output_tokens: int = Field(..., description="Response tokens generated.")
    latency_ms: float = Field(..., description="Route call latency in milliseconds.")
    attempts: int = Field(..., description="Total attempts before success.")


class HealthResponse(BaseModel):
    status: str
    version: str
    routes: list[str]
