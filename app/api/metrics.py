"""
Prometheus metrics endpoint.

Exposes /metrics endpoint for Prometheus scraping.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    generate_latest,
)

# Re-export metrics definitions for backwards compatibility
from app.metrics import (
    api_call_errors_total,
    guardrail_violations_total,
    llm_call_duration_seconds,
    llm_tokens_total,
    pipeline_duration_seconds,
    pipeline_runs_total,
)

router = APIRouter(tags=["metrics"])


@router.get("/metrics", summary="Prometheus Metrics Endpoint", include_in_schema=False)
def metrics() -> Response:
    """Generate and return current Prometheus metrics."""
    return Response(
        content=generate_latest(REGISTRY),
        media_type=CONTENT_TYPE_LATEST,
    )
