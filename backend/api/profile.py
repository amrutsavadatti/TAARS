"""Profile dashboard API for canonical draft and published snapshot state."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from backend.config import settings
from backend.database import get_db
from backend.profile_schemas import (
    ProfileDraftInput,
    ProfileDraftResponse,
    PublishedProfileResponse,
)
from backend.profile_service import get_active_snapshot, get_draft, publish_draft, save_draft

router = APIRouter(prefix="/profile", tags=["profile"])


def _validate_api_key(api_key: str | None) -> None:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")


def _owner_id() -> str:
    return settings.owner_name.lower().replace(" ", "_")


@router.get("", response_model=ProfileDraftResponse)
async def read_profile(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    owner_id = _owner_id()
    async with get_db() as db:
        draft = await get_draft(db, owner_id)
        active = await get_active_snapshot(db, owner_id)
        return ProfileDraftResponse(
            owner_id=owner_id,
            owner_name=draft.owner_name if draft else settings.owner_name,
            experiences=draft.experiences if draft else [],
            updated_at=draft.updated_at.isoformat() if draft else None,
            published_version=active.version if active else None,
            has_published_snapshot=active is not None,
        )


@router.put("/draft", response_model=ProfileDraftResponse)
async def update_profile_draft(
    body: ProfileDraftInput,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    _validate_api_key(x_api_key)
    owner_id = _owner_id()
    async with get_db() as db:
        draft = await save_draft(db, owner_id, body)
        active = await get_active_snapshot(db, owner_id)
        return ProfileDraftResponse(
            owner_id=owner_id,
            owner_name=draft.owner_name,
            experiences=draft.experiences,
            updated_at=draft.updated_at.isoformat(),
            published_version=active.version if active else None,
            has_published_snapshot=active is not None,
        )


@router.post("/publish", response_model=PublishedProfileResponse)
async def publish_profile(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    owner_id = _owner_id()
    async with get_db() as db:
        published, issues = await publish_draft(db, owner_id)
        if published is None:
            raise HTTPException(
                status_code=422,
                detail={"status": "blocked", "issues": [issue.model_dump() for issue in issues]},
            )
        return PublishedProfileResponse(
            owner_id=owner_id,
            version=published.version,
            published_at=published.published_at.isoformat(),
            snapshot=published.snapshot,
        )


@router.get("/published-snapshot", response_model=PublishedProfileResponse)
async def read_published_snapshot(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    owner_id = _owner_id()
    async with get_db() as db:
        active = await get_active_snapshot(db, owner_id)
        if active is None:
            raise HTTPException(status_code=404, detail="No published profile snapshot.")
        return PublishedProfileResponse(
            owner_id=owner_id,
            version=active.version,
            published_at=active.published_at.isoformat(),
            snapshot=active.snapshot,
        )
