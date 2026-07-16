"""
SQLAlchemy models for conversation logging.

Schema:

  visitors       — one row per unique person (identified by email or session)
  conversations  — one row per visitor per day (messages grouped by day)
  messages       — every user question and assistant answer
  agent_actions  — log of async agent runs (intent classifier, notifications, etc.)

Anonymous visitors (no email captured yet) are stored with email=None.
When they submit their email on the rate limit screen, the visitor row is updated.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Visitor(Base):
    """
    One row per unique visitor.

    For anonymous visitors:  email is None, identified only by session_id.
    For identified visitors: email is set (either from identity gate or rate limit screen).
    When an anonymous visitor later provides their email, we update their row.
    """

    __tablename__ = "visitors"
    __table_args__ = (UniqueConstraint("owner_id", "email", name="uq_visitor_owner_email"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    # Nullable — set when visitor provides their email
    email: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    # The session that first created this visitor record (used to link email later)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)

    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
    total_sessions: Mapped[int] = mapped_column(Integer, default=1)

    # Set by the intent classifier agent after session ends
    intent_classification: Mapped[str | None] = mapped_column(String, nullable=True)
    company_inferred: Mapped[str | None] = mapped_column(String, nullable=True)
    visitor_name: Mapped[str | None] = mapped_column(String, nullable=True)

    conversations: Mapped[list[Conversation]] = relationship(
        "Conversation", back_populates="visitor", cascade="all, delete-orphan"
    )


class Conversation(Base):
    """
    One row per visitor per day.

    A visitor who chats on Monday and returns Tuesday gets two conversation rows
    under the same visitor record.
    """

    __tablename__ = "conversations"
    __table_args__ = (UniqueConstraint("session_id", "date", name="uq_conversation_session_date"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    visitor_id: Mapped[str] = mapped_column(String, ForeignKey("visitors.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False)
    session_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    # Set by the summary agent after session ends
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    follow_up_sent: Mapped[bool] = mapped_column(Boolean, default=False)

    visitor: Mapped[Visitor] = relationship("Visitor", back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan",
        order_by="Message.created_at",
    )
    agent_actions: Mapped[list[AgentAction]] = relationship(
        "AgentAction", back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    """Every user question and assistant answer."""

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String, nullable=False)   # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    answer_status: Mapped[str | None] = mapped_column(String, nullable=True)
    profile_snapshot_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    knowledge_backend: Mapped[str | None] = mapped_column(String, nullable=True)
    knowledge_backend_version: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="messages")
    evidence: Mapped[list[MessageEvidence]] = relationship(
        "MessageEvidence", back_populates="message", cascade="all, delete-orphan",
        order_by="MessageEvidence.position",
    )


class MessageEvidence(Base):
    """Public evidence attached to one completed assistant message."""

    __tablename__ = "message_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    message_id: Mapped[str] = mapped_column(
        String, ForeignKey("messages.id"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)

    message: Mapped[Message] = relationship("Message", back_populates="evidence")


class AgentAction(Base):
    """Log of every async agent run tied to a conversation."""

    __tablename__ = "agent_actions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    conversation_id: Mapped[str] = mapped_column(
        String, ForeignKey("conversations.id"), nullable=False, index=True
    )
    agent_type: Mapped[str] = mapped_column(String, nullable=False)  # "intent_classifier", etc.
    action: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="agent_actions")


class ProfileDraft(Base):
    """Mutable owner-edited canonical profile draft."""

    __tablename__ = "profile_drafts"

    owner_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_name: Mapped[str] = mapped_column(String, nullable=False, default="")
    experiences: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    projects: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    skills: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    education: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    achievements: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    personal_topics: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


class PublishedProfileSnapshot(Base):
    """Immutable versioned profile snapshot used by future retrieval backends."""

    __tablename__ = "published_profile_snapshots"
    __table_args__ = (
        UniqueConstraint("owner_id", "version", name="uq_published_profile_owner_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProfileIndexState(Base):
    """Tracks which published profile snapshot version has been indexed."""

    __tablename__ = "profile_index_states"

    owner_id: Mapped[str] = mapped_column(String, primary_key=True)
    indexed_snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    backend_version: Mapped[str | None] = mapped_column(String, nullable=True)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class ProfileIndexChunk(Base):
    """Searchable chunk derived from a published profile snapshot."""

    __tablename__ = "profile_index_chunks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    quote: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
