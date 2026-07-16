from __future__ import annotations

import importlib
import json
import sys

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload


def _fresh_backend_modules() -> None:
    for name in list(sys.modules):
        if name == "backend" or name.startswith("backend."):
            del sys.modules[name]


class _SessionStore:
    def __init__(self) -> None:
        self.saved_turns: list[tuple[str, str, str]] = []

    async def get_history(self, _session_id: str) -> list[dict]:
        return []

    async def append_turn(self, session_id: str, question: str, answer: str) -> None:
        self.saved_turns.append((session_id, question, answer))


class _RateLimiter:
    async def check(self, _session_id: str, *, ip: str, email: str | None = None):
        rate_limiter = importlib.import_module("backend.middleware.rate_limiter")
        return rate_limiter.RateLimitResult(allowed=True)

    async def increment(self, _session_id: str, *, ip: str, email: str | None = None) -> None:
        return None


async def _fake_llm_stream(_system_prompt: str, _user_message: str):
    assert "representing Published Owner" in _system_prompt
    yield "Published Owner leads backend platform work at Beta Labs."


def _event_payload(stream: str, event_name: str) -> dict:
    marker = f"event: {event_name}\n"
    event_block = next(block for block in stream.split("\n\n") if block.startswith(marker))
    data_line = next(line for line in event_block.splitlines() if line.startswith("data: "))
    return json.loads(data_line.removeprefix("data: "))


@pytest.mark.asyncio
async def test_widget_chat_uses_published_profile_and_emits_evidence_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}")
    monkeypatch.setenv("OWNER_NAME", "Test Owner")
    _fresh_backend_modules()

    database = importlib.import_module("backend.database")
    await database.create_tables()
    app = importlib.import_module("backend.main").app
    app.state.session_store = _SessionStore()
    app.state.rate_limiter = _RateLimiter()
    app.state.answer_streamer = _fake_llm_stream

    headers = {"X-API-Key": "dev-key"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        draft = {
            "owner_name": "Published Owner",
            "experiences": [
                {
                    "organization": "Beta Labs",
                    "role": "Principal Platform Lead",
                    "start_month": 7,
                    "start_year": 2024,
                    "is_current": True,
                    "summary": "Leads backend platform development using FastAPI and PostgreSQL.",
                    "outcome": "Created reliable backend APIs for product teams.",
                }
            ],
        }
        assert (await client.put("/api/v1/profile/draft", json=draft, headers=headers)).status_code == 200
        assert (await client.post("/api/v1/profile/publish", headers=headers)).status_code == 200
        assert (await client.post("/api/v1/profile/index", headers=headers)).status_code == 200

        response = await client.get(
            "/api/v1/chat/stream",
            params={
                "q": "What backend work does Test Owner do?",
                "session_id": "session-1",
                "api_key": "dev-key",
            },
        )

    assert response.status_code == 200
    metadata = _event_payload(response.text, "answer_metadata")
    assert metadata["status"] == "SUPPORTED"
    assert metadata["snapshot_version"] == 1
    assert metadata["knowledge_backend"] == "postgres_pgvector"
    assert metadata["evidence"][0]["source_type"] == "experience"
    assert metadata["evidence"][0]["title"] == "Principal Platform Lead at Beta Labs"
    assert 'data: "Published Owner leads backend platform work at Beta Labs."' in response.text
    assert response.text.rstrip().endswith("data: [DONE]")
    assert app.state.session_store.saved_turns == [
        (
            "session-1",
            "What backend work does Test Owner do?",
            "Published Owner leads backend platform work at Beta Labs.",
        )
    ]

    models = importlib.import_module("backend.models")
    async with database.get_db() as db:
        result = await db.execute(
            select(models.Message)
            .where(models.Message.role == "assistant")
            .options(selectinload(models.Message.evidence))
        )
        stored_answer = result.scalar_one()
    assert stored_answer.answer_status == "SUPPORTED"
    assert stored_answer.profile_snapshot_version == 1
    assert stored_answer.knowledge_backend == "postgres_pgvector"
    assert stored_answer.evidence[0].source_type == "experience"
    assert stored_answer.evidence[0].title == "Principal Platform Lead at Beta Labs"
