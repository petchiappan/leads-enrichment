"""
Fallback Agent & Micro Pydantic Extractor schemas.

Strictly matches the schema defined in skill_llm_fallback.md.
Used with: client.chat.completions.create(response_format={"type": "json_object"})

Phase 1 addition: field-level validators coerce malformed LLM output to None
rather than storing invalid strings (e.g., "not available", bare hostnames).
Validators use mode='before' so they run on raw LLM JSON before type coercion.
"""

from __future__ import annotations

import datetime
import re
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ── Validation patterns ──────────────────────────────────────────────────────

# RFC-5322-ish email pattern (pragmatic, not exhaustive)
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

# URL must start with http:// or https:// and have at least one dot after the host
_URL_RE = re.compile(
    r"^https?://[^\s/$.?#].[^\s]*\.[^\s]+",
    re.IGNORECASE,
)

_CURRENT_YEAR = datetime.date.today().year


class MissingGapsRequest(BaseModel):
    """Specifies which fields are missing after the deterministic engine pass.

    Sent to the Fallback Agent so it knows what data to search for.
    """

    missing_fields: list[str] = Field(
        ...,
        min_length=1,
        description="List of missing field names (e.g., ['ceo_email', 'company_revenue']).",
        examples=[["ceo_email", "company_revenue", "funding_raised"]],
    )


class AgenticExtractionResult(BaseModel):
    """Strict schema the Fallback Agent must return.

    Every field matches skill_llm_fallback.md exactly.
    Used as the response_format target for OpenAI structured JSON output.

    Phase 1: field_validators coerce bad LLM output to None instead of storing
    strings like "not available", bare domains, or out-of-range years.
    """

    company_name: str = Field(
        ...,
        description="Name of the company.",
    )
    ceo_name: str | None = Field(
        default=None,
        description="Name of the CEO or top executive.",
    )
    ceo_email: str | None = Field(
        default=None,
        description="Email address of the CEO.",
    )
    company_description: str | None = Field(
        default=None,
        description="Brief description of the company.",
    )
    linkedin_url: str | None = Field(
        default=None,
        description="LinkedIn profile URL of the CEO or key contact.",
    )
    linkedin_company_url: str | None = Field(
        default=None,
        description="LinkedIn company page URL.",
    )
    employee_count: int | None = Field(
        default=None,
        ge=1,
        description="Approximate number of employees.",
    )
    company_website: str | None = Field(
        default=None,
        description="Primary company website URL.",
    )
    funding_raised: str | None = Field(
        default=None,
        description="Total funding raised (e.g., '$50M Series B').",
    )
    industry: str | None = Field(
        default=None,
        description="Industry or sector the company operates in.",
    )
    founding_year: int | None = Field(
        default=None,
        description="Year the company was founded.",
    )
    news_articles: list[str] | None = Field(
        default=None,
        description="List of relevant news article URLs or headlines.",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the extraction (0.0 to 1.0).",
    )
    sources_used: list[str] = Field(
        ...,
        description="List of data sources used for this extraction.",
    )

    # ── Field validators (Phase 1) ───────────────────────────────────────────

    @field_validator("ceo_email", mode="before")
    @classmethod
    def validate_email(cls, v: Any) -> str | None:
        """Coerce invalid email strings to None.

        Accepts None or a valid RFC-5322-ish email. Any other string
        (e.g. "not available", "unknown", bare names) becomes None.
        """
        if v is None:
            return None
        if not isinstance(v, str):
            return None
        cleaned = v.strip()
        if not cleaned or not _EMAIL_RE.match(cleaned):
            return None
        return cleaned

    @field_validator("company_website", "linkedin_url", "linkedin_company_url", mode="before")
    @classmethod
    def validate_url(cls, v: Any) -> str | None:
        """Coerce invalid URL strings to None.

        Requires http:// or https:// prefix followed by at least one dot.
        Bare domain names (e.g. "stripe.com") and placeholders are rejected.
        """
        if v is None:
            return None
        if not isinstance(v, str):
            return None
        cleaned = v.strip()
        if not cleaned or not _URL_RE.match(cleaned):
            return None
        return cleaned

    @field_validator("founding_year", mode="before")
    @classmethod
    def validate_founding_year(cls, v: Any) -> int | None:
        """Coerce out-of-range or non-numeric founding years to None.

        Valid range: 1800 – current year (inclusive).
        """
        if v is None:
            return None
        try:
            year = int(v)
        except (TypeError, ValueError):
            return None
        if 1800 <= year <= _CURRENT_YEAR:
            return year
        return None

    @field_validator("employee_count", mode="before")
    @classmethod
    def validate_employee_count(cls, v: Any) -> int | None:
        """Coerce non-positive or non-numeric employee counts to None."""
        if v is None:
            return None
        try:
            count = int(v)
        except (TypeError, ValueError):
            return None
        return count if count >= 1 else None

    @field_validator("ceo_name", "company_description", "industry", "funding_raised", mode="before")
    @classmethod
    def coerce_empty_strings(cls, v: Any) -> str | None:
        """Coerce empty or whitespace-only strings to None."""
        if v is None:
            return None
        if not isinstance(v, str):
            return str(v) if v else None
        return v.strip() or None
