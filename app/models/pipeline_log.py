"""
PipelineLog model — records every step of the enrichment pipeline.

Table: pipeline_logs
Skill ref: skill_db_schema.md (Table 2)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PipelineLog(Base):
    """Audit trail for each pipeline execution step."""

    __tablename__ = "pipeline_logs"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.request_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="References the lead's request_id.",
    )
    step_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="validate_input | fetch_apis | evaluate_intelligence_gate | spawn_fallback_agent | save_final_lineage",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="started",
        doc="started | success | failed | skipped",
    )
    payload: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        doc="Arbitrary JSON payload associated with this step (e.g., API responses, error details).",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PipelineLog request_id={self.request_id} step={self.step_name} status={self.status}>"
