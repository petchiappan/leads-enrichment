"""
Token Usage API — view OpenAI token consumption metrics.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.token_usage import TokenUsageOut, TokenUsageSummary
from app.services import token_service

router = APIRouter(prefix="/api", tags=["token-usage"])


@router.get(
    "/tokens",
    response_model=TokenUsageSummary,
    summary="Get token usage summary",
    description="Returns aggregated token usage across all requests plus recent records.",
)
async def get_token_summary(
    db: AsyncSession = Depends(get_db),
) -> TokenUsageSummary:
    """Get aggregated token usage summary."""
    return await token_service.get_usage_summary(db)


@router.get(
    "/tokens/{request_id}",
    response_model=list[TokenUsageOut],
    summary="Get token usage for a specific request",
)
async def get_token_usage_by_request(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[TokenUsageOut]:
    """Get all token usage records for a specific enrichment request."""
    records = await token_service.get_usage_by_request(db, request_id)
    return [TokenUsageOut.model_validate(r) for r in records]
