"""
Token usage service — records and aggregates OpenAI token consumption.

Works with both async (FastAPI) and sync (Celery) sessions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.token_usage import TokenUsage
from app.schemas.token_usage import TokenUsageOut, TokenUsageSummary


# ── Async (FastAPI) ──────────────────────────────────────────────────────────


async def get_usage_summary(session: AsyncSession) -> TokenUsageSummary:
    """Get aggregated token usage summary across all requests."""
    agg_result = await session.execute(
        select(
            func.coalesce(func.sum(TokenUsage.input_tokens), 0).label("total_input"),
            func.coalesce(func.sum(TokenUsage.output_tokens), 0).label("total_output"),
            func.coalesce(func.sum(TokenUsage.total_tokens), 0).label("total"),
            func.count(func.distinct(TokenUsage.request_id)).label("total_requests"),
        )
    )
    row = agg_result.one()

    records_result = await session.execute(
        select(TokenUsage).order_by(TokenUsage.created_at.desc()).limit(100)
    )
    records = [
        TokenUsageOut.model_validate(r) for r in records_result.scalars().all()
    ]

    return TokenUsageSummary(
        total_input_tokens=row.total_input,
        total_output_tokens=row.total_output,
        total_tokens=row.total,
        total_requests=row.total_requests,
        records=records,
    )


async def get_usage_by_request(
    session: AsyncSession,
    request_id: uuid.UUID,
) -> list[TokenUsage]:
    """Get all token usage records for a specific request."""
    result = await session.execute(
        select(TokenUsage)
        .where(TokenUsage.request_id == request_id)
        .order_by(TokenUsage.created_at.asc())
    )
    return list(result.scalars().all())


# ── Sync (Celery Workers) ───────────────────────────────────────────────────


def record_usage_sync(
    session: Session,
    request_id: uuid.UUID,
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    step_name: str,
) -> TokenUsage:
    """Record token usage for a pipeline step (sync version for Celery)."""
    usage = TokenUsage(
        request_id=request_id,
        model_name=model_name,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        step_name=step_name,
    )
    session.add(usage)
    session.flush()
    return usage
