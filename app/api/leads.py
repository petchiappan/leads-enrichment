"""
Leads API — list and retrieve enriched lead records.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.lead import LeadListOut, LeadOut
from app.services import lead_service

router = APIRouter(prefix="/api", tags=["leads"])


@router.get(
    "/leads",
    response_model=LeadListOut,
    summary="List all leads",
    description="Returns a paginated list of leads, optionally filtered by status.",
)
async def list_leads(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    status: str | None = Query(None, description="Filter by status (pending/processing/completed/failed)"),
    db: AsyncSession = Depends(get_db),
) -> LeadListOut:
    """List leads with pagination and optional status filter."""
    leads, total = await lead_service.list_leads(db, skip=skip, limit=limit, status=status)
    return LeadListOut(
        leads=[LeadOut.model_validate(lead) for lead in leads],
        total=total,
    )


@router.get(
    "/leads/{request_id}",
    response_model=LeadOut,
    summary="Get a single lead by request_id",
    description="Returns the full lead record including enriched data.",
)
async def get_lead(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> LeadOut:
    """Retrieve a single lead by its request_id."""
    lead = await lead_service.get_lead_by_request_id(db, request_id)
    if lead is None:
        raise HTTPException(status_code=404, detail=f"Lead not found: {request_id}")
    return LeadOut.model_validate(lead)
