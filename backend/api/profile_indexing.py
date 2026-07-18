"""Published profile indexing and evidenced question-answering API."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.database import get_db
from backend.owner import configured_owner_id
from backend.profile_indexing_schemas import (
    AskRequest,
    AskResponse,
    ProfileIndexChunkResponse,
    ProfileIndexResponse,
    ProfileIndexStatusResponse,
)
from backend.profile_indexing_service import (
    answer_question,
    get_index_status,
    index_and_activate_profile,
)

router = APIRouter(tags=["profile-indexing"])


def _validate_api_key(api_key: str | None) -> None:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")


@router.get("/profile/index-status", response_model=ProfileIndexStatusResponse)
async def read_profile_index_status(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    async with get_db() as db:
        return await get_index_status(db, configured_owner_id())


@router.post("/profile/index", response_model=ProfileIndexResponse)
async def index_profile(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    async with get_db() as db:
        try:
            status, chunks = await index_and_activate_profile(db, configured_owner_id())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return _index_response(status, chunks)


@router.post("/profile/versions/{version}/activate", response_model=ProfileIndexResponse)
async def activate_profile_version(
    version: int,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    _validate_api_key(x_api_key)
    async with get_db() as db:
        try:
            status, chunks = await index_and_activate_profile(db, configured_owner_id(), version)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return _index_response(status, chunks)


def _index_response(status: ProfileIndexStatusResponse, chunks) -> ProfileIndexResponse:
    return ProfileIndexResponse(
        **status.model_dump(),
        chunks=[
            ProfileIndexChunkResponse(
                id=chunk.id,
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                title=chunk.title,
            )
            for chunk in chunks
        ],
    )


@router.post("/ask", response_model=AskResponse)
async def ask_question(body: AskRequest, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    async with get_db() as db:
        try:
            return await answer_question(db, configured_owner_id(), body.question)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
