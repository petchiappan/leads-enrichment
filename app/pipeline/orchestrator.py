"""
Pipeline orchestrator — coordinates the 5-step enrichment pipeline.

Per skill_celery_pipeline.md execution order:
1. validate_input()
2. fetch_apis() — with tenacity, max 3 retries
3. evaluate_intelligence_gate()
4. If gaps → spawn_fallback_agent() | If no gaps → save_final_lineage()
5. save_final_lineage()

Each step is logged to pipeline_logs and broadcast via WebSocket.
"""

from __future__ import annotations

import logging
import traceback
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.pipeline import steps
from app.services import lead_service, pipeline_service

logger = logging.getLogger(__name__)

# Step names as constants (matches skill spec exactly)
STEP_VALIDATE_INPUT = "validate_input"
STEP_FETCH_APIS = "fetch_apis"
STEP_EVALUATE_INTELLIGENCE_GATE = "evaluate_intelligence_gate"
STEP_SPAWN_FALLBACK_AGENT = "spawn_fallback_agent"
STEP_SAVE_FINAL_LINEAGE = "save_final_lineage"


def run_pipeline(
    session: Session,
    request_id: uuid.UUID,
    raw_input: dict[str, Any],
) -> dict[str, Any]:
    """Execute the full enrichment pipeline for a lead.

    This runs synchronously inside a Celery worker.
    Each step is logged and errors are caught and recorded.

    Args:
        session: Synchronous database session.
        request_id: Unique identifier for this enrichment run.
        raw_input: The original POST payload.

    Returns:
        The final enriched_data dict.

    Raises:
        Exception: If any critical step fails.
    """
    logger.info(f"[{request_id}] ═══ Pipeline started ═══")

    # Update lead status to processing
    lead_service.update_lead_status_sync(session, request_id, "processing")
    session.commit()

    try:
        # ── Step 1: validate_input ──
        parsed_input = _run_step(
            session=session,
            request_id=request_id,
            step_name=STEP_VALIDATE_INPUT,
            step_fn=lambda: steps.validate_input(raw_input),
            payload_on_success=lambda result: {"validated": True, "company_name": result.company_name},
        )

        company_name = parsed_input.company_name
        company_domain = parsed_input.company_domain

        # ── Step 2: fetch_apis ──
        api_results = _run_step(
            session=session,
            request_id=request_id,
            step_name=STEP_FETCH_APIS,
            step_fn=lambda: steps.fetch_apis(company_name, company_domain),
            payload_on_success=lambda result: {
                "sources_queried": result.get("_api_sources_used", []),
                "errors": result.get("_api_errors", []),
                "fields_populated": [
                    k for k, v in result.items()
                    if not k.startswith("_") and v is not None
                ],
            },
        )

        # ── Step 3: evaluate_intelligence_gate ──
        gaps = _run_step(
            session=session,
            request_id=request_id,
            step_name=STEP_EVALUATE_INTELLIGENCE_GATE,
            step_fn=lambda: steps.evaluate_intelligence_gate(
                session, request_id, api_results, raw_input
            ),
            payload_on_success=lambda result: {
                "has_gaps": result is not None,
                "missing_fields": result.missing_fields if result else [],
            },
        )

        # ── Step 4: Branch — fallback or direct save ──
        fallback_result = None
        if gaps is not None:
            fallback_result = _run_step(
                session=session,
                request_id=request_id,
                step_name=STEP_SPAWN_FALLBACK_AGENT,
                step_fn=lambda: steps.spawn_fallback_agent(
                    session, request_id, company_name, gaps, api_results
                ),
                payload_on_success=lambda result: {
                    "confidence_score": result.confidence_score,
                    "sources_used": result.sources_used,
                    "fields_filled": [
                        k for k, v in result.model_dump().items()
                        if v is not None and k not in ("confidence_score", "sources_used", "company_name")
                    ],
                },
            )
        else:
            # Log that fallback was skipped
            pipeline_service.log_step_sync(
                session=session,
                request_id=request_id,
                step_name=STEP_SPAWN_FALLBACK_AGENT,
                status="skipped",
                payload={"reason": "No data gaps detected"},
            )
            session.commit()

        # ── Step 5: save_final_lineage ──
        final_data = _run_step(
            session=session,
            request_id=request_id,
            step_name=STEP_SAVE_FINAL_LINEAGE,
            step_fn=lambda: steps.save_final_lineage(
                session, request_id, api_results, fallback_result
            ),
            payload_on_success=lambda result: {
                "total_fields": len([k for k, v in result.items() if v is not None and not k.startswith("_")]),
                "had_fallback": result.get("_had_fallback", False),
            },
        )

        logger.info(f"[{request_id}] ═══ Pipeline completed successfully ═══")
        return final_data

    except Exception as e:
        # Mark lead as failed
        lead_service.update_lead_status_sync(session, request_id, "failed")
        session.commit()
        logger.error(f"[{request_id}] ═══ Pipeline FAILED ═══ {e}")
        raise


def _run_step(
    session: Session,
    request_id: uuid.UUID,
    step_name: str,
    step_fn,
    payload_on_success=None,
) -> Any:
    """Execute a pipeline step with logging wrapper.

    Logs 'started' before execution, then 'success' or 'failed' after.
    """
    logger.info(f"[{request_id}] Step: {step_name} → started")

    # Log started
    pipeline_service.log_step_sync(
        session=session,
        request_id=request_id,
        step_name=step_name,
        status="started",
    )
    session.commit()

    try:
        result = step_fn()

        # Log success
        payload = None
        if payload_on_success and result is not None:
            try:
                payload = payload_on_success(result)
            except Exception:
                payload = {"note": "Could not serialize step payload"}

        pipeline_service.log_step_sync(
            session=session,
            request_id=request_id,
            step_name=step_name,
            status="success",
            payload=payload,
        )
        session.commit()

        logger.info(f"[{request_id}] Step: {step_name} → success")
        return result

    except Exception as e:
        # Log failure
        pipeline_service.log_step_sync(
            session=session,
            request_id=request_id,
            step_name=step_name,
            status="failed",
            payload={
                "error": str(e),
                "traceback": traceback.format_exc()[-500:],
            },
        )
        session.commit()

        logger.error(f"[{request_id}] Step: {step_name} → FAILED: {e}")
        raise
