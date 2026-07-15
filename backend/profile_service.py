"""Canonical profile draft, validation, and publication service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ProfileDraft, PublishedProfileSnapshot
from backend.profile_schemas import ExperienceInput, ProfileDraftInput, ValidationIssue


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _experience_sort_key(exp: dict[str, Any]) -> tuple[int, str]:
    return (int(exp.get("display_order", 0)), str(exp.get("id", "")))


def normalize_experiences(experiences: list[ExperienceInput]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, exp in enumerate(experiences):
        exp_id = _clean(exp.id) or f"exp_{uuid.uuid4().hex}"
        normalized.append(
            {
                "id": exp_id,
                "type": "experience",
                "organization": _clean(exp.organization),
                "role": _clean(exp.role),
                "start_month": exp.start_month,
                "start_year": exp.start_year,
                "end_month": None if exp.is_current else exp.end_month,
                "end_year": None if exp.is_current else exp.end_year,
                "is_current": exp.is_current,
                "summary": _clean(exp.summary),
                "outcome": _clean(exp.outcome),
                "display_order": exp.display_order if exp.display_order is not None else index,
            }
        )
    return sorted(normalized, key=_experience_sort_key)


async def get_active_snapshot(db: AsyncSession, owner_id: str) -> PublishedProfileSnapshot | None:
    result = await db.execute(
        select(PublishedProfileSnapshot)
        .where(
            PublishedProfileSnapshot.owner_id == owner_id,
            PublishedProfileSnapshot.is_active.is_(True),
        )
        .order_by(PublishedProfileSnapshot.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_draft(db: AsyncSession, owner_id: str) -> ProfileDraft | None:
    result = await db.execute(select(ProfileDraft).where(ProfileDraft.owner_id == owner_id))
    return result.scalar_one_or_none()


async def save_draft(db: AsyncSession, owner_id: str, body: ProfileDraftInput) -> ProfileDraft:
    draft = await get_draft(db, owner_id)
    experiences = normalize_experiences(body.experiences)
    if draft is None:
        draft = ProfileDraft(
            owner_id=owner_id,
            owner_name=_clean(body.owner_name),
            experiences=experiences,
        )
        db.add(draft)
    else:
        draft.owner_name = _clean(body.owner_name)
        draft.experiences = experiences
    await db.commit()
    await db.refresh(draft)
    return draft


def validate_for_publication(owner_name: str, experiences: list[dict[str, Any]]) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not _clean(owner_name):
        issues.append(ValidationIssue(field="owner_name", message="Owner name is required."))
    if not experiences:
        issues.append(ValidationIssue(field="experiences", message="At least one experience is required."))

    for index, exp in enumerate(experiences):
        prefix = f"experiences.{index}"
        if not _clean(exp.get("organization")):
            issues.append(ValidationIssue(field=f"{prefix}.organization", message="Organization is required."))
        if not _clean(exp.get("role")):
            issues.append(ValidationIssue(field=f"{prefix}.role", message="Role is required."))
        if not exp.get("start_month") or not exp.get("start_year"):
            issues.append(ValidationIssue(field=f"{prefix}.start", message="Start month and year are required."))
        if not exp.get("is_current") and (not exp.get("end_month") or not exp.get("end_year")):
            issues.append(ValidationIssue(field=f"{prefix}.end", message="End month and year are required unless this is the current role."))
        if not _clean(exp.get("summary")):
            issues.append(ValidationIssue(field=f"{prefix}.summary", message="Summary is required."))
        if not _clean(exp.get("outcome")):
            issues.append(ValidationIssue(field=f"{prefix}.outcome", message="Outcome is required."))

        start_year = exp.get("start_year")
        start_month = exp.get("start_month")
        end_year = exp.get("end_year")
        end_month = exp.get("end_month")
        if start_year and start_month and end_year and end_month:
            if (int(end_year), int(end_month)) < (int(start_year), int(start_month)):
                issues.append(ValidationIssue(field=f"{prefix}.end", message="End date cannot be before start date."))

    return issues


def build_snapshot(
    owner_id: str,
    version: int,
    owner_name: str,
    experiences: list[dict[str, Any]],
    published_at: datetime,
) -> dict[str, Any]:
    ordered = sorted(experiences, key=_experience_sort_key)
    return {
        "schema_version": "profile.snapshot.v1",
        "owner_id": owner_id,
        "owner_name": _clean(owner_name),
        "version": version,
        "published_at": published_at.isoformat(),
        "experiences": ordered,
    }


async def publish_draft(db: AsyncSession, owner_id: str) -> tuple[PublishedProfileSnapshot | None, list[ValidationIssue]]:
    draft = await get_draft(db, owner_id)
    if draft is None:
        return None, [ValidationIssue(field="profile", message="Save a draft before publishing.")]

    issues = validate_for_publication(draft.owner_name, draft.experiences)
    if issues:
        return None, issues

    latest_result = await db.execute(
        select(PublishedProfileSnapshot.version)
        .where(PublishedProfileSnapshot.owner_id == owner_id)
        .order_by(PublishedProfileSnapshot.version.desc())
        .limit(1)
    )
    latest_version = latest_result.scalar_one_or_none() or 0
    next_version = latest_version + 1
    published_at = datetime.now(timezone.utc)
    snapshot = build_snapshot(owner_id, next_version, draft.owner_name, draft.experiences, published_at)

    await db.execute(
        update(PublishedProfileSnapshot)
        .where(PublishedProfileSnapshot.owner_id == owner_id)
        .values(is_active=False)
    )
    published = PublishedProfileSnapshot(
        id=f"profile_snapshot_{uuid.uuid4().hex}",
        owner_id=owner_id,
        version=next_version,
        snapshot=snapshot,
        is_active=True,
        published_at=published_at,
    )
    db.add(published)
    await db.commit()
    await db.refresh(published)
    return published, []
