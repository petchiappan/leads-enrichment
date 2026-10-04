"""
Review Service — operations for the Human Review workflow.
"""

from __future__ import annotations

import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.review_audit import ReviewAudit
from app.tasks.enrichment import run_enrichment_pipeline


async def get_leads_needing_review(session: AsyncSession) -> list[Lead]:
    """Retrieve all leads currently in 'needs_review' status."""
    stmt = (
        select(Lead)
        .where(Lead.status == "needs_review")
        .order_by(Lead.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def review_lead(
    session: AsyncSession,
    request_id: uuid.UUID,
    action: str,
    reviewer: str | None = None,
    notes: str | None = None,
) -> ReviewAudit:
    """Apply a reviewer action (approved | rejected | re_enriched) to a lead."""
    stmt = select(Lead).where(Lead.request_id == request_id)
    result = await session.execute(stmt)
    lead = result.scalar_one_or_none()
    if lead is None:
        raise ValueError(f"Lead not found for request_id: {request_id}")

    if action == "approved":
        lead.status = "completed"
    elif action == "rejected":
        lead.status = "failed"
    elif action == "re_enriched":
        lead.status = "processing"
        run_enrichment_pipeline.delay(
            request_id_str=str(lead.request_id),
            raw_input=lead.raw_input,
        )
    else:
        raise ValueError(f"Unknown review action: {action}")

    audit = ReviewAudit(
        request_id=lead.request_id,
        action=action,
        reviewer=reviewer or "admin",
        notes=notes,
    )
    session.add(audit)
    await session.flush()
    return audit


async def get_review_history(
    session: AsyncSession,
    request_id: uuid.UUID,
) -> list[ReviewAudit]:
    """Fetch review history for a specific lead."""
    stmt = (
        select(ReviewAudit)
        .where(ReviewAudit.request_id == request_id)
        .order_by(ReviewAudit.created_at.desc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
