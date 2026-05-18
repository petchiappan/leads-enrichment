"""
Pipeline API — retrieve step-by-step execution logs for an enrichment run.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.pipeline import PipelineLogListOut, PipelineLogOut
from app.services import pipeline_service

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.get(
    "/pipeline/{request_id}",
    response_model=PipelineLogListOut,
    summary="Get pipeline execution logs",
    description="Returns the step-by-step audit trail for a specific enrichment run.",
)
async def get_pipeline_logs(
    request_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> PipelineLogListOut:
    """Retrieve all pipeline logs for a given request_id."""
    logs = await pipeline_service.get_logs_for_request(db, request_id)
    if not logs:
        raise HTTPException(
            status_code=404,
            detail=f"No pipeline logs found for request_id: {request_id}",
        )
    return PipelineLogListOut(
        request_id=request_id,
        steps=[PipelineLogOut.model_validate(log) for log in logs],
        total=len(logs),
    )
