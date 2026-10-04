"""
Pydantic schemas for Prompt Versions API.
"""

from __future__ import annotations

import datetime
from pydantic import BaseModel, ConfigDict, Field


class PromptVersionIn(BaseModel):
    """Payload to create a new prompt version."""

    name: str = Field(..., min_length=1, max_length=128, description="Logical prompt name.")
    version: str = Field(..., min_length=1, max_length=32, description="Semantic version string, e.g. v1.1.0.")
    content: str = Field(..., min_length=1, description="Prompt text / template content.")
    environment: str = Field("production", max_length=32, description="Target environment.")
    is_active: bool = Field(False, description="Whether to activate immediately upon creation.")


class PromptVersionOut(BaseModel):
    """Representation of a prompt version record."""

    id: int
    name: str
    version: str
    content: str
    environment: str
    is_active: bool
    created_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class PromptVersionListOut(BaseModel):
    """List of prompt versions with total count."""

    items: list[PromptVersionOut]
    total: int


class PromptDiffOut(BaseModel):
    """Textual diff comparison between a prompt version and the active version."""

    id: int
    name: str
    version: str
    active_version: str | None
    diff: str
