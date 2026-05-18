"""
Semantic Search API — search enriched leads using pgvector cosine similarity.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import embedding_service

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    """Semantic search query."""
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Natural language search query (e.g., 'AI companies in healthcare').",
        examples=["AI companies in healthcare"],
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results to return.",
    )


class SearchResult(BaseModel):
    """A single semantic search result."""
    lead_id: str
    content_summary: str | None
    similarity: float = Field(description="Cosine similarity score (0.0 to 1.0)")


class SearchResponse(BaseModel):
    """Semantic search response."""
    query: str
    results: list[SearchResult]
    total: int


@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Semantic search across enriched leads",
    description="Uses pgvector cosine similarity to find leads matching the query.",
)
async def semantic_search(
    payload: SearchRequest,
    db: AsyncSession = Depends(get_db),
) -> SearchResponse:
    """Search for leads similar to the query using vector embeddings."""
    results = await embedding_service.search_similar(
        session=db,
        query_text=payload.query,
        limit=payload.limit,
    )
    return SearchResponse(
        query=payload.query,
        results=[SearchResult(**r) for r in results],
        total=len(results),
    )
