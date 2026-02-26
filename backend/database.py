"""
Async SQLAlchemy setup for SQLite (MVP) / Postgres (production).

DATABASE_URL in .env determines which:
  sqlite+aiosqlite:///./data/conversations.db   ← default
  postgresql+asyncpg://user:pass@host/db         ← swap-in for prod

Call create_tables() once at app startup to ensure schema exists.

Usage:
    async with get_db() as db:
        db.add(some_model)
        await db.commit()
        await db.refresh(some_model)
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from backend.config import settings


class Base(DeclarativeBase):
    pass


# Engine — created once at import time
_connect_args = {"check_same_thread": False} if "sqlite" in settings.database_url else {}

engine = create_async_engine(
    settings.database_url,
    connect_args=_connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def create_tables() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    import backend.models  # noqa: F401 — populates Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
