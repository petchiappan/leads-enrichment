"""
Admin configuration service — CRUD for key/value runtime settings.

All operations are async (admin config is only accessed via the API).
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin_config import AdminConfig


async def get_all_configs(session: AsyncSession) -> list[AdminConfig]:
    """Get all admin configuration entries."""
    result = await session.execute(
        select(AdminConfig).order_by(AdminConfig.setting_key.asc())
    )
    return list(result.scalars().all())


async def get_config(session: AsyncSession, key: str) -> AdminConfig | None:
    """Get a specific admin configuration by key."""
    result = await session.execute(
        select(AdminConfig).where(AdminConfig.setting_key == key)
    )
    return result.scalar_one_or_none()


async def upsert_config(
    session: AsyncSession,
    key: str,
    value: str,
) -> AdminConfig:
    """Create or update an admin configuration entry."""
    existing = await get_config(session, key)
    if existing:
        existing.setting_value = value
        await session.flush()
        return existing

    config = AdminConfig(setting_key=key, setting_value=value)
    session.add(config)
    await session.flush()
    return config


async def delete_config(session: AsyncSession, key: str) -> bool:
    """Delete an admin configuration entry. Returns True if deleted."""
    result = await session.execute(
        delete(AdminConfig).where(AdminConfig.setting_key == key)
    )
    return result.rowcount > 0
