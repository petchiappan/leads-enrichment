"""
Pipeline Context — ContextVars for tracing, log correlation, and metadata propagation.
"""

from __future__ import annotations

import contextvars

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


def set_request_id(request_id: str) -> None:
    """Set the current pipeline request_id for the execution context."""
    _request_id_var.set(str(request_id) if request_id else "")


def get_request_id() -> str:
    """Get the current pipeline request_id for the execution context."""
    return _request_id_var.get()
