"""
Celery periodic task: refresh_stale_leads

Queries leads whose enriched data has passed the freshness TTL and re-enriches them.
Scheduled via Celery Beat or triggered on-demand.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.celery_app import celery_app
from app.database import sync_session_factory
from app.models.admin_config import AdminConfig
from app.models.lead import Lead
from app.tasks.enrichment import run_enrichment_pipeline

logger = logging.getLogger(__name__)

DEFAULT_FRESHNESS_DAYS = 30


@celery_app.task(
    name="app.tasks.refresh.refresh_stale_leads",
    bind=True,
    max_retries=1,
)
def refresh_stale_leads(self) -> dict[str, int]:
    """Identify stale completed leads and trigger background re-enrichment."""
    session = sync_session_factory()
    try:
        # Read freshness TTL from admin_config
        ttl_row = session.execute(
            select(AdminConfig).where(AdminConfig.setting_key == "enrichment.freshness_ttl_days")
        ).scalar_one_or_none()

        freshness_days = (
            int(ttl_row.setting_value)
            if ttl_row and ttl_row.setting_value.isdigit()
            else DEFAULT_FRESHNESS_DAYS
        )

        cutoff = datetime.now(timezone.utc) - timedelta(days=freshness_days)

        # Query completed leads older than the cutoff
        stmt = (
            select(Lead)
            .where(
                Lead.status == "completed",
                (Lead.enriched_at.is_not(None) & (Lead.enriched_at < cutoff))
                | (Lead.enriched_at.is_(None) & (Lead.updated_at < cutoff)),
            )
            .limit(50)  # batch size
        )
        stale_leads = list(session.execute(stmt).scalars().all())

        dispatched = 0
        for lead in stale_leads:
            logger.info(
                "[refresh_stale_leads] Re-enriching stale lead request_id=%s (company_key=%s)",
                lead.request_id,
                lead.company_key,
            )
            run_enrichment_pipeline.delay(
                request_id_str=str(lead.request_id),
                raw_input=lead.raw_input,
            )
            dispatched += 1

        logger.info("[refresh_stale_leads] Dispatched %d stale leads for re-enrichment", dispatched)
        return {"refreshed_count": dispatched}

    except Exception as exc:
        logger.error("[refresh_stale_leads] Error scanning for stale leads: %s", exc)
        raise
    finally:
        session.close()
