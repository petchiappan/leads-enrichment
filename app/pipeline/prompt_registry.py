"""
Prompt Registry — runtime retrieval and caching of versioned prompts.

Decouples prompt text from source code. Features:
  - Queries active prompt from prompt_versions table
  - In-process TTL caching (60s) to avoid per-request DB hits
  - Safe fallback to hardcoded default prompts if DB is empty or unreachable
  - Exposes prompt content, version tag, and database ID for audit logging
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60.0

HARDCODED_PROMPTS: dict[str, dict[str, str]] = {
    "fallback_system_prompt": {
        "version": "v1.0.0-fallback",
        "content": (
            "You are an expert business intelligence analyst. Your task is to find "
            "accurate information about a company and fill in missing data fields.\n\n"
            "You MUST respond with a valid JSON object matching this exact schema:\n"
            "{\n"
            '    "company_name": "string (required)",\n'
            '    "ceo_name": "string or null",\n'
            '    "ceo_email": "string or null",\n'
            '    "company_description": "string or null",\n'
            '    "linkedin_url": "string or null",\n'
            '    "linkedin_company_url": "string or null",\n'
            '    "employee_count": "integer or null",\n'
            '    "company_website": "string or null",\n'
            '    "funding_raised": "string or null",\n'
            '    "industry": "string or null",\n'
            '    "founding_year": "integer or null",\n'
            '    "news_articles": "list of strings or null",\n'
            '    "confidence_score": "float between 0.0 and 1.0 (required)",\n'
            '    "sources_used": "list of strings (required)"\n'
            "}\n\n"
            "Important rules:\n"
            "1. Only fill in fields you have high confidence about.\n"
            "2. Set fields you're uncertain about to null.\n"
            "3. The confidence_score should reflect your overall certainty (0.0 = no confidence, 1.0 = fully verified).\n"
            "4. Always list the sources you used in sources_used.\n"
            "5. If you already have partial data from API results, incorporate and improve upon it.\n"
        ),
    },
    "intelligence_gate_prompt": {
        "version": "v1.0.0-fallback",
        "content": (
            "You are a data quality assessor. Evaluate which missing fields are "
            "important and should be filled by a fallback agent."
        ),
    },
}


@dataclass(frozen=True)
class ActivePrompt:
    id: int | None
    name: str
    version: str
    content: str
    environment: str


# Cache structure: (name, environment) -> (timestamp, ActivePrompt)
_CACHE: dict[tuple[str, str], tuple[float, ActivePrompt]] = {}


def clear_cache() -> None:
    """Clear the in-process prompt cache."""
    _CACHE.clear()


def get_active_prompt(
    name: str,
    environment: str = "production",
    session: Session | None = None,
) -> ActivePrompt:
    """Retrieve the currently active prompt for a given name and environment.

    Checks:
      1. In-process TTL cache (60s)
      2. DB query (prompt_versions where is_active=True)
      3. HARDCODED_PROMPTS fallback if DB is unreachable or prompt not found
    """
    cache_key = (name, environment)
    now = time.time()

    if cache_key in _CACHE:
        cached_time, prompt = _CACHE[cache_key]
        if (now - cached_time) < CACHE_TTL_SECONDS:
            return prompt

    if session is not None:
        try:
            from app.models.prompt_version import PromptVersion

            stmt = (
                select(PromptVersion)
                .where(
                    PromptVersion.name == name,
                    PromptVersion.environment == environment,
                    PromptVersion.is_active.is_(True),
                )
                .order_by(PromptVersion.id.desc())
            )
            row = session.execute(stmt).scalars().first()

            if row is not None:
                active = ActivePrompt(
                    id=row.id,
                    name=row.name,
                    version=row.version,
                    content=row.content,
                    environment=row.environment,
                )
                _CACHE[cache_key] = (now, active)
                return active
        except Exception as exc:
            logger.warning(
                "prompt_registry: could not load prompt '%s' (%s) from DB: %s — using fallback",
                name,
                environment,
                exc,
            )

    # Fallback to hardcoded default
    fallback_data = HARDCODED_PROMPTS.get(name)
    if fallback_data is not None:
        active = ActivePrompt(
            id=None,
            name=name,
            version=fallback_data["version"],
            content=fallback_data["content"],
            environment=environment,
        )
        _CACHE[cache_key] = (now, active)
        return active

    raise KeyError(f"Prompt '{name}' not found in DB or hardcoded defaults")


def load_active_prompt(
    name: str,
    environment: str = "production",
    session: Session | None = None,
) -> str:
    """Convenience helper returning just the prompt text content."""
    return get_active_prompt(name, environment, session).content


def get_active_prompt_id(
    name: str,
    environment: str = "production",
    session: Session | None = None,
) -> int | None:
    """Convenience helper returning the prompt version DB primary key (or None)."""
    return get_active_prompt(name, environment, session).id


def get_active_prompt_version(
    name: str,
    environment: str = "production",
    session: Session | None = None,
) -> str:
    """Convenience helper returning the prompt version string (e.g. 'v1.0.0')."""
    return get_active_prompt(name, environment, session).version
