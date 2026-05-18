"""
Admin Dashboard — SSR route handlers.

All pages rendered server-side via Jinja2Templates.TemplateResponse().
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead import Lead
from app.models.pipeline_log import PipelineLog
from app.models.token_usage import TokenUsage
from app.services import admin_service, embedding_service, lead_service, pipeline_service, token_service

router = APIRouter(prefix="/admin", tags=["admin-ui"])

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


# ── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/", include_in_schema=False)
async def dashboard(request: Request, db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(select(func.count()).select_from(Lead))
    total = total_result.scalar_one()

    counts = {}
    for s in ("pending", "processing", "completed", "failed"):
        r = await db.execute(select(func.count()).select_from(Lead).where(Lead.status == s))
        counts[s] = r.scalar_one()

    recent_result = await db.execute(select(Lead).order_by(Lead.created_at.desc()).limit(10))
    recent_leads = list(recent_result.scalars().all())

    token_summary = await token_service.get_usage_summary(db)

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "current_page": "dashboard",
        "total_leads": total, "counts": counts,
        "recent_leads": recent_leads, "token_summary": token_summary,
    })


# ── Leads List ───────────────────────────────────────────────────────────────

@router.get("/leads", include_in_schema=False)
async def leads_list(
    request: Request,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    db: AsyncSession = Depends(get_db),
):
    per_page = 20
    skip = (page - 1) * per_page
    leads, total = await lead_service.list_leads(db, skip=skip, limit=per_page, status=status)
    total_pages = max(1, (total + per_page - 1) // per_page)

    return templates.TemplateResponse("leads.html", {
        "request": request, "current_page": "leads",
        "leads": leads, "total": total,
        "page": page, "total_pages": total_pages,
        "status_filter": status,
    })


# ── Lead Detail ──────────────────────────────────────────────────────────────

@router.get("/leads/{request_id}", include_in_schema=False)
async def lead_detail(request: Request, request_id: str, db: AsyncSession = Depends(get_db)):
    rid = uuid.UUID(request_id)
    lead = await lead_service.get_lead_by_request_id(db, rid)
    logs = await pipeline_service.get_logs_for_request(db, rid) if lead else []
    tokens = await token_service.get_usage_by_request(db, rid) if lead else []

    return templates.TemplateResponse("lead_detail.html", {
        "request": request, "current_page": "leads",
        "lead": lead, "pipeline_logs": logs, "token_records": tokens,
    })


# ── Pipeline Runs ────────────────────────────────────────────────────────────

@router.get("/pipeline", include_in_schema=False)
async def pipeline_runs(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Lead).where(Lead.status.in_(["processing", "completed", "failed"]))
        .order_by(Lead.created_at.desc()).limit(50)
    )
    runs = list(result.scalars().all())

    # Get log counts per request
    run_data = []
    for run in runs:
        logs = await pipeline_service.get_logs_for_request(db, run.request_id)
        run_data.append({"lead": run, "logs": logs, "step_count": len(logs)})

    return templates.TemplateResponse("pipeline.html", {
        "request": request, "current_page": "pipeline",
        "runs": run_data,
    })


# ── Token Usage ──────────────────────────────────────────────────────────────

@router.get("/tokens", include_in_schema=False)
async def tokens_page(request: Request, db: AsyncSession = Depends(get_db)):
    summary = await token_service.get_usage_summary(db)
    return templates.TemplateResponse("tokens.html", {
        "request": request, "current_page": "tokens",
        "summary": summary,
    })


# ── Semantic Search ──────────────────────────────────────────────────────────

@router.get("/search", include_in_schema=False)
async def search_page(request: Request):
    return templates.TemplateResponse("search.html", {
        "request": request, "current_page": "search",
    })


# ── Settings ─────────────────────────────────────────────────────────────────

@router.get("/settings", include_in_schema=False)
async def settings_page(request: Request, db: AsyncSession = Depends(get_db)):
    configs = await admin_service.get_all_configs(db)
    return templates.TemplateResponse("settings.html", {
        "request": request, "current_page": "settings",
        "configs": configs,
    })


# ── Enrich Form ──────────────────────────────────────────────────────────────

@router.get("/enrich", include_in_schema=False)
async def enrich_page(request: Request):
    return templates.TemplateResponse("enrich.html", {
        "request": request, "current_page": "enrich",
    })
