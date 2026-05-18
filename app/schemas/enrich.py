"""
Enrich API schemas — request/response for POST /api/enrich.

EnrichRequest: company_name is the ONLY required field.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


class EnrichRequest(BaseModel):
    """Payload accepted by POST /api/enrich.

    Only `company_name` is required. All other fields are optional context
    that improve enrichment quality.
    """

    company_name: str = Field(
        ...,
        min_length=1,
        max_length=256,
        description="Name of the company to enrich. This is the only required field.",
        examples=["OpenAI"],
    )
    company_domain: str | None = Field(
        default=None,
        max_length=512,
        description="Company website domain (e.g., 'openai.com').",
        examples=["openai.com"],
    )
    additional_context: dict[str, Any] | None = Field(
        default=None,
        description="Free-form JSON context to assist enrichment (e.g., industry hints, known contacts).",
    )


class EnrichResponse(BaseModel):
    """Immediate 202 Accepted response returned after queuing the enrichment job."""

    request_id: uuid.UUID = Field(
        ...,
        description="Unique identifier to track this enrichment request.",
    )
    status: str = Field(
        default="accepted",
        description="Always 'accepted' for a successfully queued job.",
    )
    message: str = Field(
        default="Enrichment job has been queued for processing.",
        description="Human-readable status message.",
    )
