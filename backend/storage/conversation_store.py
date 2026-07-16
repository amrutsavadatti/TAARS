"""
ConversationStore — high-level helpers for conversation logging.

All database operations go through this module so chat.py and leads.py
stay free of raw SQLAlchemy queries.

Public API:
    await log_turn(session_id, owner_id, question, answer,
                   visitor_email=None, visitor_name=None)
        → Called after every successful chat turn. Creates visitor +
          conversation rows on first call; appends messages on subsequent calls.

    await attach_email(session_id, email, name=None)
        → Called when visitor submits their email (rate limit screen or
          identity gate). Updates the visitor row.

    await get_conversations_for_owner(owner_id, limit=50)
        → Returns recent conversations for the admin/agent layer.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from backend.database import get_db
from backend.models import Conversation, Message, MessageEvidence, Visitor
from backend.profile_indexing_schemas import AnswerMetadata

logger = logging.getLogger(__name__)


def _new_id() -> str:
    return str(uuid.uuid4())


def _today() -> date:
    return datetime.now(timezone.utc).date()


async def log_turn(
    session_id: str,
    owner_id: str,
    question: str,
    answer: str,
    visitor_email: str | None = None,
    visitor_name: str | None = None,
    answer_metadata: AnswerMetadata | None = None,
) -> None:
    """
    Persist one conversation turn (user question + assistant answer).

    On every call this function:
      1. Gets or creates a Visitor for this session.
      2. Gets or creates a Conversation for this visitor + today's date.
      3. Appends two Message rows (user + assistant).
      4. Increments the conversation message_count.

    Safe to call after every stream — idempotent visitor/conversation creation.
    Fails silently so a DB error never breaks the chat.
    """
    try:
        async with get_db() as db:
            # ── 1. Visitor ────────────────────────────────────────────
            visitor = await _get_or_create_visitor(
                db, session_id, owner_id, visitor_email, visitor_name
            )

            # ── 2. Conversation (one per session per day) ─────────────
            conversation = await _get_or_create_conversation(
                db, visitor.id, owner_id, session_id
            )

            # ── 3. Messages ───────────────────────────────────────────
            now = datetime.now(timezone.utc)
            db.add(Message(
                id=_new_id(),
                conversation_id=conversation.id,
                role="user",
                content=question,
                created_at=now,
            ))
            assistant_message_id = _new_id()
            db.add(Message(
                id=assistant_message_id,
                conversation_id=conversation.id,
                role="assistant",
                content=answer,
                answer_status=answer_metadata.status if answer_metadata else None,
                profile_snapshot_version=answer_metadata.snapshot_version if answer_metadata else None,
                knowledge_backend=answer_metadata.knowledge_backend if answer_metadata else None,
                knowledge_backend_version=(
                    answer_metadata.knowledge_backend_version if answer_metadata else None
                ),
                created_at=now,
            ))
            if answer_metadata:
                db.add_all([
                    MessageEvidence(
                        id=_new_id(), message_id=assistant_message_id, position=position,
                        source_type=evidence.source_type, source_id=evidence.source_id,
                        title=evidence.title, quote=evidence.quote,
                    )
                    for position, evidence in enumerate(answer_metadata.evidence)
                ])

            # ── 4. Increment message count ────────────────────────────
            await db.execute(
                update(Conversation)
                .where(Conversation.id == conversation.id)
                .values(message_count=Conversation.message_count + 2)
            )

            # Update visitor's last_seen timestamp
            await db.execute(
                update(Visitor)
                .where(Visitor.id == visitor.id)
                .values(last_seen_at=now)
            )

            await db.commit()

            logger.debug(
                "Logged turn — session=%s  conversation=%s  msg_count=%d",
                session_id, conversation.id, conversation.message_count + 2,
            )

    except Exception as e:
        logger.error("conversation_store.log_turn failed: %s", e)


async def attach_email(
    session_id: str,
    email: str,
    name: str | None = None,
) -> None:
    """
    Associate a verified email (and optional name) with an existing visitor.

    Called when:
      - Visitor submits email on the rate limit screen (leads.py)
      - Visitor completes the identity gate form

    If a visitor row with that email already exists (returning user), we just
    update their last_seen_at. Otherwise we update the anonymous row for this session.
    """
    try:
        async with get_db() as db:
            email_lower = email.lower().strip()

            # Check if a visitor with this email already exists
            result = await db.execute(
                select(Visitor).where(Visitor.email == email_lower)
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Returning visitor — update last seen
                await db.execute(
                    update(Visitor)
                    .where(Visitor.id == existing.id)
                    .values(
                        last_seen_at=datetime.now(timezone.utc),
                        total_sessions=Visitor.total_sessions + 1,
                        visitor_name=name or existing.visitor_name,
                    )
                )
            else:
                # Anonymous visitor — find by session_id and attach email
                await db.execute(
                    update(Visitor)
                    .where(Visitor.session_id == session_id, Visitor.email.is_(None))
                    .values(
                        email=email_lower,
                        visitor_name=name,
                        last_seen_at=datetime.now(timezone.utc),
                    )
                )

            await db.commit()
            logger.info("Attached email to visitor — session=%s  email=%s", session_id, email_lower)

    except Exception as e:
        logger.error("conversation_store.attach_email failed: %s", e)


async def get_conversations_for_owner(
    owner_id: str,
    limit: int = 50,
) -> list[Conversation]:
    """Return recent conversations for a given owner (for agents / analytics)."""
    try:
        async with get_db() as db:
            result = await db.execute(
                select(Conversation)
                .where(Conversation.owner_id == owner_id)
                .order_by(Conversation.started_at.desc())
                .limit(limit)
            )
            return list(result.scalars().all())
    except Exception as e:
        logger.error("conversation_store.get_conversations_for_owner failed: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _get_or_create_visitor(
    db,
    session_id: str,
    owner_id: str,
    email: str | None,
    name: str | None,
) -> Visitor:
    """
    Find an existing visitor by session_id, or create a new one.

    If email is provided and a visitor with that email already exists,
    return that visitor (handles the case where a known visitor starts
    a new session).
    """
    # Try by email first (identified visitor returning in a new session)
    if email:
        result = await db.execute(
            select(Visitor).where(
                Visitor.owner_id == owner_id,
                Visitor.email == email.lower().strip(),
            )
        )
        visitor = result.scalar_one_or_none()
        if visitor:
            return visitor

    # Try by session_id (same session, second+ question)
    result = await db.execute(
        select(Visitor).where(Visitor.session_id == session_id)
    )
    visitor = result.scalar_one_or_none()
    if visitor:
        return visitor

    # Create new anonymous (or identified) visitor
    visitor = Visitor(
        id=_new_id(),
        owner_id=owner_id,
        session_id=session_id,
        email=email.lower().strip() if email else None,
        visitor_name=name,
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db.add(visitor)
    # Flush to get the id before we use it in conversation
    try:
        await db.flush()
    except IntegrityError:
        # Race condition — another request created the visitor in parallel
        await db.rollback()
        result = await db.execute(
            select(Visitor).where(Visitor.session_id == session_id)
        )
        visitor = result.scalar_one()

    return visitor


async def _get_or_create_conversation(
    db,
    visitor_id: str,
    owner_id: str,
    session_id: str,
) -> Conversation:
    """
    Find today's conversation for this session, or create a new one.

    One conversation per session per day — if the visitor returns tomorrow
    they get a fresh conversation row under the same visitor.
    """
    today = _today()

    result = await db.execute(
        select(Conversation).where(
            Conversation.session_id == session_id,
            Conversation.date == today,
        )
    )
    conversation = result.scalar_one_or_none()
    if conversation:
        return conversation

    conversation = Conversation(
        id=_new_id(),
        visitor_id=visitor_id,
        owner_id=owner_id,
        session_id=session_id,
        date=today,
        started_at=datetime.now(timezone.utc),
    )
    db.add(conversation)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        result = await db.execute(
            select(Conversation).where(
                Conversation.session_id == session_id,
                Conversation.date == today,
            )
        )
        conversation = result.scalar_one()

    return conversation
