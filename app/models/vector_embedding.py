"""
VectorEmbedding model — stores pgvector embeddings for semantic search.

Table: vector_embeddings
Skill ref: skill_db_schema.md (Table 4)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base

# OpenAI text-embedding-ada-002 produces 1536-dimensional vectors
EMBEDDING_DIMENSIONS = 1536


class VectorEmbedding(Base):
    """Stores lead summary embeddings for semantic querying via pgvector."""

    __tablename__ = "vector_embeddings"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("leads.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        doc="References the lead this embedding belongs to.",
    )
    embedding = mapped_column(
        Vector(EMBEDDING_DIMENSIONS),
        nullable=False,
        doc="1536-dim vector from OpenAI text-embedding-ada-002.",
    )
    content_summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        doc="Human-readable summary of the content that was embedded.",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<VectorEmbedding lead_id={self.lead_id}>"
