"""
FastAPI application entry point.

Mounts all API routers, WebSocket endpoints, CORS middleware,
and handles application lifespan events (pgvector init).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.admin import admin_views_router
from app.api import (
    admin_router,
    enrich_router,
    leads_router,
    pipeline_router,
    search_router,
    token_usage_router,
)
from app.api.ws import router as ws_router
from app.database import engine

logger = logging.getLogger(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — startup and shutdown events."""
    # ── Startup ──
    logger.info("Starting Leads Enrichment AI v2.0.0")

    # Ensure pgvector extension is available
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        logger.info("pgvector extension verified")
    except Exception as e:
        logger.warning(f"Could not create pgvector extension (may need superuser): {e}")

    yield

    # ── Shutdown ──
    logger.info("Shutting down Leads Enrichment AI")
    await engine.dispose()


app = FastAPI(
    title="Leads Enrichment AI",
    description="Consolidated Hybrid Resilience Pipeline v2 for Lead Enrichment",
    version="2.0.0",
    lifespan=lifespan,
)

# ── CORS Middleware (open for POC) ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount API Routers ──
app.include_router(enrich_router)
app.include_router(leads_router)
app.include_router(pipeline_router)
app.include_router(admin_router)
app.include_router(token_usage_router)
app.include_router(search_router)

# ── Mount WebSocket Router ──
app.include_router(ws_router)

# ── Mount Admin SSR Views ──
app.include_router(admin_views_router)

# ── Mount Static Files ──
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Health Check ──
@app.get("/health", tags=["system"])
async def health_check():
    """Basic health check endpoint."""
    return {"status": "ok", "version": "2.0.0"}
