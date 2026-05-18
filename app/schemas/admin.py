"""
Admin configuration schemas — for the Settings page CRUD.

Maps to: admin_config table (skill_db_schema.md Table 3)
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class AdminConfigIn(BaseModel):
    """Schema for creating or updating an admin configuration entry."""

    setting_key: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Configuration key (e.g., 'enable_redis_cache').",
        examples=["enable_redis_cache"],
    )
    setting_value: str = Field(
        ...,
        max_length=512,
        description="Configuration value (e.g., 'true').",
        examples=["true"],
    )


class AdminConfigOut(BaseModel):
    """Serialized admin configuration entry for API responses."""

    id: int
    setting_key: str
    setting_value: str

    model_config = {"from_attributes": True}


class AdminConfigListOut(BaseModel):
    """List of all admin configuration entries."""

    configs: list[AdminConfigOut]
    total: int
