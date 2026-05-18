"""
Lead model — stores final enriched data.

Table: leads
Skill ref: skill_db_schema.md (Table 1)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Lead(Base):
    """Primary table storing raw input and enriched output for each lead."""

    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True,
        default=uuid.uuid4,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        unique=True,
        index=True,
        nullable=False,
    )
    raw_input: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        doc="Original payload received from the POST /api/enrich request.",
    )
    enriched_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        doc="Final merged enrichment result (deterministic + fallback).",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending",
        index=True,
        doc="pending | processing | completed | failed",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Lead request_id={self.request_id} status={self.status}>"
