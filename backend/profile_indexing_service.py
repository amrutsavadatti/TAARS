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
from backend.profile_service import (
    activate_snapshot,
    get_active_snapshot,
    get_candidate_snapshot,
    get_snapshot_version,
)


async def get_index_status(db: AsyncSession, owner_id: str) -> ProfileIndexStatusResponse:
    return await DEFAULT_KNOWLEDGE_BACKEND.status(db, owner_id)


async def index_and_activate_profile(
    db: AsyncSession, owner_id: str, version: int | None = None
):
    if version is not None:
        target = await get_snapshot_version(db, owner_id, version)
    else:
        target = await get_candidate_snapshot(db, owner_id) or await get_active_snapshot(db, owner_id)
    if target is None:
        raise ValueError("Publish a profile candidate before indexing.")

    chunks = await DEFAULT_KNOWLEDGE_BACKEND.index_snapshot(db, target)
    await activate_snapshot(db, target)
    await db.commit()
    return await get_index_status(db, owner_id), chunks


async def answer_question(db: AsyncSession, owner_id: str, question: str) -> AskResponse:
    engine = AnswerEngine()
    return await engine.answer(await engine.plan(db, owner_id, question))


__all__ = [
    "answer_question",
    "build_profile_chunks",
    "cosine_similarity",
    "embed_text",
    "get_index_status",
    "index_and_activate_profile",
]
