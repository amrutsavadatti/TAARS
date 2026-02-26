"""
Visitor lead capture endpoint.

POST /api/v1/visitor/lead
Body: { "email": "visitor@example.com", "session_id": "..." }

Called by the widget when a visitor submits their email on the rate-limit
screen. Stores the email in Valkey and logs it clearly so the owner can
see who's interested.

Storage:
  Valkey set  leads:{owner_id}   → all captured emails (deduped)
  Valkey hash leads:meta:{email} → { session_id, captured_at }

Later (Phase 3) this feeds the follow-up email agent.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr

from backend.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["leads"])


class LeadRequest(BaseModel):
    email: EmailStr
    session_id: str | None = None


@router.post("/visitor/lead", status_code=200)
async def capture_lead(body: LeadRequest, request: Request, x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """
    Store a visitor's email for follow-up.

    Called from the rate-limit screen in the widget when the visitor
    opts in by leaving their email.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header.")

    email = str(body.email).lower().strip()
    owner_id = settings.owner_name.lower().replace(" ", "_")
    now = datetime.now(timezone.utc).isoformat()

    try:
        valkey = request.app.state.valkey

        # Store in a set (automatically deduped)
        leads_key = f"leads:{owner_id}"
        await valkey.sadd(leads_key, email)

        # Store metadata (first capture wins — don't overwrite existing)
        meta_key = f"leads:meta:{email}"
        await valkey.hsetnx(meta_key, "session_id", body.session_id or "")
        await valkey.hsetnx(meta_key, "captured_at", now)
        await valkey.hsetnx(meta_key, "owner_id", owner_id)

        total = await valkey.scard(leads_key)

        logger.info(
            "🎯 Lead captured — email=%s  session=%s  total_leads=%d",
            email, body.session_id, total,
        )

    except Exception as e:
        # Fail gracefully — don't break the widget if Valkey is down
        logger.warning("Failed to store lead in Valkey: %s", e)

    return {"status": "ok", "message": "Thanks! We'll be in touch."}
