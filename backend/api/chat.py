"""
Chat endpoint — SSE streaming.

GET /api/v1/chat/stream?q={question}&session_id={id}
Headers: X-API-Key: {owner_api_key}

Response: text/event-stream
    event: answer_metadata\ndata: {status, evidence, snapshot_version, ...}\n\n
    data: token1\n\n
    data: token2\n\n
    data: [DONE]\n\n

The client (browser EventSource or fetch with ReadableStream) reads
tokens as they arrive and appends them to the chat UI in real time.

Every completed assistant message is stored with its published-profile
version, retrieval backend, answer status, and ordered evidence.
"""

from __future__ import annotations

import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.answer_engine import AnswerEngine
from backend.database import get_db
from backend.owner import configured_owner_id
from backend.sse import sse_data, sse_done, sse_event

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

async def _token_stream(
    request: Request,
    question: str,
    session_id: str,
    owner_id: str,
    client_ip: str,
    visitor_email: str | None = None,
    visitor_name: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run the grounded answer pipeline and yield SSE-formatted frames.

    1. Load session history from Valkey
    2. Retrieve evidence from the indexed published profile
    3. Emit answer metadata, then stream grounded answer tokens
    4. Save the completed turn and its provenance
    5. Send [DONE] to signal end of stream

    If anything goes wrong, yield a graceful error frame so the browser
    always receives a complete response instead of a broken stream.
    """
    session_store = request.app.state.session_store

    try:
        # 1. Load history for this session (empty list if new session)
        history = await session_store.get_history(session_id)

        logger.info(
            "Chat stream start — session=%s  history_turns=%d  question=%r",
            session_id, len(history) // 2, question[:80],
        )

        # 2. Check rate limit / identity gate
        rate_limiter = request.app.state.rate_limiter
        # visitor_email is set by the widget after identity gate completes
        email = visitor_email
        rl_result = await rate_limiter.check(session_id, ip=client_ip, email=email)

        if not rl_result.allowed:
            # Yield a named SSE event so the widget knows to render
            # the RateLimitScreen or OTPGate — not a plain chat bubble
            yield rl_result.sse_event()
            yield sse_done()
            return

        # 3. Resolve evidence once, then stream the answer from that immutable plan.
        answer_streamer = getattr(request.app.state, "answer_streamer", None)
        answer_engine = (
            AnswerEngine(token_streamer=answer_streamer) if answer_streamer else AnswerEngine()
        )
        async with get_db() as db:
            plan = await answer_engine.plan(db, owner_id, question, history)

        yield sse_event("answer_metadata", plan.metadata)
        full_answer_parts: list[str] = []
        async for token in answer_engine.stream(plan):
            full_answer_parts.append(token)
            yield sse_data(token)

        # 4. Save to Valkey session + SQLite conversation log + increment rate counter
        full_answer = "".join(full_answer_parts)
        await session_store.append_turn(session_id, question=question, answer=full_answer)
        await rate_limiter.increment(session_id, ip=client_ip, email=visitor_email)

        from backend.storage.conversation_store import log_turn
        await log_turn(
            session_id=session_id,
            owner_id=owner_id,
            question=question,
            answer=full_answer,
            visitor_email=visitor_email,
            visitor_name=visitor_name,
            answer_metadata=plan.metadata,
        )

        yield sse_done()

        logger.info(
            "Chat stream complete — session=%s  answer_length=%d",
            session_id, len(full_answer),
        )

    except Exception as e:
        logger.error("Unexpected error in token stream: %s", e)
        error_msg = (
            f"Something went wrong. Please try again or contact "
            f"{settings.owner_name} at {settings.owner_contact_email}."
        )
        yield sse_data(error_msg)
        yield sse_done()


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------

def _validate_api_key(api_key: str | None) -> None:
    """
    Validate the API key.

    The key can arrive as:
      - X-API-Key request header  (used by curl / fetch)
      - ?api_key= query parameter (used by EventSource, which can't set headers)

    Raises HTTPException 401 if the key is missing.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Provide X-API-Key header or ?api_key= query param.",
        )
    # TODO: validate against per-owner key store once auth is implemented


# ---------------------------------------------------------------------------
# Chat stream endpoint
# ---------------------------------------------------------------------------

@router.get("/chat/stream")
async def chat_stream(
    request: Request,
    q: str = Query(..., min_length=1, max_length=1000, description="The visitor's question"),
    session_id: str = Query(
        default=None,
        description="Session ID for conversation continuity. Auto-generated if not provided.",
    ),
    api_key: str | None = Query(
        default=None,
        description="API key (query param fallback for EventSource, which cannot send headers).",
    ),
    visitor_email: str | None = Query(
        default=None,
        description="Visitor email — set by widget after identity gate is completed.",
    ),
    visitor_name: str | None = Query(
        default=None,
        description="Visitor name — set by widget after identity gate is completed.",
    ),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Stream an answer grounded in the indexed published profile.

    - Validates the API key (header or query param — EventSource uses query param)
    - Checks rate limit (IP-based when OTP off, email-based when OTP on)
    - Fires identity gate SSE event when OTP threshold is reached
    - Retrieves owner-approved evidence and streams answer tokens
    - Saves turn to session store and increments rate limit counter

    Each SSE frame is:  data: "token text here"\\n\\n
    Named SSE events:   event: rate_limit\\ndata: {...}\\n\\n
                        event: identity_gate\\ndata: {...}\\n\\n
    Final frame:        data: [DONE]\\n\\n
    """
    # Accept key from header OR query param (EventSource can't set headers)
    effective_key = x_api_key or api_key
    _validate_api_key(effective_key)

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Generate session ID if not provided
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info("No session_id provided — generated: %s", session_id)

    # Resolve owner from API key (stub — uses config default for now)
    owner_id = configured_owner_id()

    return StreamingResponse(
        _token_stream(
            request=request,
            question=q,
            session_id=session_id,
            owner_id=owner_id,
            client_ip=client_ip,
            visitor_email=visitor_email,
            visitor_name=visitor_name,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Session-Id": session_id,
        },
    )
