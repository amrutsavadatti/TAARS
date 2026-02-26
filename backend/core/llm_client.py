"""
LLM client — streams tokens from OpenAI or Anthropic.

Controlled by LLM_PROVIDER in .env:
    openai     → OpenAI chat completions (gpt-4o-mini default)
    anthropic  → Anthropic messages (claude-sonnet-4-6 default)

Public API:
    async for token in stream_response(system_prompt, user_message):
        yield token   # each token is a small string, e.g. "Amrut", " has", " worked"

The function is an async generator — it yields one token at a time
as the LLM produces them. The chat endpoint iterates over this and
sends each token to the browser via SSE immediately, giving the
real-time typing effect.

Error handling:
    - If the API key is missing or invalid → raises a clear ValueError
    - If the API call fails mid-stream → logs the error and yields a
      user-friendly error message so the stream closes gracefully
      instead of leaving the browser hanging.
"""

from __future__ import annotations

import logging
from typing import AsyncGenerator

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# OpenAI streaming
# ---------------------------------------------------------------------------

async def _stream_openai(
    system_prompt: str,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from OpenAI chat completions API.

    The OpenAI SDK returns a stream of ChatCompletionChunk objects.
    Each chunk has choices[0].delta.content which is the next token
    (or None for the final chunk).
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.llm_api_key)

    logger.info("Streaming from OpenAI model: %s", settings.llm_model)

    stream = await client.chat.completions.create(
        model=settings.llm_model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_message},
        ],
        stream=True,
        # Low temperature for factual, deterministic answers grounded in the corpus.
        temperature=0.1,
        max_tokens=450,
    )

    async for chunk in stream:
        token = chunk.choices[0].delta.content
        if token is not None:
            yield token


# ---------------------------------------------------------------------------
# Anthropic streaming
# ---------------------------------------------------------------------------

async def _stream_anthropic(
    system_prompt: str,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream tokens from Anthropic messages API.

    Anthropic's streaming API emits different event types. We only
    care about 'content_block_delta' events where delta.type == 'text_delta'
    — those carry the actual token text.
    """
    import anthropic

    client = anthropic.AsyncAnthropic(api_key=settings.llm_api_key)

    logger.info("Streaming from Anthropic model: %s", settings.llm_model)

    async with client.messages.stream(
        model=settings.llm_model,
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_message},
        ],
        temperature=0.1,
        max_tokens=450,
    ) as stream:
        async for text in stream.text_stream:
            yield text


# ---------------------------------------------------------------------------
# Public interface — provider-agnostic
# ---------------------------------------------------------------------------

async def stream_response(
    system_prompt: str,
    user_message: str,
) -> AsyncGenerator[str, None]:
    """
    Stream LLM response tokens one at a time.

    Selects the provider from LLM_PROVIDER in .env.
    Wraps provider-specific errors so the caller always gets a clean
    async generator regardless of which backend is in use.

    Usage:
        async for token in stream_response(system_prompt, user_message):
            # send token to browser via SSE
            yield f"data: {token}\n\n"

    Args:
        system_prompt: The assembled system prompt from prompt_builder.
        user_message:  The visitor's question.

    Yields:
        str — one token at a time (e.g. "Amrut", " worked", " at", ...)
    """
    if not settings.llm_api_key or settings.llm_api_key.startswith("sk-..."):
        raise ValueError(
            "LLM_API_KEY is not set in .env. Add your OpenAI or Anthropic key."
        )

    provider = settings.llm_provider.lower()

    try:
        if provider == "openai":
            async for token in _stream_openai(system_prompt, user_message):
                yield token

        elif provider == "anthropic":
            async for token in _stream_anthropic(system_prompt, user_message):
                yield token

        else:
            raise ValueError(
                f"Unknown LLM_PROVIDER '{provider}'. Use 'openai' or 'anthropic'."
            )

    except ValueError:
        raise   # re-raise config errors so the endpoint returns a 500

    except Exception as e:
        # Mid-stream API error — log it and yield a graceful message
        # so the browser gets a complete (if sad) response instead of
        # a broken stream.
        logger.error("LLM streaming error (%s): %s", provider, e)
        yield "\n\n[Sorry, I encountered an error generating a response. "
        yield f"Please try again or contact {settings.owner_name} directly "
        yield f"at {settings.owner_contact_email}.]"
