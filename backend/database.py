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

from sqlalchemy import inspect, text
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

_PROFILE_DRAFT_JSON_COLUMNS = ("projects", "skills", "education", "achievements", "personal_topics")
_MESSAGE_PROVENANCE_COLUMNS = {
    "answer_status": "VARCHAR",
    "profile_snapshot_version": "INTEGER",
    "knowledge_backend": "VARCHAR",
    "knowledge_backend_version": "VARCHAR",
}
_PROFILE_INDEX_STATE_COLUMNS = {"backend_version": "VARCHAR"}


def _add_missing_profile_draft_columns(sync_conn) -> None:
    """Small startup migration for local MVP DBs until Alembic exists."""
    inspector = inspect(sync_conn)
    if "profile_drafts" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("profile_drafts")}
    default = "'[]'::json" if sync_conn.dialect.name == "postgresql" else "'[]'"
    for column in _PROFILE_DRAFT_JSON_COLUMNS:
        if column not in existing_columns:
            sync_conn.execute(
                text(f"ALTER TABLE profile_drafts ADD COLUMN {column} JSON NOT NULL DEFAULT {default}")
            )


def _ensure_pgvector(sync_conn) -> None:
    """Enable pgvector and add the vector column when running on Postgres."""
    if sync_conn.dialect.name != "postgresql":
        return

    sync_conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    inspector = inspect(sync_conn)
    if "profile_index_chunks" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("profile_index_chunks")}
    if "embedding_vector" not in existing_columns:
        sync_conn.execute(text("ALTER TABLE profile_index_chunks ADD COLUMN embedding_vector vector(384)"))
        sync_conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_profile_index_chunks_embedding_vector "
                "ON profile_index_chunks USING ivfflat (embedding_vector vector_cosine_ops) WITH (lists = 20)"
            )
        )


def _add_missing_message_columns(sync_conn) -> None:
    """Preserve local conversation data while adding grounded-answer provenance."""
    inspector = inspect(sync_conn)
    if "messages" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("messages")}
    for column, column_type in _MESSAGE_PROVENANCE_COLUMNS.items():
        if column not in existing_columns:
            sync_conn.execute(text(f"ALTER TABLE messages ADD COLUMN {column} {column_type}"))


def _add_missing_index_state_columns(sync_conn) -> None:
    inspector = inspect(sync_conn)
    if "profile_index_states" not in inspector.get_table_names():
        return
    existing_columns = {column["name"] for column in inspector.get_columns("profile_index_states")}
    for column, column_type in _PROFILE_INDEX_STATE_COLUMNS.items():
        if column not in existing_columns:
            sync_conn.execute(text(f"ALTER TABLE profile_index_states ADD COLUMN {column} {column_type}"))


async def create_tables() -> None:
    """Create all tables if they don't exist. Safe to call on every startup."""
    import backend.models  # noqa: F401 — populates Base.metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.run_sync(_add_missing_profile_draft_columns)
        await conn.run_sync(_add_missing_message_columns)
        await conn.run_sync(_add_missing_index_state_columns)
        await conn.run_sync(_ensure_pgvector)


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
