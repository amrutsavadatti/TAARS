"""Canonical profile draft, validation, and publication service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ProfileDraft, PublishedProfileSnapshot
from backend.profile_schemas import (
    AchievementInput,
    EducationInput,
    ExperienceInput,
    PersonalTopicInput,
    ProfileDraftInput,
    ProjectInput,
    SkillInput,
    ValidationIssue,
)


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _clean_list(values: list[str]) -> list[str]:
    return [cleaned for value in values if (cleaned := _clean(value))]


def _sort_key(item: dict[str, Any]) -> tuple[int, str]:
    return (int(item.get("display_order", 0)), str(item.get("id", "")))


def _stable_id(value: str | None, prefix: str) -> str:
    return _clean(value) or f"{prefix}_{uuid.uuid4().hex}"


def normalize_experiences(experiences: list[ExperienceInput]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, exp in enumerate(experiences):
        normalized.append(
            {
                "id": _stable_id(exp.id, "exp"),
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
    return sorted(normalized, key=_sort_key)


def normalize_projects(projects: list[ProjectInput]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, project in enumerate(projects):
        normalized.append(
            {
                "id": _stable_id(project.id, "proj"),
                "type": "project",
                "name": _clean(project.name),
                "problem": _clean(project.problem),
                "contribution": _clean(project.contribution),
                "outcome": _clean(project.outcome),
                "measurable_impact": _clean(project.measurable_impact),
                "technologies": _clean_list(project.technologies),
                "collaborators": _clean_list(project.collaborators),
                "links": _clean_list(project.links),
                "start_month": project.start_month,
                "start_year": project.start_year,
                "end_month": None if project.is_current else project.end_month,
                "end_year": None if project.is_current else project.end_year,
                "is_current": project.is_current,
                "featured": project.featured,
                "visibility": project.visibility,
                "display_order": project.display_order if project.display_order is not None else index,
            }
        )
    return sorted(normalized, key=_sort_key)


def normalize_skills(skills: list[SkillInput]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, skill in enumerate(skills):
        normalized.append(
            {
                "id": _stable_id(skill.id, "skill"),
                "type": "skill",
                "name": _clean(skill.name),
                "category": _clean(skill.category),
                "aliases": _clean_list(skill.aliases),
                "context": _clean(skill.context),
                "evidence": _clean(skill.evidence),
                "display_order": skill.display_order if skill.display_order is not None else index,
            }
        )
    return sorted(normalized, key=_sort_key)


def normalize_education(education: list[EducationInput]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(education):
        normalized.append(
            {
                "id": _stable_id(item.id, "edu"),
                "type": "education",
                "institution": _clean(item.institution),
                "credential": _clean(item.credential),
                "field": _clean(item.field),
                "start_month": item.start_month,
                "start_year": item.start_year,
                "end_month": None if item.is_current else item.end_month,
                "end_year": None if item.is_current else item.end_year,
                "is_current": item.is_current,
                "summary": _clean(item.summary),
                "outcome": _clean(item.outcome),
                "display_order": item.display_order if item.display_order is not None else index,
            }
        )
    return sorted(normalized, key=_sort_key)


def normalize_achievements(achievements: list[AchievementInput]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, item in enumerate(achievements):
        normalized.append(
            {
                "id": _stable_id(item.id, "ach"),
                "type": "achievement",
                "title": _clean(item.title),
                "summary": _clean(item.summary),
                "outcome": _clean(item.outcome),
                "month": item.month,
                "year": item.year,
                "featured": item.featured,
                "display_order": item.display_order if item.display_order is not None else index,
            }
        )
    return sorted(normalized, key=_sort_key)


def normalize_personal_topics(topics: list[PersonalTopicInput]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, topic in enumerate(topics):
        normalized.append(
            {
                "id": _stable_id(topic.id, "topic"),
                "type": "personal_topic",
                "category": _clean(topic.category),
                "detail": _clean(topic.detail),
                "approved": topic.approved,
                "display_order": topic.display_order if topic.display_order is not None else index,
            }
        )
    return sorted(normalized, key=_sort_key)


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
    payload = {
        "owner_name": _clean(body.owner_name),
        "experiences": normalize_experiences(body.experiences),
        "projects": normalize_projects(body.projects),
        "skills": normalize_skills(body.skills),
        "education": normalize_education(body.education),
        "achievements": normalize_achievements(body.achievements),
        "personal_topics": normalize_personal_topics(body.personal_topics),
    }
    if draft is None:
        draft = ProfileDraft(owner_id=owner_id, **payload)
        db.add(draft)
    else:
        for key, value in payload.items():
            setattr(draft, key, value)
    await db.commit()
    await db.refresh(draft)
    return draft


def _validate_dates(
    issues: list[ValidationIssue],
    prefix: str,
    item: dict[str, Any],
    *,
    require_dates: bool = True,
) -> None:
    if require_dates and (not item.get("start_month") or not item.get("start_year")):
        issues.append(ValidationIssue(field=f"{prefix}.start", message="Start month and year are required."))
    if require_dates and not item.get("is_current") and (not item.get("end_month") or not item.get("end_year")):
        issues.append(
            ValidationIssue(
                field=f"{prefix}.end",
                message="End month and year are required unless this is current.",
            )
        )
    start_year = item.get("start_year")
    start_month = item.get("start_month")
    end_year = item.get("end_year")
    end_month = item.get("end_month")
    if start_year and start_month and end_year and end_month:
        if (int(end_year), int(end_month)) < (int(start_year), int(start_month)):
            issues.append(ValidationIssue(field=f"{prefix}.end", message="End date cannot be before start date."))


def validate_for_publication(draft: ProfileDraft) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    if not _clean(draft.owner_name):
        issues.append(ValidationIssue(field="owner_name", message="Owner name is required."))
    if not draft.experiences and not draft.projects:
        issues.append(
            ValidationIssue(
                field="profile",
                message="At least one experience or project is required before publication.",
            )
        )

    for index, exp in enumerate(draft.experiences):
        prefix = f"experiences.{index}"
        if not _clean(exp.get("organization")):
            issues.append(ValidationIssue(field=f"{prefix}.organization", message="Organization is required."))
        if not _clean(exp.get("role")):
            issues.append(ValidationIssue(field=f"{prefix}.role", message="Role is required."))
        _validate_dates(issues, prefix, exp)
        if not _clean(exp.get("summary")):
            issues.append(ValidationIssue(field=f"{prefix}.summary", message="Summary is required."))

    for index, project in enumerate(draft.projects):
        prefix = f"projects.{index}"
        if not _clean(project.get("name")):
            issues.append(ValidationIssue(field=f"{prefix}.name", message="Project name is required."))
        if not _clean(project.get("problem")):
            issues.append(ValidationIssue(field=f"{prefix}.problem", message="Problem is required."))
        if not _clean(project.get("contribution")):
            issues.append(ValidationIssue(field=f"{prefix}.contribution", message="Contribution is required."))
        _validate_dates(issues, prefix, project)

    for index, skill in enumerate(draft.skills):
        prefix = f"skills.{index}"
        if not _clean(skill.get("name")):
            issues.append(ValidationIssue(field=f"{prefix}.name", message="Skill name is required."))

    for index, item in enumerate(draft.education):
        prefix = f"education.{index}"
        if not _clean(item.get("institution")):
            issues.append(ValidationIssue(field=f"{prefix}.institution", message="Institution is required."))
        if not _clean(item.get("credential")):
            issues.append(ValidationIssue(field=f"{prefix}.credential", message="Credential is required."))
        _validate_dates(issues, prefix, item)

    for index, achievement in enumerate(draft.achievements):
        prefix = f"achievements.{index}"
        if not _clean(achievement.get("title")):
            issues.append(ValidationIssue(field=f"{prefix}.title", message="Title is required."))
        if not _clean(achievement.get("summary")):
            issues.append(ValidationIssue(field=f"{prefix}.summary", message="Summary is required."))

    for index, topic in enumerate(draft.personal_topics):
        prefix = f"personal_topics.{index}"
        if topic.get("approved") and not _clean(topic.get("category")):
            issues.append(ValidationIssue(field=f"{prefix}.category", message="Category is required."))
        if topic.get("approved") and not _clean(topic.get("detail")):
            issues.append(ValidationIssue(field=f"{prefix}.detail", message="Detail is required."))

    return issues


def build_snapshot(
    owner_id: str,
    version: int,
    draft: ProfileDraft,
    published_at: datetime,
) -> dict[str, Any]:
    return {
        "schema_version": "profile.snapshot.v1",
        "owner_id": owner_id,
        "owner_name": _clean(draft.owner_name),
        "version": version,
        "published_at": published_at.isoformat(),
        "experiences": sorted(draft.experiences, key=_sort_key),
        "projects": sorted(draft.projects, key=_sort_key),
        "skills": sorted(draft.skills, key=_sort_key),
        "education": sorted(draft.education, key=_sort_key),
        "achievements": sorted(draft.achievements, key=_sort_key),
        "personal_topics": [
            topic for topic in sorted(draft.personal_topics, key=_sort_key) if topic.get("approved")
        ],
    }


async def publish_draft(db: AsyncSession, owner_id: str) -> tuple[PublishedProfileSnapshot | None, list[ValidationIssue]]:
    draft = await get_draft(db, owner_id)
    if draft is None:
        return None, [ValidationIssue(field="profile", message="Save a draft before publishing.")]

    issues = validate_for_publication(draft)
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
    snapshot = build_snapshot(owner_id, next_version, draft, published_at)

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
