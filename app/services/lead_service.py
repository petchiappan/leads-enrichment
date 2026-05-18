"""
Lead CRUD service — create, read, update lead records.

Works with both async (FastAPI) and sync (Celery) sessions.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.lead import Lead


# ── Async (FastAPI) ──────────────────────────────────────────────────────────


async def create_lead(
    session: AsyncSession,
    request_id: uuid.UUID,
    raw_input: dict[str, Any],
) -> Lead:
    """Create a new lead record with pending status."""
    lead = Lead(
        request_id=request_id,
        raw_input=raw_input,
        status="pending",
    )
    session.add(lead)
    await session.flush()
    return lead


async def get_lead_by_request_id(
    session: AsyncSession,
    request_id: uuid.UUID,
) -> Lead | None:
    """Fetch a lead by its request_id."""
    result = await session.execute(
        select(Lead).where(Lead.request_id == request_id)
    )
    return result.scalar_one_or_none()


async def get_lead_by_id(
    session: AsyncSession,
    lead_id: uuid.UUID,
) -> Lead | None:
    """Fetch a lead by its primary key."""
    result = await session.execute(
        select(Lead).where(Lead.id == lead_id)
    )
    return result.scalar_one_or_none()


async def list_leads(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 50,
    status: str | None = None,
) -> tuple[list[Lead], int]:
    """List leads with pagination and optional status filter."""
    query = select(Lead).order_by(Lead.created_at.desc())
    count_query = select(func.count()).select_from(Lead)

    if status:
        query = query.where(Lead.status == status)
        count_query = count_query.where(Lead.status == status)

    total_result = await session.execute(count_query)
    total = total_result.scalar_one()

    result = await session.execute(query.offset(skip).limit(limit))
    leads = list(result.scalars().all())
    return leads, total


async def update_lead_status(
    session: AsyncSession,
    request_id: uuid.UUID,
    status: str,
    enriched_data: dict[str, Any] | None = None,
) -> Lead | None:
    """Update lead status and optionally set enriched_data."""
    lead = await get_lead_by_request_id(session, request_id)
    if lead is None:
        return None
    lead.status = status
    if enriched_data is not None:
        lead.enriched_data = enriched_data
    await session.flush()
    return lead


# ── Sync (Celery Workers) ───────────────────────────────────────────────────


def create_lead_sync(
    session: Session,
    request_id: uuid.UUID,
    raw_input: dict[str, Any],
) -> Lead:
    """Create a new lead record (sync version for Celery)."""
    lead = Lead(
        request_id=request_id,
        raw_input=raw_input,
        status="pending",
    )
    session.add(lead)
    session.flush()
    return lead


def get_lead_by_request_id_sync(
    session: Session,
    request_id: uuid.UUID,
) -> Lead | None:
    """Fetch a lead by its request_id (sync)."""
    result = session.execute(
        select(Lead).where(Lead.request_id == request_id)
    )
    return result.scalar_one_or_none()


def update_lead_status_sync(
    session: Session,
    request_id: uuid.UUID,
    status: str,
    enriched_data: dict[str, Any] | None = None,
) -> Lead | None:
    """Update lead status (sync version for Celery)."""
    lead = get_lead_by_request_id_sync(session, request_id)
    if lead is None:
        return None
    lead.status = status
    if enriched_data is not None:
        lead.enriched_data = enriched_data
    session.flush()
    return lead
