"""Published-profile indexing and retrieval adapter contract."""

from __future__ import annotations

import hashlib
import math
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Protocol

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ProfileIndexChunk, ProfileIndexState, PublishedProfileSnapshot
from backend.profile_indexing_schemas import ProfileIndexStatusResponse
from backend.profile_service import get_active_snapshot

EMBEDDING_DIMENSION = 384
TOKEN_RE = re.compile(r"[a-zA-Z0-9+#.]+")
QUESTION_STOP_WORDS = {
    "a", "about", "an", "and", "are", "can", "did", "do", "does", "for", "have",
    "he", "her", "his", "i", "in", "is", "me", "of", "on", "owner", "she", "tell",
    "that", "the", "their", "they", "to", "what", "when", "where", "which", "who", "with",
}
QUERY_ALIASES = {
    "career": {"experience", "role", "work"},
    "job": {"experience", "role", "work"},
    "occupation": {"experience", "role", "work"},
    "work": {"experience", "project", "role"},
    "study": {"education", "credential", "university"},
    "school": {"education", "university"},
    "built": {"build", "project", "contribution"},
    "technology": {"technologies", "skill"},
    "tech": {"technologies", "skill"},
    "skills": {"skill"},
    "projects": {"project"},
    "experiences": {"experience"},
    "achievements": {"achievement"},
    "interests": {"personal_topic"},
}


@dataclass(frozen=True)
class ProfileChunk:
    source_type: str
    source_id: str
    title: str
    quote: str
    text: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class EvidenceCandidate:
    chunk_id: str
    source_type: str
    source_id: str
    title: str
    quote: str
    text: str
    metadata: dict[str, Any]
    relevance: float


@dataclass(frozen=True)
class RetrievalResult:
    owner_name: str
    snapshot_version: int
    candidates: list[EvidenceCandidate]


class KnowledgeBackend(Protocol):
    name: str
    version: str

    async def status(self, db: AsyncSession, owner_id: str) -> ProfileIndexStatusResponse: ...

    async def index_active_profile(
        self, db: AsyncSession, owner_id: str
    ) -> tuple[ProfileIndexStatusResponse, list[ProfileIndexChunk]]: ...

    async def retrieve(
        self, db: AsyncSession, owner_id: str, question: str, *, limit: int = 3
    ) -> RetrievalResult: ...


def tokens(value: str) -> list[str]:
    return [match.group(0).lower() for match in TOKEN_RE.finditer(value)]


def meaningful_tokens(value: str) -> set[str]:
    base = {token for token in tokens(value) if token not in QUESTION_STOP_WORDS and len(token) > 1}
    expanded = set(base)
    for token in base:
        expanded.update(QUERY_ALIASES.get(token, set()))
    return expanded


def embed_text(value: str) -> list[float]:
    """Build a deterministic normalized feature vector for the local MVP."""
    vector = [0.0] * EMBEDDING_DIMENSION
    for token in meaningful_tokens(value):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % EMBEDDING_DIMENSION
        vector[index] += 1.0 if digest[4] % 2 == 0 else -1.0

    norm = math.sqrt(sum(component * component for component in vector))
    return [round(component / norm, 8) for component in vector] if norm else vector


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right)) if left and right else 0.0


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _join(parts: list[str]) -> str:
    return " ".join(part for part in parts if part)


def _date_range(item: dict[str, Any]) -> str:
    start = (
        f"{item.get('start_month')}/{item.get('start_year')}"
        if item.get("start_month") and item.get("start_year")
        else ""
    )
    end = "Present" if item.get("is_current") else (
        f"{item.get('end_month')}/{item.get('end_year')}"
        if item.get("end_month") and item.get("end_year")
        else ""
    )
    return " - ".join(part for part in (start, end) if part)


def _chunk(
    source_type: str,
    source_id: Any,
    title: str,
    quote: str,
    metadata: dict[str, Any] | None = None,
    prefix: str = "",
) -> ProfileChunk:
    text_value = _join([source_type, title, prefix, quote])
    return ProfileChunk(
        source_type=source_type,
        source_id=_clean(source_id),
        title=title,
        quote=quote,
        text=text_value,
        metadata=metadata or {},
    )


def build_profile_chunks(snapshot: dict[str, Any]) -> list[ProfileChunk]:
    chunks: list[ProfileChunk] = []
    for item in snapshot.get("experiences", []):
        title = _join([
            _clean(item.get("role")),
            f"at {_clean(item.get('organization'))}" if item.get("organization") else "",
        ])
        chunks.append(_chunk(
            "experience", item.get("id"), title,
            _join([_clean(item.get("summary")), _clean(item.get("outcome"))]),
            {"date_range": _date_range(item)}, _date_range(item),
        ))

    for item in snapshot.get("projects", []):
        if item.get("visibility", "public") != "public":
            continue
        technologies = item.get("technologies", [])
        chunks.append(_chunk(
            "project", item.get("id"), _clean(item.get("name")),
            _join([
                _clean(item.get("problem")), _clean(item.get("contribution")),
                _clean(item.get("outcome")), _clean(item.get("measurable_impact")),
                " ".join(technologies),
            ]),
            {"date_range": _date_range(item), "technologies": technologies}, _date_range(item),
        ))

    for item in snapshot.get("skills", []):
        chunks.append(_chunk(
            "skill", item.get("id"), _clean(item.get("name")),
            _join([
                _clean(item.get("category")), " ".join(item.get("aliases", [])),
                _clean(item.get("context")), _clean(item.get("evidence")),
            ]),
            {"category": item.get("category")},
        ))

    for item in snapshot.get("education", []):
        title = _join([
            _clean(item.get("credential")), _clean(item.get("field")),
            f"at {_clean(item.get('institution'))}" if item.get("institution") else "",
        ])
        chunks.append(_chunk(
            "education", item.get("id"), title,
            _join([_clean(item.get("summary")), _clean(item.get("outcome"))]),
            {"date_range": _date_range(item)}, _date_range(item),
        ))

    for item in snapshot.get("achievements", []):
        chunks.append(_chunk(
            "achievement", item.get("id"), _clean(item.get("title")),
            _join([_clean(item.get("summary")), _clean(item.get("outcome"))]),
            {"month": item.get("month"), "year": item.get("year")},
        ))

    for item in snapshot.get("personal_topics", []):
        if not item.get("approved"):
            continue
        chunks.append(_chunk(
            "personal_topic", item.get("id"), _clean(item.get("category")),
            _clean(item.get("detail")), {"approved": True},
        ))

    return [chunk for chunk in chunks if chunk.source_id and chunk.title and chunk.quote]


def _vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{value:.8f}" for value in vector) + "]"


def _relevance(question: str, chunk_text: str, vector_score: float) -> float:
    question_terms = meaningful_tokens(question)
    overlap = len(question_terms & meaningful_tokens(chunk_text)) / max(1, len(question_terms))
    return round((0.7 * overlap) + (0.3 * max(0.0, vector_score)), 6)


class PostgresPgvectorKnowledgeBackend:
    """SQLAlchemy adapter with pgvector ranking and a SQLite test fallback."""

    name = "postgres_pgvector"
    version = "profile-hash-384-v2"

    async def _state(self, db: AsyncSession, owner_id: str) -> ProfileIndexState | None:
        result = await db.execute(select(ProfileIndexState).where(ProfileIndexState.owner_id == owner_id))
        return result.scalar_one_or_none()

    async def status(self, db: AsyncSession, owner_id: str) -> ProfileIndexStatusResponse:
        active = await get_active_snapshot(db, owner_id)
        state = await self._state(db, owner_id)
        return ProfileIndexStatusResponse(
            owner_id=owner_id,
            published_version=active.version if active else None,
            indexed_version=state.indexed_snapshot_version if state else None,
            indexed_backend_version=state.backend_version if state else None,
            indexed_at=state.indexed_at.isoformat() if state else None,
            chunk_count=state.chunk_count if state else 0,
            is_stale=bool(
                active and (
                    state is None
                    or state.indexed_snapshot_version != active.version
                    or state.backend_version != self.version
                )
            ),
        )

    async def index_active_profile(
        self, db: AsyncSession, owner_id: str
    ) -> tuple[ProfileIndexStatusResponse, list[ProfileIndexChunk]]:
        active = await get_active_snapshot(db, owner_id)
        if active is None:
            raise ValueError("Publish a profile before indexing.")

        state = await self._state(db, owner_id)
        if (
            state
            and state.indexed_snapshot_version == active.version
            and state.backend_version == self.version
        ):
            result = await db.execute(
                select(ProfileIndexChunk)
                .where(
                    ProfileIndexChunk.owner_id == owner_id,
                    ProfileIndexChunk.snapshot_version == active.version,
                )
                .order_by(ProfileIndexChunk.source_type, ProfileIndexChunk.title)
            )
            return await self.status(db, owner_id), list(result.scalars().all())

        await db.execute(delete(ProfileIndexChunk).where(ProfileIndexChunk.owner_id == owner_id))
        stored_chunks: list[ProfileIndexChunk] = []
        for chunk in build_profile_chunks(active.snapshot):
            embedding = embed_text(chunk.text)
            stored = ProfileIndexChunk(
                id=f"profile_chunk_{uuid.uuid4().hex}", owner_id=owner_id,
                snapshot_version=active.version, source_type=chunk.source_type,
                source_id=chunk.source_id, title=chunk.title, quote=chunk.quote,
                text=chunk.text, chunk_metadata=chunk.metadata, embedding=embedding,
            )
            db.add(stored)
            stored_chunks.append(stored)

        now = datetime.now(timezone.utc)
        if state is None:
            db.add(ProfileIndexState(
                owner_id=owner_id, indexed_snapshot_version=active.version,
                backend_version=self.version, chunk_count=len(stored_chunks), indexed_at=now,
            ))
        else:
            state.indexed_snapshot_version = active.version
            state.backend_version = self.version
            state.chunk_count = len(stored_chunks)
            state.indexed_at = now

        await db.flush()
        if db.bind and db.bind.dialect.name == "postgresql":
            for chunk in stored_chunks:
                await db.execute(
                    text(
                        "UPDATE profile_index_chunks "
                        "SET embedding_vector = CAST(:embedding AS vector) WHERE id = :chunk_id"
                    ),
                    {"embedding": _vector_literal(chunk.embedding), "chunk_id": chunk.id},
                )
        await db.commit()
        return await self.status(db, owner_id), stored_chunks

    async def retrieve(
        self, db: AsyncSession, owner_id: str, question: str, *, limit: int = 3
    ) -> RetrievalResult:
        state = await self._state(db, owner_id)
        if state is None:
            raise ValueError("Index the published profile before asking questions.")

        snapshot_result = await db.execute(
            select(PublishedProfileSnapshot).where(
                PublishedProfileSnapshot.owner_id == owner_id,
                PublishedProfileSnapshot.version == state.indexed_snapshot_version,
            )
        )
        indexed_snapshot = snapshot_result.scalar_one_or_none()
        if indexed_snapshot is None:
            raise ValueError("The indexed published profile snapshot is unavailable.")

        query_embedding = embed_text(question)
        if db.bind and db.bind.dialect.name == "postgresql":
            rows = await self._postgres_rows(
                db, owner_id, state.indexed_snapshot_version, query_embedding, max(limit * 4, limit)
            )
        else:
            rows = await self._sqlite_rows(db, owner_id, state.indexed_snapshot_version, query_embedding)

        candidates = [
            EvidenceCandidate(
                chunk_id=row["id"], source_type=row["source_type"], source_id=row["source_id"],
                title=row["title"], quote=row["quote"], text=row["text"],
                metadata=row["chunk_metadata"] or {},
                relevance=_relevance(question, row["text"], float(row["vector_score"] or 0.0)),
            )
            for row in rows
        ]
        candidates.sort(key=lambda candidate: (candidate.relevance, candidate.title), reverse=True)
        return RetrievalResult(
            owner_name=_clean(indexed_snapshot.snapshot.get("owner_name")),
            snapshot_version=state.indexed_snapshot_version,
            candidates=candidates[:limit],
        )

    async def _postgres_rows(
        self, db: AsyncSession, owner_id: str, snapshot_version: int,
        query_embedding: list[float], limit: int,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            text(
                "SELECT id, source_type, source_id, title, quote, text, chunk_metadata, "
                "GREATEST(0, 1 - (embedding_vector <=> CAST(:embedding AS vector))) AS vector_score "
                "FROM profile_index_chunks "
                "WHERE owner_id = :owner_id AND snapshot_version = :snapshot_version "
                "AND embedding_vector IS NOT NULL "
                "ORDER BY embedding_vector <=> CAST(:embedding AS vector) LIMIT :limit"
            ),
            {
                "embedding": _vector_literal(query_embedding), "owner_id": owner_id,
                "snapshot_version": snapshot_version, "limit": limit,
            },
        )
        return [dict(row) for row in result.mappings().all()]

    async def _sqlite_rows(
        self, db: AsyncSession, owner_id: str, snapshot_version: int,
        query_embedding: list[float],
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(ProfileIndexChunk).where(
                ProfileIndexChunk.owner_id == owner_id,
                ProfileIndexChunk.snapshot_version == snapshot_version,
            )
        )
        return [
            {
                "id": chunk.id, "source_type": chunk.source_type, "source_id": chunk.source_id,
                "title": chunk.title, "quote": chunk.quote, "text": chunk.text,
                "chunk_metadata": chunk.chunk_metadata,
                "vector_score": cosine_similarity(query_embedding, chunk.embedding),
            }
            for chunk in result.scalars().all()
        ]


DEFAULT_KNOWLEDGE_BACKEND = PostgresPgvectorKnowledgeBackend()
