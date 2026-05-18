"""
LLM Fallback Agent — fills data gaps using OpenAI structured JSON output.

Per skill_llm_fallback.md:
- Uses client.chat.completions.create with response_format={"type": "json_object"}
- Returns AgenticExtractionResult with all 14 fields
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import settings
from app.schemas.fallback import AgenticExtractionResult
from app.services import token_service

logger = logging.getLogger(__name__)


FALLBACK_SYSTEM_PROMPT = """You are an expert business intelligence analyst. Your task is to find accurate information about a company and fill in missing data fields.

You MUST respond with a valid JSON object matching this exact schema:
{
    "company_name": "string (required)",
    "ceo_name": "string or null",
    "ceo_email": "string or null",
    "company_description": "string or null",
    "linkedin_url": "string or null",
    "linkedin_company_url": "string or null",
    "employee_count": "integer or null",
    "company_website": "string or null",
    "funding_raised": "string or null",
    "industry": "string or null",
    "founding_year": "integer or null",
    "news_articles": "list of strings or null",
    "confidence_score": "float between 0.0 and 1.0 (required)",
    "sources_used": "list of strings (required)"
}

Important rules:
1. Only fill in fields you have high confidence about.
2. Set fields you're uncertain about to null.
3. The confidence_score should reflect your overall certainty (0.0 = no confidence, 1.0 = fully verified).
4. Always list the sources you used in sources_used.
5. If you already have partial data from API results, incorporate and improve upon it.
"""


def run_fallback(
    session: Session,
    request_id: uuid.UUID,
    company_name: str,
    missing_fields: list[str],
    existing_data: dict[str, Any] | None = None,
) -> AgenticExtractionResult:
    """Execute the LLM fallback agent to fill data gaps.

    Args:
        session: Database session for recording token usage.
        request_id: Pipeline request identifier.
        company_name: Name of the company to research.
        missing_fields: List of field names that need to be filled.
        existing_data: Any data already gathered from API calls.

    Returns:
        AgenticExtractionResult with filled fields.
    """
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Build the user prompt
    user_prompt = _build_user_prompt(company_name, missing_fields, existing_data)

    logger.info(
        f"[{request_id}] Fallback agent: requesting {settings.OPENAI_MODEL} "
        f"for {len(missing_fields)} missing fields"
    )

    # Call OpenAI with structured JSON output (per skill_llm_fallback.md)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": FALLBACK_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
        max_tokens=2000,
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
            step_name="spawn_fallback_agent",
        )

    # Parse response into AgenticExtractionResult
    raw_content = response.choices[0].message.content
    logger.info(f"[{request_id}] Fallback agent raw response: {raw_content[:500]}")

    result = AgenticExtractionResult.model_validate_json(raw_content)

    logger.info(
        f"[{request_id}] Fallback agent completed: "
        f"confidence={result.confidence_score}, sources={len(result.sources_used)}"
    )

    return result


def _build_user_prompt(
    company_name: str,
    missing_fields: list[str],
    existing_data: dict[str, Any] | None,
) -> str:
    """Build the user prompt for the fallback agent."""
    prompt_parts = [
        f"Research the company: **{company_name}**",
        "",
        f"The following fields are missing and need to be filled: {', '.join(missing_fields)}",
    ]

    if existing_data:
        prompt_parts.extend([
            "",
            "Here is the data already gathered from API sources (use this as a starting point):",
            f"```json\n{json.dumps(existing_data, indent=2, default=str)}\n```",
            "",
            "Please verify, correct, and supplement this data. Fill in the missing fields.",
        ])
    else:
        prompt_parts.extend([
            "",
            "No API data was available. Please research the company from scratch and fill in as many fields as possible.",
        ])

    prompt_parts.extend([
        "",
        "Respond with a single JSON object matching the required schema.",
    ])

    return "\n".join(prompt_parts)
