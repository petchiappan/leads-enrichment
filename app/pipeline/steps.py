"""
Pipeline step implementations — individual functions for each enrichment step.

Per skill_celery_pipeline.md execution order:
1. validate_input()
2. fetch_apis() — with tenacity, max 3 retries
3. evaluate_intelligence_gate()
4. spawn_fallback_agent() (if gaps exist)
5. save_final_lineage()
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

import httpx
from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app import metrics
from app.config import settings
from app.pipeline import prompt_registry
from app.pipeline.fallback_agent import run_fallback
from app.pipeline.guardrails import check_confidence, sanitise_input
from app.schemas.enrich import EnrichRequest
from app.schemas.fallback import AgenticExtractionResult, MissingGapsRequest
from app.services import embedding_service, lead_service, token_service
from app.services.observability import timed_llm_call



logger = logging.getLogger(__name__)


# ── Step 1: validate_input ──────────────────────────────────────────────────


def validate_input(raw_input: dict[str, Any]) -> EnrichRequest:
    """Validate and sanitise the raw input against the EnrichRequest Pydantic schema.

    Phase 1: company_name is sanitised against prompt injection and control
    characters before Pydantic validation.

    Returns parsed EnrichRequest or raises ValidationError.
    """
    # Sanitise company_name before validation (no DB session needed — uses defaults)
    if isinstance(raw_input.get("company_name"), str):
        raw_input = dict(raw_input)  # don't mutate the original
        raw_input["company_name"] = sanitise_input(raw_input["company_name"])

    return EnrichRequest.model_validate(raw_input)


# ── Step 2: fetch_apis ─────────────────────────────────────────────────────


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    reraise=True,
)
def _call_api(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Make a single API call with tenacity retry (3 attempts per skill spec).

    Phase 1: 429 (rate limit) and 5xx (server error) responses are now treated
    as retryable by raising httpx.HTTPError before raise_for_status is called.
    Previously these were HTTPStatusError and were NOT caught by tenacity.
    """
    with httpx.Client(timeout=timeout) as client:
        response = client.get(url, params=params, headers=headers)
        # Treat rate-limit and server errors as transient — tenacity will retry
        if response.status_code == 429 or response.status_code >= 500:
            raise httpx.HTTPError(
                f"Retryable HTTP status {response.status_code} from {url}"
            )
        response.raise_for_status()
        return response.json()


def _fetch_google_news(company_name: str) -> dict[str, Any]:
    """Fetch news articles about the company via Google News / NewsAPI."""
    if not settings.GOOGLE_NEWS_API_KEY:
        logger.info("Google News API key not configured — skipping")
        return {"news_articles": None, "_source": "google_news", "_skipped": True}

    try:
        data = _call_api(
            url=settings.GOOGLE_NEWS_API_URL,
            params={
                "q": company_name,
                "apiKey": settings.GOOGLE_NEWS_API_KEY,
                "pageSize": 5,
                "sortBy": "relevancy",
                "language": "en",
            },
        )
        articles = [
            article.get("title", article.get("url", ""))
            for article in data.get("articles", [])
        ]
        return {"news_articles": articles, "_source": "google_news"}
    except Exception as e:
        logger.warning(f"Google News API failed: {e}")
        metrics.api_call_errors_total.labels(source="google_news").inc()
        return {"news_articles": None, "_source": "google_news", "_error": str(e)}


def _fetch_lusha(company_name: str, company_domain: str | None) -> dict[str, Any]:
    """Fetch contact information via Lusha API."""
    if not settings.LUSHA_API_KEY:
        logger.info("Lusha API key not configured — skipping")
        return {"_source": "lusha", "_skipped": True}

    try:
        params: dict[str, Any] = {"company": company_name}
        if company_domain:
            params["domain"] = company_domain

        data = _call_api(
            url=settings.LUSHA_API_URL,
            params=params,
            headers={"api_key": settings.LUSHA_API_KEY},
        )
        return {
            "ceo_name": data.get("fullName"),
            "ceo_email": data.get("emailAddresses", [{}])[0].get("email")
            if data.get("emailAddresses")
            else None,
            "linkedin_url": data.get("socialNetworks", {}).get("linkedin"),
            "_source": "lusha",
        }
    except Exception as e:
        logger.warning(f"Lusha API failed: {e}")
        metrics.api_call_errors_total.labels(source="lusha").inc()
        return {"_source": "lusha", "_error": str(e)}


def _fetch_clearbit(company_name: str, company_domain: str | None) -> dict[str, Any]:
    """Fetch company enrichment data via Clearbit API."""
    if not settings.CLEARBIT_API_KEY:
        logger.info("Clearbit API key not configured — skipping")
        return {"_source": "clearbit", "_skipped": True}

    try:
        params: dict[str, Any] = {}
        if company_domain:
            params["domain"] = company_domain
        else:
            params["name"] = company_name

        data = _call_api(
            url=settings.CLEARBIT_API_URL,
            params=params,
            headers={"Authorization": f"Bearer {settings.CLEARBIT_API_KEY}"},
        )
        return {
            "company_name": data.get("name", company_name),
            "company_description": data.get("description"),
            "company_website": data.get("url"),
            "linkedin_company_url": data.get("linkedin", {}).get("handle"),
            "employee_count": data.get("metrics", {}).get("employees"),
            "industry": data.get("category", {}).get("industry"),
            "founding_year": data.get("foundedYear"),
            "funding_raised": data.get("metrics", {}).get("raised"),
            "_source": "clearbit",
        }
    except Exception as e:
        logger.warning(f"Clearbit API failed: {e}")
        metrics.api_call_errors_total.labels(source="clearbit").inc()
        return {"_source": "clearbit", "_error": str(e)}


def _fetch_hunter(company_domain: str | None) -> dict[str, Any]:
    """Fetch email data via Hunter.io API."""
    if not settings.HUNTER_API_KEY or not company_domain:
        logger.info("Hunter API key or domain not available — skipping")
        return {"_source": "hunter", "_skipped": True}

    try:
        data = _call_api(
            url=settings.HUNTER_API_URL,
            params={
                "domain": company_domain,
                "api_key": settings.HUNTER_API_KEY,
            },
        )
        emails_data = data.get("data", {}).get("emails", [])
        ceo_email = None
        for email_entry in emails_data:
            if email_entry.get("type") == "personal" or email_entry.get("position", "").lower() in (
                "ceo", "chief executive officer", "founder"
            ):
                ceo_email = email_entry.get("value")
                break

        return {
            "ceo_email": ceo_email,
            "_source": "hunter",
        }
    except Exception as e:
        logger.warning(f"Hunter.io API failed: {e}")
        metrics.api_call_errors_total.labels(source="hunter").inc()
        return {"_source": "hunter", "_error": str(e)}



def fetch_apis(
    company_name: str,
    company_domain: str | None = None,
) -> dict[str, Any]:
    """Fetch data from all configured external APIs.

    Merges results from Google News, Lusha, Clearbit, and Hunter.io.
    Non-None values from later sources override earlier ones.
    """
    merged: dict[str, Any] = {"company_name": company_name}
    sources_used: list[str] = []
    api_errors: list[dict] = []

    # Call each API and merge results
    fetchers = [
        ("clearbit", _fetch_clearbit(company_name, company_domain)),
        ("lusha", _fetch_lusha(company_name, company_domain)),
        ("hunter", _fetch_hunter(company_domain)),
        ("google_news", _fetch_google_news(company_name)),
    ]

    provenance: dict[str, str] = {"company_name": "input"}

    for source_name, result in fetchers:
        if result.get("_error"):
            api_errors.append({"source": source_name, "error": result["_error"]})
        if not result.get("_skipped"):
            sources_used.append(source_name)

        # Merge non-None, non-private values
        for key, value in result.items():
            if not key.startswith("_") and value is not None:
                merged[key] = value
                provenance[key] = source_name

    merged["_api_sources_used"] = sources_used
    merged["_api_errors"] = api_errors
    merged["_field_provenance"] = provenance


    logger.info(
        f"fetch_apis complete: {len(sources_used)} sources queried, "
        f"{len(api_errors)} errors"
    )

    return merged


# ── Step 3: evaluate_intelligence_gate ──────────────────────────────────────


# All fields from AgenticExtractionResult that we check for completeness
_ENRICHMENT_FIELDS = [
    "company_name", "ceo_name", "ceo_email", "company_description",
    "linkedin_url", "linkedin_company_url", "employee_count",
    "company_website", "funding_raised", "industry", "founding_year",
    "news_articles",
]


def evaluate_intelligence_gate(
    session: Session,
    request_id: uuid.UUID,
    api_results: dict[str, Any],
    raw_input: dict[str, Any],
) -> MissingGapsRequest | None:
    """Fast LLM check to determine if data gaps exist.

    Uses OpenAI to evaluate completeness of the gathered data.
    Returns MissingGapsRequest if gaps exist, None if data is complete.
    """
    # First, do a simple field-level check
    missing_fields = [
        field for field in _ENRICHMENT_FIELDS
        if not api_results.get(field)
    ]

    if not missing_fields:
        logger.info(f"[{request_id}] Intelligence gate: all fields populated, no gaps")
        return None

    # If we have the OpenAI key, use LLM to evaluate if the gaps are critical
    if settings.OPENAI_API_KEY:
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)

            active_prompt = prompt_registry.get_active_prompt(
                "intelligence_gate_prompt",
                environment=settings.APP_ENV,
                session=session,
            )

            # Phase 5: sanitize api_results to prevent leaking PII into gate prompt
            from app.pipeline.guardrails import redact_pii_from_dict
            sanitized_api_results = redact_pii_from_dict(api_results, session=session)

            gate_prompt = (
                f"Given this partial company data:\n"
                f"```json\n{json.dumps(sanitized_api_results, indent=2, default=str)}\n```\n\n"
                f"The following fields are missing: {', '.join(missing_fields)}\n\n"
                f"Respond with JSON: {{\"missing_fields\": [list of field names that are truly missing "
                f"and important], \"assessment\": \"brief explanation\"}}"
            )

            response, duration_s = timed_llm_call(
                client=client,
                step_name="evaluate_intelligence_gate",

                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": active_prompt.content,
                    },
                    {"role": "user", "content": gate_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_tokens=500,
            )

            # Record token usage
            usage = response.usage
            if usage:
                token_service.record_usage_sync(
                    session=session,
                    request_id=request_id,
                    model_name=settings.OPENAI_MODEL,
                    input_tokens=usage.prompt_tokens,
                    output_tokens=usage.completion_tokens,
                    step_name="evaluate_intelligence_gate",
                )

            gate_result = json.loads(response.choices[0].message.content)

            confirmed_missing = gate_result.get("missing_fields", missing_fields)

            if confirmed_missing:
                logger.info(
                    f"[{request_id}] Intelligence gate: {len(confirmed_missing)} gaps confirmed "
                    f"(prompt_version={active_prompt.version})"
                )
                req = MissingGapsRequest(missing_fields=confirmed_missing)
                setattr(req, "_prompt_version", active_prompt.version)
                setattr(req, "_prompt_version_id", active_prompt.id)
                api_results["_gate_prompt_version"] = active_prompt.version
                return req
            else:
                logger.info(f"[{request_id}] Intelligence gate: LLM says data is sufficient")
                return None


        except Exception as e:
            logger.warning(f"[{request_id}] Intelligence gate LLM call failed: {e}")
            # Fall back to simple field check
            return MissingGapsRequest(missing_fields=missing_fields)
    else:
        # No OpenAI key — use simple field check
        logger.info(
            f"[{request_id}] Intelligence gate (no LLM): {len(missing_fields)} fields missing"
        )
        return MissingGapsRequest(missing_fields=missing_fields)


# ── Step 4: spawn_fallback_agent ────────────────────────────────────────────


def spawn_fallback_agent(
    session: Session,
    request_id: uuid.UUID,
    company_name: str,
    gaps: MissingGapsRequest,
    existing_data: dict[str, Any] | None = None,
) -> AgenticExtractionResult:
    """Spawn the LLM fallback agent to fill identified data gaps.

    Phase 1: After the agent returns, the confidence score is checked against
    the configured guardrail threshold. If the score is below threshold,
    a private '_needs_review' attribute is set on the result object so that
    save_final_lineage can set lead.status = 'needs_review' instead of
    'completed'. The result is still persisted — it is not discarded.

    Delegates to pipeline.fallback_agent.run_fallback().
    """
    result = run_fallback(
        session=session,
        request_id=request_id,
        company_name=company_name,
        missing_fields=gaps.missing_fields,
        existing_data=existing_data,
    )

    # Guardrail: confidence threshold check
    confidence_ok = check_confidence(result, session=session)
    if not confidence_ok:
        logger.warning(
            "[%s] Guardrail triggered: confidence=%.3f below threshold — will mark needs_review",
            request_id,
            result.confidence_score,
        )
        # Attach flag as a plain attribute — Pydantic model_extra is not used;
        # we use object.__setattr__ to avoid Pydantic's immutability guard.
        object.__setattr__(result, "_needs_review", True)
    else:
        object.__setattr__(result, "_needs_review", False)

    return result


# ── Step 5: save_final_lineage ──────────────────────────────────────────────


def save_final_lineage(
    session: Session,
    request_id: uuid.UUID,
    api_data: dict[str, Any],
    fallback_data: AgenticExtractionResult | None = None,
) -> dict[str, Any]:
    """Merge API data + fallback data, update lead, and store embedding.

    Phase 1: If the fallback agent set _needs_review=True (confidence below
    threshold), the lead status is set to 'needs_review' instead of 'completed'.
    The enriched data is still persisted so a reviewer can inspect it.

    Returns the final merged enriched_data dict.
    """
    # Build the final merged result
    merged = _merge_results(api_data, fallback_data)

    # Update lead record
    lead = lead_service.get_lead_by_request_id_sync(session, request_id)
    if lead is None:
        raise ValueError(f"Lead not found for request_id={request_id}")

    lead.enriched_data = merged

    # Phase 1: honour guardrail flag from spawn_fallback_agent
    needs_review = (
        fallback_data is not None
        and getattr(fallback_data, "_needs_review", False)
    )
    lead.status = "needs_review" if needs_review else "completed"

    # Phase 5: set enriched_at timestamp when completed
    if lead.status == "completed":
        from datetime import datetime, timezone
        lead.enriched_at = datetime.now(timezone.utc)

    session.flush()

    # Generate and store vector embedding
    try:
        embedding_service.store_embedding_sync(
            session=session,
            lead_id=lead.id,
            enriched_data=merged,
        )
    except Exception as e:
        logger.warning(f"[{request_id}] Failed to store embedding: {e}")
        # Non-fatal — don't fail the pipeline for embedding errors

    final_status = lead.status
    logger.info(f"[{request_id}] Final lineage saved: status={final_status}")
    return merged


def _merge_results(
    api_data: dict[str, Any],
    fallback_data: AgenticExtractionResult | None,
) -> dict[str, Any]:
    """Merge API-sourced data with fallback agent results.

    Fallback data fills gaps but doesn't overwrite existing API data.
    Private keys (starting with _) are excluded from the final result.
    """
    # Start with clean API data (remove private keys)
    merged = {k: v for k, v in api_data.items() if not k.startswith("_")}
    provenance = dict(api_data.get("_field_provenance", {}))

    if fallback_data:
        fallback_dict = fallback_data.model_dump()
        for key, value in fallback_dict.items():
            if value is not None and not merged.get(key):
                merged[key] = value
                provenance[key] = "fallback"

        # Always include confidence and sources from fallback
        merged["fallback_confidence_score"] = fallback_data.confidence_score
        merged["fallback_sources_used"] = fallback_data.sources_used
        provenance["fallback_confidence_score"] = "fallback"
        provenance["fallback_sources_used"] = "fallback"

    # Include provenance metadata
    merged["_api_sources"] = api_data.get("_api_sources_used", [])
    merged["_had_fallback"] = fallback_data is not None
    merged["_field_provenance"] = provenance


    # Phase 2: include prompt version lineage
    prompt_versions: dict[str, str] = {}
    if fallback_data:
        fb_version = getattr(fallback_data, "_prompt_version", None)
        if fb_version:
            prompt_versions["fallback"] = fb_version
    gate_version = api_data.get("_gate_prompt_version")
    if gate_version:
        prompt_versions["gate"] = gate_version

    if prompt_versions:
        merged["_prompt_versions"] = prompt_versions

    return merged

