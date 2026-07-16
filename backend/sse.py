"""Server-Sent Event formatting shared by streaming endpoints."""

from __future__ import annotations

import json
from typing import Any


def sse_data(data: str) -> str:
    return f"data: {json.dumps(data)}\n\n"


def sse_event(event_type: str, payload: Any) -> str:
    data = payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


def sse_done() -> str:
    return "data: [DONE]\n\n"
