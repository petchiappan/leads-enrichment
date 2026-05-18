"""
Pipeline log schemas — used for step-by-step audit trail views.

Maps to: pipeline_logs table (skill_db_schema.md Table 2)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class PipelineStepStatus(str, enum.Enum):
    """Valid statuses for a pipeline execution step."""

    STARTED = "started"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class PipelineLogOut(BaseModel):
    """Serialized representation of a single pipeline step log entry."""

    id: int
    request_id: uuid.UUID
    step_name: str
    status: PipelineStepStatus
    payload: dict[str, Any] | None = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class PipelineLogListOut(BaseModel):
    """List of pipeline log entries for a specific request."""

    request_id: uuid.UUID
    steps: list[PipelineLogOut]
    total: int
