"""
Enrich API — POST /api/enrich

Accepts a company name, creates a lead, and dispatches
the Celery enrichment pipeline task.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.enrich import EnrichRequest, EnrichResponse
from app.services import lead_service
from app.tasks.enrichment import run_enrichment_pipeline

router = APIRouter(prefix="/api", tags=["enrich"])


@router.post(
    "/enrich",
    response_model=EnrichResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a company for enrichment",
    description="Queues an enrichment pipeline job and returns a request_id for tracking.",
)
async def enrich_company(
    payload: EnrichRequest,
    db: AsyncSession = Depends(get_db),
) -> EnrichResponse:
    """Accept an enrichment request and dispatch to the Celery pipeline."""
    request_id = uuid.uuid4()

    # Create lead record in pending state
    await lead_service.create_lead(
        session=db,
        request_id=request_id,
        raw_input=payload.model_dump(),
    )

    # Dispatch Celery task
    run_enrichment_pipeline.delay(
        request_id_str=str(request_id),
        raw_input=payload.model_dump(),
    )

    return EnrichResponse(
        request_id=request_id,
        status="accepted",
        message=f"Enrichment job queued. Track with request_id: {request_id}",
    )
