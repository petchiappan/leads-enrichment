"""
Admin Prompts API — list, create, activate, and diff prompt versions.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.prompt import (
    PromptDiffOut,
    PromptVersionIn,
    PromptVersionListOut,
    PromptVersionOut,
)
from app.services import prompt_service

router = APIRouter(prefix="/api/admin/prompts", tags=["prompts"])


@router.get(
    "",
    response_model=PromptVersionListOut,
    summary="List all prompt versions",
)
async def list_prompts(
    name: str | None = Query(None, description="Filter by prompt name"),
    environment: str | None = Query(None, description="Filter by environment"),
    db: AsyncSession = Depends(get_db),
) -> PromptVersionListOut:
    """Retrieve all stored prompt versions."""
    items = await prompt_service.get_all_prompts(db, name=name, environment=environment)
    return PromptVersionListOut(
        items=[PromptVersionOut.model_validate(p) for p in items],
        total=len(items),
    )


@router.get(
    "/{name}",
    response_model=PromptVersionListOut,
    summary="List versions for a specific prompt name",
)
async def get_prompts_by_name(
    name: str,
    environment: str | None = Query(None, description="Filter by environment"),
    db: AsyncSession = Depends(get_db),
) -> PromptVersionListOut:
    """Retrieve all versions of a prompt by logical name."""
    items = await prompt_service.get_all_prompts(db, name=name, environment=environment)
    return PromptVersionListOut(
        items=[PromptVersionOut.model_validate(p) for p in items],
        total=len(items),
    )


@router.post(
    "",
    response_model=PromptVersionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new prompt version",
)
async def create_prompt(
    payload: PromptVersionIn,
    db: AsyncSession = Depends(get_db),
) -> PromptVersionOut:
    """Create a new prompt version. If is_active is true, previous versions are deactivated."""
    try:
        prompt = await prompt_service.create_prompt_version(db, payload)
        await db.commit()
        return PromptVersionOut.model_validate(prompt)
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to create prompt version: {exc}",
        )


@router.post(
    "/{prompt_id}/activate",
    response_model=PromptVersionOut,
    summary="Activate a prompt version",
)
async def activate_prompt(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
) -> PromptVersionOut:
    """Activate a specific prompt version and deactivate its siblings in the same environment."""
    try:
        prompt = await prompt_service.activate_prompt_version(db, prompt_id)
        await db.commit()
        return PromptVersionOut.model_validate(prompt)
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except Exception as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate prompt version: {exc}",
        )


@router.get(
    "/{prompt_id}/diff",
    response_model=PromptDiffOut,
    summary="Compute diff against the active prompt version",
)
async def get_prompt_diff(
    prompt_id: int,
    db: AsyncSession = Depends(get_db),
) -> PromptDiffOut:
    """Get textual diff between this prompt version and the currently active version."""
    try:
        return await prompt_service.compute_diff(db, prompt_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
