# Leads Enrichment AI — Consolidated Hybrid Resilience Pipeline v2

A production-grade lead enrichment system using a deterministic-first approach with AI-powered fallback agents.

## Architecture

```
POST /api/enrich → FastAPI → Celery Task Queue
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              Validate Input   Fetch APIs     LLM Intelligence
              (Pydantic)       (tenacity)     Gate (OpenAI)
                                                    │
                                          ┌─────────┼─────────┐
                                          ▼                    ▼
                                    Data Complete         Gaps Found
                                          │                    │
                                          ▼                    ▼
                                    Save Lineage      Fallback Agent
                                    (Postgres)        (OpenAI + Pydantic)
                                          │                    │
                                          ▼                    ▼
                                    Embed → pgvector     Merge & Save
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn, Gunicorn |
| Database | PostgreSQL + pgvector |
| Migrations | Alembic |
| Cache | Redis (toggleable via Admin) |
| Task Queue | Celery + Redis |
| AI/LLM | OpenAI API |
| Validation | Pydantic v2 |
| Admin UI | FastAPI + Jinja2 Templates |

## Quick Start

```bash
# 1. Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Copy and configure environment
copy .env.example .env
# Edit .env with your database and API credentials

# 4. Run migrations
alembic upgrade head

# 5. Start the server
uvicorn app.main:app --reload --port 8000
```

## Project Structure

```
app/
├── config.py          # Settings (pydantic-settings)
├── database.py        # Async SQLAlchemy engine & session
├── main.py            # FastAPI entry point
├── models/            # SQLAlchemy ORM models
├── schemas/           # Pydantic validation schemas
├── services/          # Business logic (Phase 2)
├── tasks/             # Celery workers (Phase 2)
├── api/               # FastAPI routers (Phase 2)
└── templates/         # Jinja2 Admin UI (Phase 2)
```
