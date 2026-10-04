"""
Observability service — structured JSON logging, correlation IDs, timed LLM calls, and PII redaction.
"""

from __future__ import annotations

import logging
import re
import sys
import time
from typing import Any

from pythonjsonlogger import jsonlogger

from app import metrics
from app.pipeline import context

logger = logging.getLogger(__name__)

# ── PII Patterns ─────────────────────────────────────────────────────────────
_EMAIL_PATTERN = re.compile(
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b"
)
_PHONE_PATTERN = re.compile(
    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"
)


def redact_pii(text: str) -> str:
    """Redact sensitive PII (emails and phone numbers) from strings before logging or storing."""
    if not isinstance(text, str):
        return text
    redacted = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    redacted = _PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    return redacted


# ── Correlation Filter ────────────────────────────────────────────────────────
class RequestIdFilter(logging.Filter):
    """Logging filter that injects the current pipeline request_id into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = context.get_request_id() or "-"
        return True


# ── Logging Configuration ────────────────────────────────────────────────────
def configure_logging(as_json: bool = True) -> None:
    """Configure root logger with structured JSON formatting and request_id injection."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers to prevent duplicate lines
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIdFilter())

    if as_json:
        formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(request_id)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | [%(request_id)s] %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


# ── Timed LLM Call Wrapper ───────────────────────────────────────────────────
def timed_llm_call(
    client: Any,
    step_name: str,
    **kwargs: Any,
) -> tuple[Any, float]:
    """Execute an OpenAI chat completion with latency timing and Prometheus recording.

    Args:
        client: OpenAI client instance.
        step_name: Logical step name, e.g. 'spawn_fallback_agent' or 'evaluate_intelligence_gate'.
        **kwargs: Arguments to pass to client.chat.completions.create.

    Returns:
        (response, duration_seconds)
    """
    model = kwargs.get("model", "unknown")
    start = time.perf_counter()
    try:
        response = client.chat.completions.create(**kwargs)
        duration_s = time.perf_counter() - start
        metrics.llm_call_duration_seconds.labels(step_name=step_name, model=model).observe(duration_s)
        return response, duration_s
    except Exception:
        duration_s = time.perf_counter() - start
        metrics.llm_call_duration_seconds.labels(step_name=step_name, model=model).observe(duration_s)
        raise
