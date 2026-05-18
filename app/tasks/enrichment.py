"""
Celery task: run_enrichment_pipeline

Entry point triggered by POST /api/enrich.
Runs the full 5-step enrichment pipeline inside a Celery worker.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.celery_app import celery_app
from app.database import sync_session_factory
from app.pipeline.orchestrator import run_pipeline
from app.services import lead_service

logger = logging.getLogger(__name__)


@celery_app.task(
    name="app.tasks.enrichment.run_enrichment_pipeline",
    bind=True,
    max_retries=0,
    acks_late=True,
    track_started=True,
)
def run_enrichment_pipeline(
    self,
    request_id_str: str,
    raw_input: dict[str, Any],
) -> dict[str, Any]:
    """Execute the enrichment pipeline for a single lead.

    This is the main Celery task dispatched by the /api/enrich endpoint.
    Uses a synchronous database session since Celery workers don't run
    an async event loop.

    Args:
        request_id_str: UUID string identifying this enrichment request.
        raw_input: The original EnrichRequest payload as a dict.

    Returns:
        The final enriched_data dict.
    """
    request_id = uuid.UUID(request_id_str)

    logger.info(f"[Celery] Starting enrichment pipeline for request_id={request_id}")

    session = sync_session_factory()
    try:
        result = run_pipeline(
            session=session,
            request_id=request_id,
            raw_input=raw_input,
        )
        session.commit()
        logger.info(f"[Celery] Pipeline completed for request_id={request_id}")
        return result

    except Exception as e:
        session.rollback()
        logger.error(f"[Celery] Pipeline FAILED for request_id={request_id}: {e}")

        # Ensure lead is marked as failed
        try:
            lead_service.update_lead_status_sync(session, request_id, "failed")
            session.commit()
        except Exception:
            session.rollback()

        raise

    finally:
        session.close()
