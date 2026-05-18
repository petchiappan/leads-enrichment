"""
Embedding service — generate and search vector embeddings via OpenAI + pgvector.

Uses text-embedding-ada-002 (1536 dimensions) for semantic search.
"""

from __future__ import annotations

import logging
import uuid

from openai import OpenAI
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.config import settings
from app.models.vector_embedding import EMBEDDING_DIMENSIONS, VectorEmbedding

logger = logging.getLogger(__name__)


def _get_openai_client() -> OpenAI:
    """Create an OpenAI client instance."""
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def generate_embedding(text_content: str) -> list[float]:
    """Generate a vector embedding for the given text using OpenAI.

    Returns a list of floats with length EMBEDDING_DIMENSIONS (1536).
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set — returning zero vector")
        return [0.0] * EMBEDDING_DIMENSIONS

    client = _get_openai_client()
    response = client.embeddings.create(
        model=settings.OPENAI_EMBEDDING_MODEL,
        input=text_content,
    )
    return response.data[0].embedding


def build_content_summary(enriched_data: dict) -> str:
    """Build a human-readable summary from enriched data for embedding."""
    parts = []
    if enriched_data.get("company_name"):
        parts.append(f"Company: {enriched_data['company_name']}")
    if enriched_data.get("industry"):
        parts.append(f"Industry: {enriched_data['industry']}")
    if enriched_data.get("company_description"):
        parts.append(enriched_data["company_description"])
    if enriched_data.get("ceo_name"):
        parts.append(f"CEO: {enriched_data['ceo_name']}")
    if enriched_data.get("employee_count"):
        parts.append(f"Employees: {enriched_data['employee_count']}")
    if enriched_data.get("funding_raised"):
        parts.append(f"Funding: {enriched_data['funding_raised']}")
    if enriched_data.get("founding_year"):
        parts.append(f"Founded: {enriched_data['founding_year']}")

    return " | ".join(parts) if parts else "No enrichment data available"


# ── Sync (Celery Workers) ───────────────────────────────────────────────────


def store_embedding_sync(
    session: Session,
    lead_id: uuid.UUID,
    enriched_data: dict,
) -> VectorEmbedding:
    """Generate and store an embedding for the enriched lead data (sync)."""
    summary = build_content_summary(enriched_data)
    vector = generate_embedding(summary)

    embedding = VectorEmbedding(
        lead_id=lead_id,
        embedding=vector,
        content_summary=summary,
    )
    session.add(embedding)
    session.flush()
    return embedding


# ── Async (FastAPI — semantic search) ────────────────────────────────────────


async def search_similar(
    session: AsyncSession,
    query_text: str,
    limit: int = 10,
) -> list[dict]:
    """Search for leads with similar embeddings using cosine distance.

    Returns list of dicts with lead_id, content_summary, and similarity score.
    """
    query_vector = generate_embedding(query_text)

    # pgvector cosine distance: <=> operator (lower = more similar)
    result = await session.execute(
        select(
            VectorEmbedding.lead_id,
            VectorEmbedding.content_summary,
            VectorEmbedding.embedding.cosine_distance(query_vector).label("distance"),
        )
        .order_by(text("distance ASC"))
        .limit(limit)
    )

    rows = result.all()
    return [
        {
            "lead_id": str(row.lead_id),
            "content_summary": row.content_summary,
            "similarity": round(1.0 - row.distance, 4),  # Convert distance to similarity
        }
        for row in rows
    ]
