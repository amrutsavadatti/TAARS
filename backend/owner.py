"""Owner identity helpers shared by owner-scoped APIs and services."""

from __future__ import annotations

import re

from backend.config import settings


def owner_id_from_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return normalized or "owner"


def configured_owner_id() -> str:
    return owner_id_from_name(settings.owner_name)
