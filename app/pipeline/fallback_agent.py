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
from app.pipeline import prompt_registry
from app.schemas.fallback import AgenticExtractionResult
from app.services import token_service
from app.services.observability import timed_llm_call

logger = logging.getLogger(__name__)


# Fallback module constant preserved for backwards-compatibility
FALLBACK_SYSTEM_PROMPT = prompt_registry.HARDCODED_PROMPTS["fallback_system_prompt"]["content"]



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

    # Phase 5: sanitize existing data to protect PII in LLM prompt
    from app.pipeline import guardrails
    sanitized_data = guardrails.redact_pii_from_dict(existing_data, session=session)

    # Build the user prompt
    user_prompt = _build_user_prompt(company_name, missing_fields, sanitized_data)

    logger.info(
        f"[{request_id}] Fallback agent: requesting {settings.OPENAI_MODEL} "
        f"for {len(missing_fields)} missing fields"
    )


    # Load active prompt from registry (DB or fallback)
    active_prompt = prompt_registry.get_active_prompt(
        "fallback_system_prompt",
        environment=settings.APP_ENV,
        session=session,
    )

    # Call OpenAI with structured JSON output and latency timing
    response, duration_s = timed_llm_call(
        client=client,
        step_name="spawn_fallback_agent",
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": active_prompt.content},
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
    logger.info(f"[{request_id}] Fallback agent raw response ({duration_s:.3f}s): {raw_content[:500]}")

    result = AgenticExtractionResult.model_validate_json(raw_content)
    setattr(result, "_prompt_version", active_prompt.version)
    setattr(result, "_prompt_version_id", active_prompt.id)
    setattr(result, "_duration_s", duration_s)

    logger.info(
        f"[{request_id}] Fallback agent completed in {duration_s:.3f}s: "
        f"confidence={result.confidence_score}, sources={len(result.sources_used)}, "
        f"prompt_version={active_prompt.version}"
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
