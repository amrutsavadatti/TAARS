"""
Chat endpoint — SSE streaming.

GET /api/v1/chat/stream?q={question}&session_id={id}
Headers: X-API-Key: {owner_api_key}

Response: text/event-stream
    data: token1\n\n
    data: token2\n\n
    data: [DONE]\n\n

The client (browser EventSource or fetch with ReadableStream) reads
tokens as they arrive and appends them to the chat UI in real time.

Rate limiting and session history are stubs for now — they will be
wired up once session_store.py and rate_limiter.py are implemented.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Header, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from backend.config import settings
from backend.core.rag_engine import stream_answer

logger = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------

def _sse(data: str) -> str:
    """
    Format a single SSE message.

    SSE protocol:
      - Each message is "data: {payload}\n\n"
      - The double newline signals the end of one message to the client
      - The client's EventSource fires an 'message' event for each one

    We JSON-encode the token so special characters (newlines inside
    the token itself, quotes, etc.) don't break the SSE framing.
    """
    return f"data: {json.dumps(data)}\n\n"


def _sse_done() -> str:
    """Terminal SSE frame — tells the client the stream is finished."""
    return "data: [DONE]\n\n"


async def _token_stream(
    request: Request,
    question: str,
    session_id: str,
    owner_id: str,
    client_ip: str,
) -> AsyncGenerator[str, None]:
    """
    Async generator that runs the RAG pipeline and yields SSE-formatted frames.

    1. Load session history from Valkey
    2. Call rag_engine.stream_answer() — streams tokens
    3. Wrap each token in SSE format and yield to browser
    4. Assemble full answer, save turn to session store
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
        email = None  # TODO: populated from JWT when OTP is ON
        rl_result = await rate_limiter.check(session_id, ip=client_ip, email=email)

        if not rl_result.allowed:
            # Yield a named SSE event so the widget knows to render
            # the RateLimitScreen or OTPGate — not a plain chat bubble
            yield rl_result.sse_event()
            yield _sse_done()
            return

        # 3. Stream answer token by token, collecting the full response
        full_answer_parts: list[str] = []

        async for token in stream_answer(question, history=history, owner_id=owner_id):
            full_answer_parts.append(token)
            yield _sse(token)

        yield _sse_done()

        # 4. Save the completed turn + increment rate limit counter
        full_answer = "".join(full_answer_parts)
        await session_store.append_turn(session_id, question=question, answer=full_answer)
        await rate_limiter.increment(session_id, ip=client_ip, email=email)

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
        yield _sse(error_msg)
        yield _sse_done()


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------

def _validate_api_key(api_key: str | None) -> None:
    """
    Validate the X-API-Key header against the configured owner API key.

    For now we just check it's not missing. Full per-owner key validation
    will be added with the auth middleware.

    Raises HTTPException 401 if the key is missing or invalid.
    """
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header.",
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
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    """
    Stream a RAG-powered answer to the visitor's question.

    - Validates the API key
    - Checks rate limit (IP-based when OTP off, email-based when OTP on)
    - Fires identity gate SSE event when OTP threshold is reached
    - Runs the full RAG pipeline and streams tokens
    - Saves turn to session store and increments rate limit counter

    Each SSE frame is:  data: "token text here"\\n\\n
    Named SSE events:   event: rate_limit\\ndata: {...}\\n\\n
                        event: identity_gate\\ndata: {...}\\n\\n
    Final frame:        data: [DONE]\\n\\n
    """
    # Validate API key
    _validate_api_key(x_api_key)

    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"

    # Generate session ID if not provided
    # The widget sends one; curl/direct API calls may omit it
    if not session_id:
        session_id = str(uuid.uuid4())
        logger.info("No session_id provided — generated: %s", session_id)

    # Resolve owner from API key (stub — uses config default for now)
    owner_id = settings.owner_name

    return StreamingResponse(
        _token_stream(request=request, question=q, session_id=session_id, owner_id=owner_id, client_ip=client_ip),
        media_type="text/event-stream",
        headers={
            # Prevent proxies and browsers from buffering the stream
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            # Return the session ID so the client can use it for follow-ups
            "X-Session-Id": session_id,
        },
    )
