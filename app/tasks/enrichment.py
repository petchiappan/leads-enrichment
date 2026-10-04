"""
Celery task: run_enrichment_pipeline

Entry point triggered by POST /api/enrich.
Runs the full 5-step enrichment pipeline inside a Celery worker.

Phase 1 changes:
  - max_retries raised from 0 → 3 (transient errors are retried)
  - Exponential countdown: 30s → 60s → 120s
  - ValidationError is NOT retried (permanent input failure)
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from pydantic import ValidationError

from app import metrics
from app.celery_app import celery_app
from app.database import sync_session_factory
from app.pipeline import context
from app.pipeline.orchestrator import run_pipeline
from app.services import lead_service

logger = logging.getLogger(__name__)



@celery_app.task(
    name="app.tasks.enrichment.run_enrichment_pipeline",
    bind=True,
    max_retries=3,          # Phase 1: was 0 — transient failures now retried
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

    Retry policy (Phase 1):
      - Retries up to 3 times for transient errors (network, OpenAI rate limits).
      - Countdown doubles each attempt: 30s, 60s, 120s.
      - ValidationError is never retried — it is a permanent input failure.

    Args:
        request_id_str: UUID string identifying this enrichment request.
        raw_input: The original EnrichRequest payload as a dict.

    Returns:
        The final enriched_data dict.
    """
    request_id = uuid.UUID(request_id_str)
    context.set_request_id(request_id_str)
    start_time = time.perf_counter()

    logger.info(
        "[Celery] Starting enrichment pipeline for request_id=%s (attempt=%d/%d)",
        request_id,
        self.request.retries + 1,
        self.max_retries + 1,
    )

    session = sync_session_factory()
    try:
        result = run_pipeline(
            session=session,
            request_id=request_id,
            raw_input=raw_input,
        )
        session.commit()

        duration_s = time.perf_counter() - start_time
        lead = lead_service.get_lead_by_request_id_sync(session, request_id)
        lead_status = lead.status if lead else "completed"

        try:
            metrics.pipeline_duration_seconds.observe(duration_s)
            metrics.pipeline_runs_total.labels(status=lead_status).inc()
        except Exception:
            pass

        logger.info(
            "[Celery] Pipeline completed in %.3fs for request_id=%s (status=%s)",
            duration_s,
            request_id,
            lead_status,
        )
        return result

    except Exception as e:
        session.rollback()
        try:
            metrics.pipeline_runs_total.labels(status="failed").inc()
        except Exception:
            pass
        logger.error("[Celery] Pipeline FAILED for request_id=%s: %s", request_id, e)


        # Ensure lead is marked as failed (best-effort)
        try:
            lead_service.update_lead_status_sync(session, request_id, "failed")
            session.commit()
        except Exception:
            session.rollback()

        # Phase 1: Retry logic
        # Do NOT retry permanent failures (bad input validation).
        # DO retry transient failures (OpenAI rate limits, network timeouts, etc.)
        if isinstance(e, ValidationError):
            logger.error(
                "[Celery] ValidationError is permanent — not retrying request_id=%s",
                request_id,
            )
            raise

        # Exponential backoff: 30s * 2^attempt  (30, 60, 120)
        countdown = 30 * (2 ** self.request.retries)
        logger.warning(
            "[Celery] Scheduling retry %d/%d for request_id=%s in %ds",
            self.request.retries + 1,
            self.max_retries,
            request_id,
            countdown,
        )
        raise self.retry(exc=e, countdown=countdown)

    finally:
        session.close()
