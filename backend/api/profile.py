"""Profile dashboard API for canonical draft and published snapshot state."""

from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from backend.config import settings
from backend.database import get_db
from backend.owner import configured_owner_id
from backend.profile_schemas import (
    ProfileDraftInput,
    ProfileDraftResponse,
    ProfileVersionResponse,
    PublishedProfileResponse,
    ResumeImportResponse,
)
from backend.profile_import_service import ResumeImportError, extract_resume_profile
from backend.profile_service import (
    get_active_snapshot,
    get_candidate_snapshot,
    get_draft,
    list_snapshot_versions,
    publish_draft,
    save_draft,
)

router = APIRouter(prefix="/profile", tags=["profile"])
RESUME_EXTENSIONS = {".pdf", ".docx"}


def _validate_api_key(api_key: str | None) -> None:
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")


def _draft_response(owner_id: str, draft, active, candidate) -> ProfileDraftResponse:
    return ProfileDraftResponse(
        owner_id=owner_id,
        owner_name=draft.owner_name if draft else settings.owner_name,
        experiences=draft.experiences if draft else [],
        projects=draft.projects if draft else [],
        skills=draft.skills if draft else [],
        education=draft.education if draft else [],
        certifications=draft.certifications if draft else [],
        achievements=draft.achievements if draft else [],
        personal_topics=draft.personal_topics if draft else [],
        updated_at=draft.updated_at.isoformat() if draft else None,
        published_version=active.version if active else None,
        candidate_version=candidate.version if candidate else None,
        has_published_snapshot=active is not None,
    )


def _snapshot_response(snapshot) -> PublishedProfileResponse:
    return PublishedProfileResponse(
        owner_id=snapshot.owner_id,
        version=snapshot.version,
        published_at=snapshot.published_at.isoformat(),
        activated_at=snapshot.activated_at.isoformat() if snapshot.activated_at else None,
        publication_status=snapshot.publication_status,
        is_active=snapshot.is_active,
        snapshot=snapshot.snapshot,
    )


def _version_response(snapshot) -> ProfileVersionResponse:
    return ProfileVersionResponse(
        version=snapshot.version,
        published_at=snapshot.published_at.isoformat(),
        activated_at=snapshot.activated_at.isoformat() if snapshot.activated_at else None,
        publication_status=snapshot.publication_status,
        is_active=snapshot.is_active,
    )


@router.post("/import-resume", response_model=ResumeImportResponse)
async def import_resume(
    file: UploadFile = File(...),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    _validate_api_key(x_api_key)
    filename = Path(file.filename or "resume").name
    suffix = Path(filename).suffix.lower()
    if suffix not in RESUME_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Upload a PDF or DOCX resume.")

    content = await file.read(settings.max_upload_size_bytes + 1)
    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Resume exceeds the {settings.max_upload_size_mb} MB upload limit.",
        )

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(content)
            temp_path = Path(temp_file.name)
        return await extract_resume_profile(
            temp_path,
            owner_id=configured_owner_id(),
            filename=filename,
        )
    except ResumeImportError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        if temp_path:
            temp_path.unlink(missing_ok=True)


@router.get("", response_model=ProfileDraftResponse)
async def read_profile(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    owner_id = configured_owner_id()
    async with get_db() as db:
        draft = await get_draft(db, owner_id)
        active = await get_active_snapshot(db, owner_id)
        candidate = await get_candidate_snapshot(db, owner_id)
        return _draft_response(owner_id, draft, active, candidate)


@router.put("/draft", response_model=ProfileDraftResponse)
async def update_profile_draft(
    body: ProfileDraftInput,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    _validate_api_key(x_api_key)
    owner_id = configured_owner_id()
    async with get_db() as db:
        draft = await save_draft(db, owner_id, body)
        active = await get_active_snapshot(db, owner_id)
        candidate = await get_candidate_snapshot(db, owner_id)
        return _draft_response(owner_id, draft, active, candidate)


@router.post("/publish", response_model=PublishedProfileResponse)
async def publish_profile(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    owner_id = configured_owner_id()
    async with get_db() as db:
        published, issues = await publish_draft(db, owner_id)
        if published is None:
            raise HTTPException(
                status_code=422,
                detail={"status": "blocked", "issues": [issue.model_dump() for issue in issues]},
            )
        return _snapshot_response(published)


@router.get("/published-snapshot", response_model=PublishedProfileResponse)
async def read_published_snapshot(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    owner_id = configured_owner_id()
    async with get_db() as db:
        active = await get_active_snapshot(db, owner_id)
        if active is None:
            raise HTTPException(status_code=404, detail="No published profile snapshot.")
        return _snapshot_response(active)


@router.get("/versions", response_model=list[ProfileVersionResponse])
async def read_profile_versions(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    _validate_api_key(x_api_key)
    async with get_db() as db:
        versions = await list_snapshot_versions(db, configured_owner_id())
        return [_version_response(snapshot) for snapshot in versions]
