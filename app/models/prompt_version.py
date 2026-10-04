"""
PromptVersion model — database-backed versioned prompts.

Table: prompt_versions
Supports runtime prompt management, activation, and audit logging.
"""

from __future__ import annotations

import datetime

from sqlalchemy import Boolean, DateTime, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PromptVersion(Base):
    """Stores versioned prompts for LLM pipeline steps."""

    __tablename__ = "prompt_versions"
    __table_args__ = (
        UniqueConstraint("name", "version", name="uq_prompt_name_version"),
        Index("ix_prompt_versions_name_env", "name", "environment"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    name: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        doc="Logical name of prompt, e.g. 'fallback_system_prompt' or 'intelligence_gate_prompt'.",
    )
    version: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Semver string, e.g. 'v1.0.0'.",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        doc="Full prompt text / system instructions or template.",
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="production",
        server_default="production",
        doc="Environment tag, e.g. 'production', 'staging', 'development'.",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
        doc="Whether this version is currently the active one for its name and environment.",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when prompt version was created.",
    )

    def __repr__(self) -> str:
        return f"<PromptVersion {self.name}:{self.version} env={self.environment} active={self.is_active}>"
