"""Public schemas for the canonical profile dashboard and snapshot contract."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ExperienceInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    organization: str = ""
    role: str = ""
    start_month: int | None = Field(default=None, ge=1, le=12)
    start_year: int | None = Field(default=None, ge=1900, le=2500)
    end_month: int | None = Field(default=None, ge=1, le=12)
    end_year: int | None = Field(default=None, ge=1900, le=2500)
    is_current: bool = False
    summary: str = ""
    outcome: str = ""
    display_order: int = 0


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    name: str = ""
    problem: str = ""
    contribution: str = ""
    outcome: str = ""
    measurable_impact: str = ""
    technologies: list[str] = Field(default_factory=list)
    collaborators: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    start_month: int | None = Field(default=None, ge=1, le=12)
    start_year: int | None = Field(default=None, ge=1900, le=2500)
    end_month: int | None = Field(default=None, ge=1, le=12)
    end_year: int | None = Field(default=None, ge=1900, le=2500)
    is_current: bool = False
    featured: bool = False
    visibility: Literal["public", "private"] = "public"
    display_order: int = 0


class SkillInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    name: str = ""
    category: str = ""
    aliases: list[str] = Field(default_factory=list)
    context: str = ""
    evidence: str = ""
    display_order: int = 0


class EducationInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    institution: str = ""
    credential: str = ""
    field: str = ""
    start_month: int | None = Field(default=None, ge=1, le=12)
    start_year: int | None = Field(default=None, ge=1900, le=2500)
    end_month: int | None = Field(default=None, ge=1, le=12)
    end_year: int | None = Field(default=None, ge=1900, le=2500)
    is_current: bool = False
    summary: str = ""
    outcome: str = ""
    display_order: int = 0


class AchievementInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    title: str = ""
    summary: str = ""
    outcome: str = ""
    month: int | None = Field(default=None, ge=1, le=12)
    year: int | None = Field(default=None, ge=1900, le=2500)
    featured: bool = False
    display_order: int = 0


class PersonalTopicInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str | None = None
    category: str = ""
    detail: str = ""
    approved: bool = True
    display_order: int = 0


class ProfileDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_name: str = ""
    experiences: list[ExperienceInput] = Field(default_factory=list)
    projects: list[ProjectInput] = Field(default_factory=list)
    skills: list[SkillInput] = Field(default_factory=list)
    education: list[EducationInput] = Field(default_factory=list)
    achievements: list[AchievementInput] = Field(default_factory=list)
    personal_topics: list[PersonalTopicInput] = Field(default_factory=list)


class ProfileDraftResponse(BaseModel):
    owner_id: str
    owner_name: str
    experiences: list[dict]
    projects: list[dict]
    skills: list[dict]
    education: list[dict]
    achievements: list[dict]
    personal_topics: list[dict]
    updated_at: str | None = None
    published_version: int | None = None
    has_published_snapshot: bool


class ValidationIssue(BaseModel):
    field: str
    message: str


class PublishErrorResponse(BaseModel):
    status: Literal["blocked"] = "blocked"
    issues: list[ValidationIssue]


class PublishedProfileResponse(BaseModel):
    owner_id: str
    version: int
    published_at: str
    snapshot: dict
