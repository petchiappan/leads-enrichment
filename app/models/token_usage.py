"""
TokenUsage model — tracks OpenAI API token consumption per pipeline step.

Table: token_usage
Required by Admin Dashboard (Token Usage menu — split by Input/Output tokens).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TokenUsage(Base):
    """Records OpenAI token usage for cost tracking and admin visibility."""

    __tablename__ = "token_usage"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.request_id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="References the lead pipeline run.",
    )
    model_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="OpenAI model used (e.g., 'gpt-4o', 'text-embedding-ada-002').",
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    step_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Pipeline step that consumed these tokens.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<TokenUsage request_id={self.request_id} model={self.model_name} total={self.total_tokens}>"
