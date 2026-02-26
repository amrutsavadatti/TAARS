"""
Rate limiter — enforces per-day question limits using Valkey counters.

Two modes depending on ENABLE_OTP_GATE in .env:

  OTP OFF (default, anonymous):
    Key:   ratelimit:ip:{ip}:{date}
    Limit: RATE_LIMIT_PER_IP_PER_DAY (default 50)
    On hit: returns RateLimitAction with email capture + Cal.com CTA

  OTP ON (identity-gated):
    Key:   ratelimit:email:{email}:{date}
    Limit: RATE_LIMIT_PER_EMAIL_PER_DAY (default 20)
    On hit: returns RateLimitAction with "come back tomorrow" message
            (visitor already identified, so no email capture needed)

Both keys use TTL that expires at the end of the current UTC day so
the counter resets automatically at midnight — no cron job needed.

Also tracks question count per session for the OTP identity gate trigger
(when OTP ON, fire the identity gate after N questions).

Public API:
    limiter = RateLimiter(valkey_client)

    result = await limiter.check(session_id, ip, email=None)
    if result.allowed:
        # proceed with chat
        await limiter.increment(session_id, ip, email=None)
    else:
        # yield result.sse_event to browser (widget renders CTA screen)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import redis.asyncio as aioredis

from backend.config import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result dataclass — returned by check()
# ---------------------------------------------------------------------------

@dataclass
class RateLimitResult:
    allowed: bool               # True = proceed with chat, False = blocked

    # Only populated when allowed=False
    event_type: str = ""        # "rate_limit" or "identity_gate"
    payload: dict = None        # data sent to widget as SSE event

    def __post_init__(self):
        if self.payload is None:
            self.payload = {}

    def sse_event(self) -> str:
        """
        Format as a named SSE event.

        Named SSE events look like:
            event: rate_limit
            data: {"message": "...", "cal_com_url": "..."}

        The widget's EventSource listener checks e.type to decide
        which screen to render (RateLimitScreen vs OTPGate).
        """
        return f"event: {self.event_type}\ndata: {json.dumps(self.payload)}\n\n"


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Stateless rate limiter — safe to instantiate once and reuse.
    All state lives in Valkey.
    """

    def __init__(self, client: aioredis.Redis):
        self._client = client

    # ------------------------------------------------------------------
    # Key helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ip_key(ip: str) -> str:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"ratelimit:ip:{ip}:{date}"

    @staticmethod
    def _email_key(email: str) -> str:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return f"ratelimit:email:{email.lower()}:{date}"

    @staticmethod
    def _session_count_key(session_id: str) -> str:
        """Tracks how many questions this session has asked (for OTP gate trigger)."""
        return f"qcount:{session_id}"

    @staticmethod
    def _seconds_until_midnight_utc() -> int:
        """TTL to set so the key expires exactly at midnight UTC."""
        now = datetime.now(timezone.utc)
        midnight = now.replace(hour=23, minute=59, second=59, microsecond=0)
        return max(1, int((midnight - now).total_seconds()))

    # ------------------------------------------------------------------
    # Check — call BEFORE processing the question
    # ------------------------------------------------------------------

    async def check(
        self,
        session_id: str,
        ip: str,
        email: str | None = None,
    ) -> RateLimitResult:
        """
        Check whether this request should be allowed.

        Returns RateLimitResult:
            .allowed = True   → proceed with chat
            .allowed = False  → block; yield .sse_event() to the browser

        Also checks whether the OTP identity gate should fire
        (when OTP is enabled and question count reaches the threshold).
        """
        try:
            # ── OTP ON: check identity gate trigger ───────────────────
            if settings.enable_otp_gate and not email:
                gate_result = await self._check_identity_gate(session_id)
                if gate_result:
                    return gate_result

            # ── Choose rate limit key based on mode ───────────────────
            if settings.enable_otp_gate and email:
                key = self._email_key(email)
                limit = settings.rate_limit_per_email_per_day
            else:
                key = self._ip_key(ip)
                limit = settings.rate_limit_per_ip_per_day

            count = await self._client.get(key)
            current = int(count) if count else 0

            if current >= limit:
                logger.info(
                    "Rate limit hit — key=%s  count=%d  limit=%d",
                    key, current, limit,
                )
                return self._rate_limit_response(email=email)

            return RateLimitResult(allowed=True)

        except Exception as e:
            # If Valkey is down, fail open — let the request through.
            # Losing rate limiting temporarily is better than blocking all users.
            logger.warning("Rate limiter check failed (Valkey error): %s", e)
            return RateLimitResult(allowed=True)

    # ------------------------------------------------------------------
    # Increment — call AFTER successfully streaming the answer
    # ------------------------------------------------------------------

    async def increment(
        self,
        session_id: str,
        ip: str,
        email: str | None = None,
    ) -> None:
        """
        Increment the rate limit counter and session question count.

        Call this after the answer has been fully streamed — so aborted
        or errored requests don't count against the visitor's limit.
        """
        try:
            ttl = self._seconds_until_midnight_utc()

            # Increment the rate limit counter
            if settings.enable_otp_gate and email:
                key = self._email_key(email)
            else:
                key = self._ip_key(ip)

            await self._client.incr(key)
            await self._client.expireat(
                key,
                int(datetime.now(timezone.utc).replace(
                    hour=23, minute=59, second=59
                ).timestamp())
            )

            # Increment session question count (for OTP gate trigger)
            qkey = self._session_count_key(session_id)
            await self._client.incr(qkey)
            # Session question count TTL matches session TTL
            await self._client.expire(qkey, settings.session_ttl_minutes * 60)

            logger.debug(
                "Incremented rate limit — key=%s  session=%s", key, session_id
            )

        except Exception as e:
            logger.warning("Rate limiter increment failed (Valkey error): %s", e)

    # ------------------------------------------------------------------
    # OTP identity gate check
    # ------------------------------------------------------------------

    async def _check_identity_gate(self, session_id: str) -> RateLimitResult | None:
        """
        Check if the OTP identity gate should fire for this session.

        Returns a RateLimitResult with event_type="identity_gate" if the
        visitor has hit the configured question threshold and hasn't
        identified themselves yet.

        Returns None if the gate should not fire (let the request through).
        """
        qkey = self._session_count_key(session_id)
        count = await self._client.get(qkey)
        questions_asked = int(count) if count else 0

        # Gate fires when visitor has asked exactly N-1 questions
        # (i.e. this is their Nth question and we haven't gated yet)
        threshold = settings.otp_gate_after_n_questions - 1

        if questions_asked >= threshold:
            logger.info(
                "Identity gate trigger — session=%s  questions_asked=%d  threshold=%d",
                session_id, questions_asked, threshold,
            )
            return RateLimitResult(
                allowed=False,
                event_type="identity_gate",
                payload={
                    "message": (
                        f"Before we continue — I'd love to connect you with "
                        f"{settings.owner_name} directly!"
                    ),
                    "fields": {
                        "name":    {"required": True,  "label": "Your name"},
                        "email":   {"required": True,  "label": "Your email"},
                        "company": {"required": False, "label": "Company (optional)"},
                    },
                    "submit_url": "/api/v1/visitor/identify",
                    "skip_allowed": False,
                },
            )

        return None

    # ------------------------------------------------------------------
    # Rate limit response builder
    # ------------------------------------------------------------------

    def _rate_limit_response(self, email: str | None) -> RateLimitResult:
        """
        Build the rate_limit SSE event payload.

        OTP OFF (anonymous): show email capture + Cal.com CTA
        OTP ON  (identified): visitor already gave email — just show
                              "come back tomorrow" + Cal.com CTA
        """
        owner = settings.owner_name
        cal_url = settings.cal_com_booking_url

        if settings.enable_otp_gate and email:
            # Visitor is already identified — no need to ask for email again
            payload = {
                "message": (
                    f"You've reached today's question limit! "
                    f"Come back tomorrow to continue chatting."
                ),
                "show_email_capture": False,
                "cal_com_url": cal_url or None,
                "owner_email": settings.owner_contact_email,
                "owner_name": owner,
            }
        else:
            # Anonymous visitor — capture email + show Cal.com
            payload = {
                "message": (
                    f"You've reached today's question limit!"
                ),
                "show_email_capture": True,
                "email_capture_label": f"Want {owner} to reach out? Share your email:",
                "email_submit_url": "/api/v1/visitor/lead",
                "cal_com_url": cal_url or None,
                "owner_name": owner,
            }

        return RateLimitResult(
            allowed=False,
            event_type="rate_limit",
            payload=payload,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_rate_limiter(client: aioredis.Redis) -> RateLimiter:
    """Create a RateLimiter from an existing aioredis client."""
    return RateLimiter(client)
