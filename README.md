# Leads Enrichment AI — Production Hybrid Resilience Pipeline v2

An enterprise-grade, deterministic-first B2B lead enrichment platform featuring multi-source data ingestion, AI-powered fallback agents, and an end-to-end **AI Reliability Stack**.

---

## Architecture Overview

```
POST /api/enrich ──► Deduplication / Freshness Check ──(Cache Hit)──► Return Cached Lead (200 OK)
                             │
                        (Cache Miss)
                             ▼
                     Celery Task Queue (Redis)
                             │
     ┌───────────────────────┼───────────────────────┐
     ▼                       ▼                       ▼
Input Sanitisation      Multi-Source APIs      Intelligence Gate
(Injection/Length)     (Clearbit/Lusha/Hunter) (Prompt Registry vX.Y)
                             │                       │
                             └───────────┬───────────┘
                                         ▼
                                All Data Complete?
                                   /          \
                             (Yes)/            \(No - Gaps Found)
                                 ▼              ▼
                          Save Lineage     PII Redaction & Sanitisation
                          (Postgres)            │
                                 │              ▼
                                 │         Fallback Agent (LLM)
                                 │         (Prompt Registry vX.Y)
                                 │              │
                                 │              ▼
                                 │         Guardrails & Schema Validators
                                 │         (Confidence >= Threshold?)
                                 │              /       \
                                 │        (Yes)/         \(No - Low Confidence)
                                 │            ▼           ▼
                                 │     Merge Provenance  Flag for Human Review
                                 │     (Field Sources)   (status: needs_review)
                                 │            │           │
                                 └───────────┬┴───────────┘
                                             ▼
                                   Embeddings ──► pgvector
                                   Metrics    ──► Prometheus (/metrics)
                                   Logs       ──► JSON Structured Logs
```

---

## Key Capabilities & Recent Updates

### 1. Configurable AI Guardrails & Validation
- **Input Sanitisation:** Automatically strips prompt injection patterns, removes control characters, and caps company name length before processing.
- **Strict Schema Coercion:** Pydantic validators sanitize malformed emails, bare domains, out-of-range founding years (1800–present), placeholder strings (`"N/A"`, `"unknown"`), and negative employee counts into clean `None` values.
- **Dynamic Confidence Gating:** Validates LLM self-reported confidence against `admin_config` thresholds (`guardrail.min_confidence_threshold`). Leads falling below the threshold are routed to human review rather than failing silently.
- **Transient Failure Retries:** Tenacity exponential backoff retries for HTTP 429/5xx errors on external APIs, and Celery retries (30s, 60s, 120s) for transient LLM timeouts.

### 2. Runtime Prompt Versioning & Atomic Rollback
- **Database-Backed Prompt Registry:** System and gate prompts are stored with SemVer tags in `prompt_versions` table with in-memory TTL caching (60s) and fallback safety defaults.
- **Zero-Downtime Activation:** Activate new prompt versions or perform atomic rollbacks instantly via API or Admin UI without redeploying code.
- **Visual Diff Inspection:** Unified diff comparison between any prompt version and the active production version.
- **Lineage Attribution:** Every lead records `_prompt_versions` in its enriched payload and execution logs for full reproducibility.

### 3. Structured Observability & Metrics
- **JSON Structured Logging:** Standardized JSON formatting (`python-json-logger`) with automatic correlation `request_id` propagation across async FastAPI endpoints and Celery workers.
- **PII Scrubbing in Logs:** Contact data (emails, phone numbers) are masked with `[REDACTED_EMAIL]` and `[REDACTED_PHONE]` before database logging.
- **Prometheus Metrics Endpoint:** Scraping endpoint at `/metrics` tracking:
  - `enrichment_pipeline_total`: Pipeline execution counts partitioned by status.
  - `enrichment_pipeline_duration_seconds`: End-to-end pipeline latency histograms.
  - `llm_call_duration_seconds`: Individual LLM completion duration per step and model.
  - `llm_tokens_total`: Input and output token usage counters.
  - `api_call_errors_total`: Provider-specific failure counters (`clearbit`, `lusha`, `hunter`).
  - `guardrail_violations_total`: Flags triggered per field and rule.

### 4. Automated Evaluation Harness & Quality Gates
- **Golden Benchmark Dataset:** 20 production test cases covering happy path, partial API data, malformed fields, low confidence, API outages, and injection attempts.
- **Continuous Evaluation Engine:** Evaluator measuring fill rate, format error rate, anti-hallucination source verification, and confidence calibration.
- **CI Quality Gates:** Automated GitHub Actions workflow blocking merges if fill rate drops below 80% or format error rate exceeds 5%.

### 5. Advanced Enrichment Platform Features
- **Lead Deduplication:** Derives canonical company keys (normalizing domains and legal suffixes) and performs TTL-aware cache checks before queueing Celery tasks.
- **Field-Level Source Provenance:** `_field_provenance` metadata maps every enriched attribute to its source (`clearbit`, `lusha`, `hunter`, `google_news`, `llm_fallback`), rendered with visual badges in the Admin UI.
- **Data Freshness & Scheduled Re-enrichment:** Automatic `enriched_at` timestamp tracking paired with a daily Celery Beat scheduled task (`refresh_stale_leads`) to refresh leads past the freshness threshold.
- **Human Review Workflow:** Dedicated operational review queue for low-confidence results with Approve, Reject, and Re-enrich action triggers and an immutable `review_audit` trail.
- **PII Redaction Controls:** Configurable scrubbing of sensitive contact data prior to injecting third-party data into OpenAI fallback prompts.

---

## Tech Stack

| Component | Technology | Description |
|-----------|-----------|-------------|
| **Core Framework** | Python 3.11+, FastAPI, Uvicorn | Async REST API & WebSocket server |
| **Database** | PostgreSQL 16 + pgvector | Persistent store, audit logs, vector search |
| **ORM & Migrations**| SQLAlchemy 2.0 (async/sync), Alembic | Schema definition and migration history |
| **Distributed Queue**| Celery 5.4 + Redis 7 | Asynchronous worker tasks & Celery Beat scheduler |
| **AI / LLM** | OpenAI API (GPT-4o / GPT-4o-mini) | Intelligence gate evaluation, fallback extraction, embeddings |
| **Validation** | Pydantic v2 | Input validation, schema coercion, and guardrails |
| **Observability** | Prometheus Client, Python JSON Logger | Metrics scraping (`/metrics`) and structured logs |
| **Admin UI** | Jinja2 Templates, Vanilla JS & CSS | Server-side rendered administration portal |
| **Testing** | Pytest, Pytest-Asyncio, Pytest-Mock | 128 automated unit, integration, and quality tests |

---

## Quick Start

### 1. Local Environment Setup

```bash
# Clone and enter directory
cd leads_enrichment_ai

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux / macOS

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your PostgreSQL, Redis, and OpenAI API credentials

# Run database migrations
alembic upgrade head

# Start FastAPI development server
uvicorn app.main:app --reload --port 8000
```

### 2. Start Celery Worker & Beat Scheduler

```bash
# Start background worker
celery -A app.celery_app worker --loglevel=info -P solo

# Start periodic refresh scheduler (Beat)
celery -A app.celery_app beat --loglevel=info
```

### 3. Docker Compose (Full Stack)

```bash
docker compose up --build
```

---

## Key Endpoints & UI Pages

### Public & Admin Web Pages
- **Admin Dashboard:** [http://localhost:8000/admin/](http://localhost:8000/admin/) — Real-time KPIs, status counts, token consumption.
- **Human Review Queue:** [http://localhost:8000/admin/review](http://localhost:8000/admin/review) — Triage low-confidence leads with 1-click Approve / Reject / Re-enrich.
- **Prompt Management:** [http://localhost:8000/admin/prompts](http://localhost:8000/admin/prompts) — Create, activate, and inspect prompt version diffs.
- **Lead Detail & Provenance:** [http://localhost:8000/admin/leads/{request_id}](http://localhost:8000/admin/leads/{request_id}) — Field-level provenance badges, pipeline timeline, and token records.
- **Interactive API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs) (Swagger UI)

### REST & Operational Endpoints
- `POST /api/enrich` — Submit company for enrichment (supports deduplication & freshness check).
- `GET /api/leads/{request_id}` — Fetch enrichment status and enriched results.
- `GET /api/leads/needs-review` — Retrieve leads flagged for human review.
- `POST /api/leads/{request_id}/approve` — Approve lead and mark status as completed.
- `POST /api/leads/{request_id}/reject` — Reject lead and record rejection reason.
- `POST /api/leads/{request_id}/re-enrich` — Re-dispatch enrichment job.
- `GET /api/admin/prompts` — List all registered prompt versions.
- `POST /api/admin/prompts/{id}/activate` — Atomically activate a prompt version.
- `GET /api/admin/prompts/{id}/diff` — Compute unified diff against active version.
- `GET /metrics` — Prometheus metrics scraping endpoint.

---

## Running Automated Tests

The test suite covers guardrails, schema coercion, prompt registry caching, observability, deduplication, PII controls, human review workflows, and quality gates.

```bash
# Run all tests
pytest -v

# Run quality gate metrics test
pytest tests/test_quality_metrics.py -v

# Run with short tracebacks
pytest tests/ -v --tb=short
```

---

## Database Migrations

Database revisions are managed via Alembic:

| Revision | Description |
|----------|-------------|
| `001` | Initial schema: `leads`, `pipeline_logs`, `token_usage`, `admin_config` |
| `002` | Seed guardrail configuration thresholds (`guardrail.min_confidence_threshold`) |
| `003` | Create `prompt_versions` table and seed `v1.0.0` prompts |
| `004` | Seed observability and latency logging settings |
| `005` | Add `company_key`, `enriched_at`, create `review_audit` table, and seed freshness/dedup configs |

```bash
# Apply all pending migrations
alembic upgrade head

# Check current revision
alembic current
```

---

## Project Structure

```
leads_enrichment_ai/
├── alembic/                      # Database migration scripts (001 - 005)
├── app/
│   ├── admin/                    # Server-side rendered views for Admin UI
│   ├── api/                      # FastAPI endpoint routers (enrich, leads, review, prompts, metrics)
│   ├── models/                   # SQLAlchemy ORM models (Lead, PromptVersion, ReviewAudit, etc.)
│   ├── pipeline/                 # Core enrichment pipeline
│   │   ├── context.py            # ContextVar request correlation ID propagation
│   │   ├── fallback_agent.py     # LLM extraction agent with prompt versioning
│   │   ├── guardrails.py         # Input sanitisation, confidence checks, PII redaction
│   │   ├── orchestrator.py       # Pipeline step orchestrator
│   │   ├── prompt_registry.py    # Runtime prompt caching & fallback safety registry
│   │   └── steps.py              # Ingestion, fallback gate, merging, provenance
│   ├── schemas/                  # Pydantic models & validation rules
│   ├── services/                 # Business logic services (lead, prompt, review, token, observability)
│   ├── tasks/                    # Celery asynchronous tasks (enrichment, refresh)
│   ├── templates/                # Jinja2 HTML templates for Admin UI
│   ├── metrics.py                # Standalone Prometheus metric definitions
│   ├── celery_app.py             # Celery worker and Celery Beat periodic schedule configuration
│   ├── config.py                 # Application settings (pydantic-settings)
│   ├── database.py               # Async & sync database engine and session factories
│   └── main.py                   # FastAPI application initialization & middleware
├── tests/                        # Comprehensive test suite (128 passing tests)
│   ├── fixtures/golden_leads.json # 20 golden benchmark evaluation leads
│   ├── test_admin_views.py       # Admin UI SSR rendering tests
│   ├── test_dedup_and_provenance.py # Deduplication & source provenance tests
│   ├── test_guardrails.py        # Input sanitisation & confidence threshold tests
│   ├── test_observability.py     # JSON logging & Prometheus metrics tests
│   ├── test_pii_controls.py      # Sensitive data redaction tests
│   ├── test_pipeline_integration.py # End-to-end integration tests
│   ├── test_prompt_registry.py   # Dynamic prompt caching & activation tests
│   ├── test_quality_metrics.py   # Golden dataset evaluation & CI quality gate tests
│   └── test_validators.py        # Schema coercion & boundary condition tests
├── .github/workflows/ci.yml      # Continuous Integration quality gate workflow
├── docker-compose.yml            # Multi-container orchestration (web, worker, beat, postgres, redis)
├── Dockerfile                    # Container definition
├── requirements.txt              # Production and testing Python dependencies
└── README.md                     # Project documentation
```
