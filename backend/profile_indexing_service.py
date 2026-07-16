"""Application facade for published-profile indexing and evidenced answers."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from backend.answer_engine import AnswerEngine
from backend.knowledge_backend import (
    DEFAULT_KNOWLEDGE_BACKEND,
    build_profile_chunks,
    cosine_similarity,
    embed_text,
)
from backend.profile_indexing_schemas import AskResponse, ProfileIndexStatusResponse


async def get_index_status(db: AsyncSession, owner_id: str) -> ProfileIndexStatusResponse:
    return await DEFAULT_KNOWLEDGE_BACKEND.status(db, owner_id)


async def index_active_profile(db: AsyncSession, owner_id: str):
    return await DEFAULT_KNOWLEDGE_BACKEND.index_active_profile(db, owner_id)


async def answer_question(db: AsyncSession, owner_id: str, question: str) -> AskResponse:
    engine = AnswerEngine()
    return await engine.answer(await engine.plan(db, owner_id, question))


__all__ = [
    "answer_question",
    "build_profile_chunks",
    "cosine_similarity",
    "embed_text",
    "get_index_status",
    "index_active_profile",
]
