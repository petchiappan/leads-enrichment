"""
ReviewAudit model — audit log of human review decisions on leads.

Table: review_audit
Tracks when a reviewer approves, rejects, or triggers re-enrichment on a lead.
"""

from __future__ import annotations

import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ReviewAudit(Base):
    """Audit log tracking human review actions on leads."""

    __tablename__ = "review_audit"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.request_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="Reference to the lead request_id.",
    )
    action: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Action taken: approved | rejected | re_enriched",
    )
    reviewer: Mapped[str | None] = mapped_column(
        String(256),
        nullable=True,
        default="admin",
        doc="Identifier or email of the reviewer.",
    )
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Optional reviewer notes or rejection rationale.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp of review action.",
    )

    def __repr__(self) -> str:
        return f"<ReviewAudit request_id={self.request_id} action={self.action}>"
