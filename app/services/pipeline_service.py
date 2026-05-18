"""
Pipeline logging service — records step-by-step audit trail for enrichment runs.

Works with both async (FastAPI) and sync (Celery) sessions.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.pipeline_log import PipelineLog


# ── Async (FastAPI) ──────────────────────────────────────────────────────────


async def log_step(
    session: AsyncSession,
    request_id: uuid.UUID,
    step_name: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> PipelineLog:
    """Log a pipeline step execution."""
    log = PipelineLog(
        request_id=request_id,
        step_name=step_name,
        status=status,
        payload=payload,
    )
    session.add(log)
    await session.flush()
    return log


async def get_logs_for_request(
    session: AsyncSession,
    request_id: uuid.UUID,
) -> list[PipelineLog]:
    """Get all pipeline logs for a given request, ordered by timestamp."""
    result = await session.execute(
        select(PipelineLog)
        .where(PipelineLog.request_id == request_id)
        .order_by(PipelineLog.timestamp.asc())
    )
    return list(result.scalars().all())


# ── Sync (Celery Workers) ───────────────────────────────────────────────────


def log_step_sync(
    session: Session,
    request_id: uuid.UUID,
    step_name: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> PipelineLog:
    """Log a pipeline step execution (sync version for Celery)."""
    log = PipelineLog(
        request_id=request_id,
        step_name=step_name,
        status=status,
        payload=payload,
    )
    session.add(log)
    session.flush()
    return log


def get_logs_for_request_sync(
    session: Session,
    request_id: uuid.UUID,
) -> list[PipelineLog]:
    """Get all pipeline logs for a given request (sync)."""
    result = session.execute(
        select(PipelineLog)
        .where(PipelineLog.request_id == request_id)
        .order_by(PipelineLog.timestamp.asc())
    )
    return list(result.scalars().all())
