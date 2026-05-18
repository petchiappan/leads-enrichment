"""
Admin Config API — CRUD for runtime configuration settings.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.admin import AdminConfigIn, AdminConfigListOut, AdminConfigOut
from app.services import admin_service

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get(
    "/config",
    response_model=AdminConfigListOut,
    summary="List all configuration entries",
)
async def list_configs(
    db: AsyncSession = Depends(get_db),
) -> AdminConfigListOut:
    """Get all admin configuration key-value pairs."""
    configs = await admin_service.get_all_configs(db)
    return AdminConfigListOut(
        configs=[AdminConfigOut.model_validate(c) for c in configs],
        total=len(configs),
    )


@router.post(
    "/config",
    response_model=AdminConfigOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create or update a configuration entry",
)
async def upsert_config(
    payload: AdminConfigIn,
    db: AsyncSession = Depends(get_db),
) -> AdminConfigOut:
    """Create a new config entry or update an existing one."""
    config = await admin_service.upsert_config(db, payload.setting_key, payload.setting_value)
    return AdminConfigOut.model_validate(config)


@router.put(
    "/config/{key}",
    response_model=AdminConfigOut,
    summary="Update a configuration entry by key",
)
async def update_config(
    key: str,
    payload: AdminConfigIn,
    db: AsyncSession = Depends(get_db),
) -> AdminConfigOut:
    """Update an existing config entry."""
    existing = await admin_service.get_config(db, key)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Config key not found: {key}")
    config = await admin_service.upsert_config(db, key, payload.setting_value)
    return AdminConfigOut.model_validate(config)


@router.delete(
    "/config/{key}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a configuration entry",
)
async def delete_config(
    key: str,
    db: AsyncSession = Depends(get_db),
):
    """Delete a config entry by key."""
    deleted = await admin_service.delete_config(db, key)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Config key not found: {key}")
