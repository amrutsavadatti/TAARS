"""
RAG Engine — the single entry point for the chat pipeline.

Orchestrates the full flow:
    question + history
        │
        ├─1─▶ retriever.retrieve()
        │         │
        │         ├── no chunks  ──▶ yield canned "I don't know" response
        │         │                  (LLM is never called — saves tokens, no hallucination)
        │         │
        │         └── chunks found
        │                 │
        ├─2─▶            prompt_builder.build_prompt()
        │                 │
        ├─3─▶            llm_client.stream_response()
        │                 │
        └─────────────── yield tokens one by one

The function always returns an AsyncGenerator[str, None].
The chat SSE endpoint just iterates over it and sends each token to the browser.
It never needs to know whether it's a real LLM response or a canned reply.

Public API:
    async for token in stream_answer(question, history, owner_id):
        yield token
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from backend.config import settings
from backend.core.prompt_builder import build_prompt, no_context_response
from backend.core.retriever import get_retriever

logger = logging.getLogger(__name__)


async def stream_answer(
    question: str,
    history: list[dict] | None = None,
    owner_id: str | None = None,
) -> AsyncGenerator[str, None]:
    """
    Run the full RAG pipeline and stream the answer token by token.

    Args:
        question: The visitor's current question (raw string).
        history:  Conversation history — list of {"role": ..., "content": ...} dicts.
                  Pass None or [] for the first message in a session.
        owner_id: Portfolio owner identifier. Defaults to OWNER_NAME in config.

    Yields:
        str — one token at a time.
        The chat endpoint wraps each in an SSE frame and sends it to the browser.

    This function never raises — all errors are caught and yielded as
    user-friendly messages so the SSE stream always closes cleanly.
    """
    history = history or []
    owner_id = owner_id or settings.owner_name

    logger.info("RAG pipeline start — owner=%s  question=%r", owner_id, question[:80])

    # ------------------------------------------------------------------
    # Step 1 — Retrieve relevant chunks
    # ------------------------------------------------------------------
    try:
        retriever = get_retriever(owner_id=owner_id)
        chunks = retriever.retrieve(question)
    except Exception as e:
        logger.error("Retrieval failed: %s", e)
        yield "I'm having trouble searching the knowledge base right now. "
        yield f"Please try again or contact {settings.owner_name} at {settings.owner_contact_email}."
        return

    # ------------------------------------------------------------------
    # Step 2 — No relevant content found → canned response, skip LLM
    # ------------------------------------------------------------------
    if not chunks:
        logger.info("No relevant chunks found — returning canned response.")
        yield no_context_response()
        return

    logger.info("Retrieved %d chunks — calling LLM.", len(chunks))

    # ------------------------------------------------------------------
    # Step 3 — Build the prompt
    # ------------------------------------------------------------------
    try:
        system_prompt, user_message = build_prompt(chunks, history, question)
    except Exception as e:
        logger.error("Prompt building failed: %s", e)
        yield "Something went wrong preparing your answer. "
        yield f"Please reach out to {settings.owner_name} directly at {settings.owner_contact_email}."
        return

    # ------------------------------------------------------------------
    # Step 4 — Stream LLM response
    # ------------------------------------------------------------------
    # Import here to avoid circular imports and so the module loads even
    # when no API key is configured (useful for testing retrieval alone).
    from backend.core.llm_client import stream_response

    try:
        async for token in stream_response(system_prompt, user_message):
            yield token
    except ValueError as e:
        # Config error (missing API key etc.) — surface it clearly
        logger.error("LLM config error: %s", e)
        yield f"The assistant is not configured correctly. "
        yield f"Please contact {settings.owner_name} at {settings.owner_contact_email}."
    except Exception as e:
        # Unexpected error mid-stream — already handled inside llm_client,
        # but catch anything that bubbles up just in case.
        logger.error("Unexpected LLM error: %s", e)
        yield "\n\nSomething went wrong. Please try again."

    logger.info("RAG pipeline complete.")
