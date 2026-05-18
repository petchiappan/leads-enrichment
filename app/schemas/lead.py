"""
Lead output schemas — used for Admin Dashboard list/detail views.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class LeadOut(BaseModel):
    """Serialized representation of a lead for API and Admin UI responses."""

    id: uuid.UUID
    request_id: uuid.UUID
    raw_input: dict[str, Any]
    enriched_data: dict[str, Any] | None = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LeadListOut(BaseModel):
    """Paginated list of leads."""

    leads: list[LeadOut]
    total: int = Field(ge=0, description="Total number of leads matching the query.")
