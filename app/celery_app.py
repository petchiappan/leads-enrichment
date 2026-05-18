"""
Celery application instance.

Configured with Redis broker and result backend.
Auto-discovers tasks from app.tasks package.
"""

from __future__ import annotations

from celery import Celery

from app.config import settings

celery_app = Celery("leads_enrichment")

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_default_queue="enrichment",
    task_routes={
        "app.tasks.enrichment.run_enrichment_pipeline": {"queue": "enrichment"},
    },
    imports=["app.tasks.enrichment"],
)
