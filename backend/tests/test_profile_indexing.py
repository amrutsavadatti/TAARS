from __future__ import annotations

import importlib
import sys

import pytest
from httpx import ASGITransport, AsyncClient


def _fresh_backend_modules() -> None:
    for name in list(sys.modules):
        if name == "backend" or name.startswith("backend."):
            del sys.modules[name]


async def _save_and_publish_profile(client: AsyncClient, headers: dict[str, str], *, project_outcome: str):
    draft = {
        "owner_name": "Test Owner",
        "experiences": [
            {
                "organization": "Beta Labs",
                "role": "Principal Platform Lead",
                "start_month": 7,
                "start_year": 2024,
                "is_current": True,
                "summary": "Leads backend platform development using FastAPI and PostgreSQL.",
                "outcome": "Created reliable backend APIs for product teams.",
                "display_order": 0,
            }
        ],
        "projects": [
            {
                "name": "Career assistant",
                "problem": "Visitors needed evidence-backed answers about backend systems work.",
                "contribution": "Built a canonical profile workflow and retrieval contract.",
                "outcome": project_outcome,
                "technologies": ["FastAPI", "PostgreSQL", "pgvector"],
                "start_month": 2,
                "start_year": 2024,
                "end_month": 6,
                "end_year": 2024,
                "display_order": 0,
            },
            {
                "name": "Private launch plan",
                "problem": "Internal launch sequencing needed documentation.",
                "contribution": "Prepared confidential rollout notes.",
                "outcome": "Kept private launch details out of public answers.",
                "technologies": ["InternalOnlyTool"],
                "start_month": 1,
                "start_year": 2025,
                "end_month": 2,
                "end_year": 2025,
                "visibility": "private",
                "display_order": 1,
            },
        ],
        "skills": [
            {
                "name": "Backend systems",
                "category": "Engineering",
                "aliases": ["APIs", "PostgreSQL"],
                "context": "Builds durable APIs and data-backed product systems.",
                "evidence": "Published profile API and pgvector indexing flow.",
                "display_order": 0,
            }
        ],
        "personal_topics": [
            {
                "category": "Interests",
                "detail": "Enjoys building mechanical keyboards.",
                "approved": True,
                "display_order": 0,
            },
            {
                "category": "Private",
                "detail": "This personal detail must never be indexed.",
                "approved": False,
                "display_order": 1,
            },
        ],
    }
    save = await client.put("/api/v1/profile/draft", json=draft, headers=headers)
    assert save.status_code == 200
    published = await client.post("/api/v1/profile/publish", headers=headers)
    assert published.status_code == 200
    return save.json(), published.json()


@pytest.mark.asyncio
async def test_published_profile_can_be_indexed_and_queried_with_evidence(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}")
    monkeypatch.setenv("OWNER_NAME", "Test Owner")
    _fresh_backend_modules()

    database = importlib.import_module("backend.database")
    await database.create_tables()
    app = importlib.import_module("backend.main").app

    headers = {"X-API-Key": "dev-key"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        saved, published_v1 = await _save_and_publish_profile(
            client,
            headers,
            project_outcome="Created a stable profile snapshot for future pgvector indexing.",
        )
        project_id = saved["projects"][0]["id"]

        status_before = await client.get("/api/v1/profile/index-status", headers=headers)
        assert status_before.status_code == 200
        assert status_before.json()["published_version"] == 1
        assert status_before.json()["indexed_version"] is None

        indexed = await client.post("/api/v1/profile/index", headers=headers)
        assert indexed.status_code == 200
        indexed_body = indexed.json()
        assert indexed_body["published_version"] == 1
        assert indexed_body["indexed_version"] == 1
        assert indexed_body["indexed_backend_version"] == "profile-hash-384-v2"
        assert indexed_body["chunk_count"] >= 3
        assert {chunk["source_id"] for chunk in indexed_body["chunks"]} >= {
            published_v1["snapshot"]["experiences"][0]["id"],
            project_id,
        }
        assert "Private launch plan" not in {chunk["title"] for chunk in indexed_body["chunks"]}
        assert "Interests" in {chunk["title"] for chunk in indexed_body["chunks"]}

        answer = await client.post(
            "/api/v1/ask",
            json={"question": "What backend experience does Test Owner have?"},
            headers=headers,
        )
        assert answer.status_code == 200
        answer_body = answer.json()
        assert answer_body["snapshot_version"] == 1
        assert answer_body["status"] == "SUPPORTED"
        assert answer_body["knowledge_backend"] == "postgres_pgvector"
        assert "backend" in answer_body["answer"].lower()
        assert answer_body["evidence"]
        assert answer_body["evidence"][0]["source_id"] in {
            published_v1["snapshot"]["experiences"][0]["id"],
            project_id,
            saved["skills"][0]["id"],
        }
        assert answer_body["evidence"][0]["quote"]

        skills_answer = await client.post(
            "/api/v1/ask",
            json={"question": "What skills does Test Owner have?"},
            headers=headers,
        )
        assert skills_answer.status_code == 200
        assert skills_answer.json()["status"] == "SUPPORTED"
        assert skills_answer.json()["evidence"][0]["source_type"] == "skill"

        unsupported = await client.post(
            "/api/v1/ask",
            json={"question": "Can you write a pancake recipe for twelve people?"},
            headers=headers,
        )
        assert unsupported.status_code == 200
        assert unsupported.json()["status"] == "UNANSWERABLE"
        assert unsupported.json()["evidence"] == []
        assert "don't have enough information" in unsupported.json()["answer"].lower()

        await client.put(
            "/api/v1/profile/draft",
            json={
                **saved,
                "projects": [
                    {
                        **saved["projects"][0],
                        "outcome": "Changed draft-only outcome that should not be indexed yet.",
                    }
                ],
            },
            headers=headers,
        )
        draft_only_answer = await client.post(
            "/api/v1/ask",
            json={"question": "What did the career assistant project accomplish?"},
            headers=headers,
        )
        assert draft_only_answer.status_code == 200
        assert "Changed draft-only outcome" not in draft_only_answer.json()["answer"]
        assert draft_only_answer.json()["snapshot_version"] == 1

        await client.post("/api/v1/profile/publish", headers=headers)
        stale_status = await client.get("/api/v1/profile/index-status", headers=headers)
        assert stale_status.json()["published_version"] == 2
        assert stale_status.json()["indexed_version"] == 1

        reindexed = await client.post("/api/v1/profile/index", headers=headers)
        assert reindexed.status_code == 200
        assert reindexed.json()["indexed_version"] == 2
