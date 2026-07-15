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


class ProfileDraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    owner_name: str = ""
    experiences: list[ExperienceInput] = Field(default_factory=list)


class ProfileDraftResponse(BaseModel):
    owner_id: str
    owner_name: str
    experiences: list[dict]
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
