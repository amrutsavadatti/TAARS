"""
Session store — persists conversation history in Valkey.

Each session is stored as a JSON list of {role, content} turns under
the key: session:{session_id}

TTL slides on every interaction — the session stays alive as long as
the visitor keeps chatting. If they go quiet for SESSION_TTL_MINUTES
(default 30), the key expires and the next message starts fresh.

We only store the last MAX_TURNS turns (2 * SESSION_CONTEXT_WINDOW)
so the key never grows unbounded. Older turns are dropped from the
front of the list.

Public API:
    store = await get_session_store()

    history = await store.get_history(session_id)
    # → [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]

    await store.append_turn(session_id, question="...", answer="...")
    # adds two entries (user + assistant), trims old turns, resets TTL

    await store.clear(session_id)
    # deletes the session key entirely
"""

from __future__ import annotations

import json
import logging

import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)


class SessionStore:
    """
    Async session store backed by Valkey (Redis-compatible).

    One instance is created at app startup and reused across all requests.
    Thread-safe — aioredis handles concurrent access correctly.
    """

    def __init__(self, client: aioredis.Redis):
        self._client = client
        # Max number of individual messages to keep (user + assistant pairs)
        # SESSION_CONTEXT_WINDOW=5 → keep 5 pairs = 10 messages
        self._max_messages = settings.session_context_window * 2
        self._ttl_seconds = settings.session_ttl_minutes * 60

    # ------------------------------------------------------------------
    # Key helper
    # ------------------------------------------------------------------

    @staticmethod
    def _key(session_id: str) -> str:
        return f"session:{session_id}"

    # ------------------------------------------------------------------
    # Get history
    # ------------------------------------------------------------------

    async def get_history(self, session_id: str) -> list[dict]:
        """
        Load conversation history for a session.

        Returns a list of {"role": "user"|"assistant", "content": "..."}
        dicts ordered oldest → newest.

        Returns [] if the session doesn't exist or has expired.
        """
        try:
            raw = await self._client.get(self._key(session_id))
            if not raw:
                return []
            history = json.loads(raw)
            logger.debug("Loaded %d messages for session=%s", len(history), session_id)
            return history
        except Exception as e:
            # If Valkey is down, degrade gracefully — return empty history
            # so the chat still works, just without conversation memory.
            logger.warning("Failed to load session %s: %s", session_id, e)
            return []

    # ------------------------------------------------------------------
    # Append a completed turn
    # ------------------------------------------------------------------

    async def append_turn(
        self,
        session_id: str,
        question: str,
        answer: str,
    ) -> None:
        """
        Save a completed question/answer turn to the session.

        Appends two messages: user turn + assistant turn.
        Trims the list to MAX_MESSAGES (dropping oldest) to keep it bounded.
        Resets the TTL so the session stays alive after every interaction.

        Call this AFTER the full answer has been streamed to the browser,
        not before — so we store the complete answer, not a partial one.

        Args:
            session_id: The session identifier.
            question:   The visitor's question (user turn).
            answer:     The complete assistant response (assembled from tokens).
        """
        try:
            key = self._key(session_id)

            # Load existing history (or start fresh)
            raw = await self._client.get(key)
            history: list[dict] = json.loads(raw) if raw else []

            # Append the new turn
            history.append({"role": "user",      "content": question})
            history.append({"role": "assistant", "content": answer})

            # Trim to keep only the most recent MAX_MESSAGES messages
            # We drop from the front (oldest) when over the limit
            if len(history) > self._max_messages:
                history = history[-self._max_messages:]
                logger.debug(
                    "Trimmed session %s to %d messages", session_id, self._max_messages
                )

            # Save back with refreshed TTL
            await self._client.setex(
                key,
                self._ttl_seconds,
                json.dumps(history),
            )

            logger.debug(
                "Saved turn to session=%s  total_messages=%d  ttl=%ds",
                session_id, len(history), self._ttl_seconds,
            )

        except Exception as e:
            # If Valkey is down, log and continue — losing session history
            # is acceptable, losing the chat response is not.
            logger.warning("Failed to save session %s: %s", session_id, e)

    # ------------------------------------------------------------------
    # Clear session
    # ------------------------------------------------------------------

    async def clear(self, session_id: str) -> None:
        """
        Delete a session entirely.

        Useful when a visitor explicitly starts a new conversation,
        or when the rate limit is hit and we want a clean slate.
        """
        try:
            await self._client.delete(self._key(session_id))
            logger.info("Cleared session=%s", session_id)
        except Exception as e:
            logger.warning("Failed to clear session %s: %s", session_id, e)

    # ------------------------------------------------------------------
    # Inspect (useful for testing and admin)
    # ------------------------------------------------------------------

    async def get_turn_count(self, session_id: str) -> int:
        """Return the number of messages stored for a session. 0 if not found."""
        history = await self.get_history(session_id)
        # Each "turn" = one user + one assistant message
        return len(history) // 2

    async def get_ttl(self, session_id: str) -> int:
        """Return seconds remaining on the session TTL. -2 if key doesn't exist."""
        try:
            return await self._client.ttl(self._key(session_id))
        except Exception:
            return -2


# ---------------------------------------------------------------------------
# Factory — creates a SessionStore from an aioredis client
# ---------------------------------------------------------------------------

async def get_session_store() -> SessionStore:
    """
    Create a SessionStore connected to Valkey.

    In the FastAPI app, call this once at startup and store the instance
    on app.state.session_store.  Each request then accesses it via:
        store = request.app.state.session_store
    """
    client = aioredis.from_url(
        settings.valkey_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return SessionStore(client)
