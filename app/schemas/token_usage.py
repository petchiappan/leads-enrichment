"""
Token Usage schemas — for the Admin Dashboard Token Usage view.

Tracks OpenAI token consumption split by input/output tokens.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class TokenUsageOut(BaseModel):
    """Serialized token usage record for API and Admin UI responses."""

    id: int
    request_id: uuid.UUID
    model_name: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    step_name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenUsageSummary(BaseModel):
    """Aggregated token usage summary for the dashboard."""

    total_input_tokens: int = Field(ge=0)
    total_output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    total_requests: int = Field(ge=0)
    records: list[TokenUsageOut]
