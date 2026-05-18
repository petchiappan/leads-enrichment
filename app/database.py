"""
Database engine, session factory, and declarative Base.

Uses SQLAlchemy 2.0 async API with asyncpg driver.
Includes synchronous engine/session for Celery workers.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# ── Async Engine (FastAPI) ──
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# ── Async Session Factory (FastAPI) ──
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# ── Sync Engine (Celery Workers) ──
sync_engine = create_engine(
    settings.DATABASE_URL_SYNC,
    echo=settings.DEBUG,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

# ── Sync Session Factory (Celery Workers) ──
sync_session_factory = sessionmaker(
    bind=sync_engine,
    expire_on_commit=False,
)


# ── Declarative Base (SQLAlchemy 2.0) ──
class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models."""
    pass


# ── Async Dependency for FastAPI ──
async def get_db() -> AsyncSession:  # type: ignore[misc]
    """Yield an async database session for request-scoped usage."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Sync Context Manager for Celery ──
def get_sync_db() -> Session:  # type: ignore[misc]
    """Yield a synchronous database session for Celery task usage."""
    session = sync_session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
