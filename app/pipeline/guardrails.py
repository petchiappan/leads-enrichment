"""
Guardrails — input sanitisation and output quality checks for LLM enrichment.

Two entry points:
  - sanitise_input(company_name)      : strips control characters, enforces max length
  - check_confidence(result, session) : reads threshold from admin_config; returns bool

Policy on failure:
  - Invalid output fields are coerced to None by Pydantic validators (schemas/fallback.py).
  - A result below the confidence threshold returns False here; the caller sets
    lead.status = "needs_review" rather than raising an exception.
  - If admin_config is unavailable, hardcoded conservative defaults are used.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from sqlalchemy.orm import Session

from app import metrics

if TYPE_CHECKING:
    from app.schemas.fallback import AgenticExtractionResult

logger = logging.getLogger(__name__)

# ── Defaults (used when admin_config is unavailable) ────────────────────────
DEFAULT_MIN_CONFIDENCE: float = 0.3
DEFAULT_MAX_COMPANY_NAME_LENGTH: int = 256

# Regex for control characters (excludes printable ASCII and common Unicode)
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

# Prompt-injection sentinel patterns (basic heuristic)
_INJECTION_RE = re.compile(
    r"(ignore\s+(all\s+)?previous\s+instructions|"
    r"forget\s+(all\s+)?previous|"
    r"you\s+are\s+now|"
    r"system\s*:\s*)",
    re.IGNORECASE,
)


# ── Internal helpers ─────────────────────────────────────────────────────────


def _get_float_config(session: Session, key: str, default: float) -> float:
    """Read a float value from admin_config, falling back to default on any error."""
    try:
        from app.models.admin_config import AdminConfig
        from sqlalchemy import select

        row = session.execute(
            select(AdminConfig).where(AdminConfig.setting_key == key)
        ).scalar_one_or_none()

        if row is not None:
            return float(row.setting_value)
    except Exception as exc:
        logger.warning("guardrails: could not read config key=%s: %s — using default", key, exc)

    return default


def _get_int_config(session: Session, key: str, default: int) -> int:
    """Read an int value from admin_config, falling back to default on any error."""
    try:
        from app.models.admin_config import AdminConfig
        from sqlalchemy import select

        row = session.execute(
            select(AdminConfig).where(AdminConfig.setting_key == key)
        ).scalar_one_or_none()

        if row is not None:
            return int(row.setting_value)
    except Exception as exc:
        logger.warning("guardrails: could not read config key=%s: %s — using default", key, exc)

    return default


# ── Public API ───────────────────────────────────────────────────────────────


def sanitise_input(company_name: str, session: Session | None = None) -> str:
    """Sanitise company_name before it is injected into an LLM prompt.

    Actions:
      1. Strip leading/trailing whitespace.
      2. Remove ASCII control characters (\\x00–\\x1f, \\x7f).
      3. Warn and truncate if name contains injection-like patterns.
      4. Truncate to max_company_name_length (from admin_config or default).

    Returns the cleaned string. Never raises — returns at least an empty string.
    """
    if not isinstance(company_name, str):
        return ""

    name = company_name.strip()

    # Remove control characters
    name = _CONTROL_CHAR_RE.sub("", name)

    # Warn on suspected injection attempts
    if _INJECTION_RE.search(name):
        logger.warning(
            "guardrails: suspected prompt injection in company_name — sanitising. "
            "Original (truncated): %.80r",
            company_name,
        )
        try:
            metrics.guardrail_violations_total.labels(field="company_name", rule="prompt_injection").inc()
        except Exception:
            pass
        # Remove the matched injection patterns
        name = _INJECTION_RE.sub("", name).strip()

    # Enforce max length
    max_len = (
        _get_int_config(session, "guardrail.max_company_name_length", DEFAULT_MAX_COMPANY_NAME_LENGTH)
        if session is not None
        else DEFAULT_MAX_COMPANY_NAME_LENGTH
    )
    if len(name) > max_len:
        logger.warning(
            "guardrails: company_name truncated from %d to %d chars", len(name), max_len
        )
        try:
            metrics.guardrail_violations_total.labels(field="company_name", rule="max_length").inc()
        except Exception:
            pass
        name = name[:max_len]

    return name


def check_confidence(
    result: "AgenticExtractionResult",
    session: Session | None = None,
) -> bool:
    """Return True if the result's confidence_score meets the configured threshold.

    If False, the caller should set lead.status = "needs_review" rather than
    "completed". The result is still persisted — it is not discarded.

    Args:
        result: Parsed LLM output after Pydantic validation.
        session: Sync DB session to read admin_config threshold. If None, uses default.

    Returns:
        True  — confidence is acceptable.
        False — confidence is below threshold; result needs human review.
    """
    threshold = (
        _get_float_config(session, "guardrail.min_confidence_threshold", DEFAULT_MIN_CONFIDENCE)
        if session is not None
        else DEFAULT_MIN_CONFIDENCE
    )

    if result.confidence_score < threshold:
        logger.warning(
            "guardrails: confidence_score=%.3f below threshold=%.3f — flagging for review",
            result.confidence_score,
            threshold,
            extra={
                "confidence_score": result.confidence_score,
                "threshold": threshold,
                "guardrail": "min_confidence_threshold",
            },
        )
        try:
            metrics.guardrail_violations_total.labels(field="confidence_score", rule="confidence_threshold").inc()
        except Exception:
            pass
        return False


    logger.debug(
        "guardrails: confidence_score=%.3f >= threshold=%.3f — OK",
        result.confidence_score,
        threshold,
    )
    return True


def is_pii_redaction_enabled(session: Session | None = None) -> bool:
    """Check if PII redaction is enabled in admin_config."""
    if session is not None:
        try:
            from app.models.admin_config import AdminConfig
            from sqlalchemy import select
            row = session.execute(
                select(AdminConfig).where(AdminConfig.setting_key == "guardrail.pii_redaction_enabled")
            ).scalar_one_or_none()
            if row is not None:
                return row.setting_value.lower() == "true"
        except Exception as exc:
            logger.warning("guardrails: could not read pii_redaction_enabled config: %s", exc)
    return False


def redact_pii_from_dict(
    data: dict[str, Any] | None,
    session: Session | None = None,
) -> dict[str, Any]:
    """Redact PII from dictionary values if PII redaction is enabled."""
    if not data or not is_pii_redaction_enabled(session):
        return dict(data or {})

    from app.services.observability import redact_pii

    sanitized: dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            sanitized[k] = redact_pii(v)
        elif isinstance(v, list):
            sanitized[k] = [redact_pii(item) if isinstance(item, str) else item for item in v]
        elif isinstance(v, dict):
            sanitized[k] = redact_pii_from_dict(v, session=session)
        else:
            sanitized[k] = v
    return sanitized

