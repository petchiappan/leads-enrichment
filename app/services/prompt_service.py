"""
Prompt service — CRUD, activation, and diffing for prompt versions.
"""

from __future__ import annotations

import difflib
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prompt_version import PromptVersion
from app.pipeline import prompt_registry
from app.schemas.prompt import PromptDiffOut, PromptVersionIn


async def get_all_prompts(
    session: AsyncSession,
    name: str | None = None,
    environment: str | None = None,
) -> list[PromptVersion]:
    """Retrieve all prompt versions, optionally filtered by name or environment."""
    stmt = select(PromptVersion).order_by(PromptVersion.name.asc(), PromptVersion.created_at.desc())
    if name:
        stmt = stmt.where(PromptVersion.name == name)
    if environment:
        stmt = stmt.where(PromptVersion.environment == environment)

    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_prompt_by_id(session: AsyncSession, prompt_id: int) -> PromptVersion | None:
    """Retrieve a specific prompt version by primary key."""
    result = await session.execute(
        select(PromptVersion).where(PromptVersion.id == prompt_id)
    )
    return result.scalar_one_or_none()


async def get_active_prompt_for(
    session: AsyncSession,
    name: str,
    environment: str = "production",
) -> PromptVersion | None:
    """Retrieve the currently active prompt version for a given name and environment."""
    stmt = (
        select(PromptVersion)
        .where(
            PromptVersion.name == name,
            PromptVersion.environment == environment,
            PromptVersion.is_active.is_(True),
        )
        .order_by(PromptVersion.id.desc())
    )
    result = await session.execute(stmt)
    return result.scalars().first()


async def create_prompt_version(
    session: AsyncSession,
    payload: PromptVersionIn,
) -> PromptVersion:
    """Create a new prompt version. If is_active=True, deactivates sibling versions."""
    if payload.is_active:
        await session.execute(
            update(PromptVersion)
            .where(
                PromptVersion.name == payload.name,
                PromptVersion.environment == payload.environment,
            )
            .values(is_active=False)
        )

    prompt = PromptVersion(
        name=payload.name,
        version=payload.version,
        content=payload.content,
        environment=payload.environment,
        is_active=payload.is_active,
    )
    session.add(prompt)
    await session.flush()

    prompt_registry.clear_cache()
    return prompt


async def activate_prompt_version(
    session: AsyncSession,
    prompt_id: int,
) -> PromptVersion:
    """Activate a specific prompt version and deactivate its siblings."""
    prompt = await get_prompt_by_id(session, prompt_id)
    if not prompt:
        raise ValueError(f"Prompt version {prompt_id} not found")

    # Deactivate all versions with same name and environment
    await session.execute(
        update(PromptVersion)
        .where(
            PromptVersion.name == prompt.name,
            PromptVersion.environment == prompt.environment,
        )
        .values(is_active=False)
    )

    prompt.is_active = True
    await session.flush()

    prompt_registry.clear_cache()
    return prompt


async def compute_diff(session: AsyncSession, prompt_id: int) -> PromptDiffOut:
    """Compute unified text diff between this prompt version and the active version."""
    target = await get_prompt_by_id(session, prompt_id)
    if not target:
        raise ValueError(f"Prompt version {prompt_id} not found")

    active = await get_active_prompt_for(session, target.name, target.environment)
    active_content = active.content if active else ""
    active_version = active.version if active else None

    diff_lines = list(
        difflib.unified_diff(
            active_content.splitlines(keepends=True),
            target.content.splitlines(keepends=True),
            fromfile=f"{target.name}:{active_version or 'none'}",
            tofile=f"{target.name}:{target.version}",
        )
    )
    diff_text = "".join(diff_lines)

    return PromptDiffOut(
        id=target.id,
        name=target.name,
        version=target.version,
        active_version=active_version,
        diff=diff_text,
    )
