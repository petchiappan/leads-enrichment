"""
Pydantic schemas for Human Review Workflow.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class ReviewActionIn(BaseModel):
    """Payload to perform a human review decision."""

    action: str = Field(
        ...,
        pattern="^(approved|rejected|re_enriched)$",
        description="Action to apply: 'approved' | 'rejected' | 're_enriched'",
    )
    reviewer: str | None = Field(default="admin", max_length=256, description="Reviewer name or ID")
    notes: str | None = Field(default=None, description="Reviewer comments or justification")


class ReviewAuditOut(BaseModel):
    """Output representation of a review decision log entry."""

    id: int
    request_id: uuid.UUID
    action: str
    reviewer: str | None
    notes: str | None
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewQueueItem(BaseModel):
    """Summary of a lead awaiting review."""

    request_id: uuid.UUID
    company_name: str
    status: str
    confidence_score: float | None
    created_at: datetime.datetime | None = None
    enriched_data: dict[str, Any] | None = None


    model_config = ConfigDict(from_attributes=True)


class ReviewQueueListOut(BaseModel):
    items: list[ReviewQueueItem]
    total: int
