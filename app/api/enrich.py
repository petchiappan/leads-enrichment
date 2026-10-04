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
    # Check deduplication cache if enabled
    try:
        from app.services import admin_service
        dedup_cfg = await admin_service.get_config(db, "enrichment.dedup_enabled")
        dedup_enabled = dedup_cfg.setting_value.lower() == "true" if dedup_cfg else True

        if dedup_enabled:
            ttl_cfg = await admin_service.get_config(db, "enrichment.freshness_ttl_days")
            ttl_days = int(ttl_cfg.setting_value) if ttl_cfg and ttl_cfg.setting_value.isdigit() else 30

            company_key = lead_service.compute_company_key(payload.company_name, payload.company_domain)
            fresh_lead = await lead_service.find_fresh_lead(db, company_key, max_age_days=ttl_days)

            if fresh_lead is not None:
                return EnrichResponse(
                    request_id=fresh_lead.request_id,
                    status="cached",
                    message=f"Fresh enrichment record reused. Original request_id: {fresh_lead.request_id}",
                    cached=True,
                    cached_since=fresh_lead.enriched_at.isoformat() if fresh_lead.enriched_at else None,
                )
    except Exception:
        # Fall back to normal pipeline dispatch on any config/dedup query issue
        pass

    request_id = uuid.uuid4()

    # Create lead record in pending state
    await lead_service.create_lead(
        session=db,
        request_id=request_id,
        raw_input=payload.model_dump(),
    )

    # Dispatch Celery task
    from app.tasks.enrichment import run_enrichment_pipeline

    run_enrichment_pipeline.delay(
        request_id_str=str(request_id),
        raw_input=payload.model_dump(),
    )

    return EnrichResponse(
        request_id=request_id,
        status="accepted",
        message=f"Enrichment job queued. Track with request_id: {request_id}",
        cached=False,
        cached_since=None,
    )

