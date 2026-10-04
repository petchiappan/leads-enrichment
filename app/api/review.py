"""
Human Review API — queue inspection and decision actions for leads.
"""

from __future__ import annotations

import uuid
from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.review import (
    ReviewActionIn,
    ReviewAuditOut,
    ReviewQueueItem,
    ReviewQueueListOut,
)
from app.services import review_service

router = APIRouter(prefix="/api/leads", tags=["review"])


@router.get(
    "/needs-review",
    response_model=ReviewQueueListOut,
    summary="List all leads needing human review",
)
async def list_needs_review(
    db: AsyncSession = Depends(get_db),
) -> ReviewQueueListOut:
    """Retrieve all leads currently flagged as needs_review."""
    leads = await review_service.get_leads_needing_review(db)
    items = []
    for lead in leads:
        conf = None
        if lead.enriched_data:
            conf = lead.enriched_data.get("fallback_confidence_score")

        company_name = (
            lead.raw_input.get("company_name", "Unknown")
            if lead.raw_input
            else "Unknown"
        )
        items.append(
            ReviewQueueItem(
                request_id=lead.request_id,
                company_name=company_name,
                status=lead.status,
                confidence_score=conf,
                created_at=lead.created_at,
                enriched_data=lead.enriched_data,
            )
        )

    return ReviewQueueListOut(items=items, total=len(items))


@router.post(
    "/{request_id}/approve",
    response_model=ReviewAuditOut,
    summary="Approve a lead",
)
async def approve_lead(
    request_id: uuid.UUID,
    payload: ReviewActionIn = Body(ReviewActionIn(action="approved")),
    db: AsyncSession = Depends(get_db),
) -> ReviewAuditOut:
    """Approve a low-confidence lead, changing its status to 'completed'."""
    try:
        audit = await review_service.review_lead(
            session=db,
            request_id=request_id,
            action="approved",
            reviewer=payload.reviewer,
            notes=payload.notes,
        )
        await db.commit()
        return ReviewAuditOut.model_validate(audit)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/{request_id}/reject",
    response_model=ReviewAuditOut,
    summary="Reject a lead",
)
async def reject_lead(
    request_id: uuid.UUID,
    payload: ReviewActionIn = Body(ReviewActionIn(action="rejected")),
    db: AsyncSession = Depends(get_db),
) -> ReviewAuditOut:
    """Reject a lead, changing its status to 'failed'."""
    try:
        audit = await review_service.review_lead(
            session=db,
            request_id=request_id,
            action="rejected",
            reviewer=payload.reviewer,
            notes=payload.notes,
        )
        await db.commit()
        return ReviewAuditOut.model_validate(audit)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post(
    "/{request_id}/re-enrich",
    response_model=ReviewAuditOut,
    summary="Re-enrich a lead",
)
async def re_enrich_lead(
    request_id: uuid.UUID,
    payload: ReviewActionIn = Body(ReviewActionIn(action="re_enriched")),
    db: AsyncSession = Depends(get_db),
) -> ReviewAuditOut:
    """Trigger immediate re-enrichment of a lead through the Celery pipeline."""
    try:
        audit = await review_service.review_lead(
            session=db,
            request_id=request_id,
            action="re_enriched",
            reviewer=payload.reviewer,
            notes=payload.notes,
        )
        await db.commit()
        return ReviewAuditOut.model_validate(audit)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.get(
    "/{request_id}/review-history",
    response_model=list[ReviewAuditOut],
    summary="Get review history for a lead",
)
async def get_review_history(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ReviewAuditOut]:
    """Retrieve chronological audit decisions for a specific lead."""
    audits = await review_service.get_review_history(db, request_id)
    return [ReviewAuditOut.model_validate(a) for a in audits]
