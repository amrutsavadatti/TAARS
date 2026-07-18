"""Schemas for published profile indexing and evidenced answers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

AnswerStatus = Literal["SUPPORTED", "PARTIAL", "UNANSWERABLE"]


class ProfileIndexChunkResponse(BaseModel):
    id: str
    source_type: str
    source_id: str
    title: str


class ProfileIndexStatusResponse(BaseModel):
    owner_id: str
    published_version: int | None
    candidate_version: int | None
    indexed_version: int | None
    indexed_backend_version: str | None
    indexed_at: str | None
    chunk_count: int
    is_stale: bool


class ProfileIndexResponse(ProfileIndexStatusResponse):
    chunks: list[ProfileIndexChunkResponse]


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


class AnswerEvidence(BaseModel):
    source_type: str
    source_id: str
    title: str
    quote: str


class AnswerMetadata(BaseModel):
    status: AnswerStatus
    evidence: list[AnswerEvidence]
    snapshot_version: int
    knowledge_backend: str
    knowledge_backend_version: str


class AskResponse(AnswerMetadata):
    answer: str
