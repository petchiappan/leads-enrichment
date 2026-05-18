"""
Fallback Agent & Micro Pydantic Extractor schemas.

Strictly matches the schema defined in skill_llm_fallback.md.
Used with: client.chat.completions.create(response_format={"type": "json_object"})
"""

from __future__ import annotations

from pydantic import BaseModel, Field


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
        ge=0,
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
