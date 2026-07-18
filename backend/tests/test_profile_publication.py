from __future__ import annotations

import importlib
import sys

import pytest
from httpx import ASGITransport, AsyncClient


def _fresh_backend_modules() -> None:
    for name in list(sys.modules):
        if name == "backend" or name.startswith("backend."):
            del sys.modules[name]


@pytest.mark.asyncio
async def test_profile_draft_publication_snapshot_and_reload_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}")
    monkeypatch.setenv("OWNER_NAME", "Test Owner")
    _fresh_backend_modules()

    database = importlib.import_module("backend.database")
    await database.create_tables()
    app = importlib.import_module("backend.main").app

    headers = {"X-API-Key": "dev-key"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        empty = await client.get("/api/v1/profile", headers=headers)
        assert empty.status_code == 200
        assert empty.json()["owner_name"] == "Test Owner"
        assert empty.json()["experiences"] == []
        assert empty.json()["projects"] == []
        assert empty.json()["skills"] == []
        assert empty.json()["education"] == []
        assert empty.json()["achievements"] == []
        assert empty.json()["personal_topics"] == []

        first_draft = {
            "owner_name": "Test Owner",
            "experiences": [
                {
                    "organization": "Acme",
                    "role": "Engineer",
                    "start_month": 1,
                    "start_year": 2022,
                    "end_month": 12,
                    "end_year": 2021,
                    "is_current": False,
                    "summary": "Built internal tools.",
                    "outcome": "",
                    "display_order": 0,
                }
            ],
            "projects": [
                {
                    "name": "Career assistant",
                    "summary": "Built the profile publication workflow for a career assistant.",
                    "problem": "Visitors needed better answers about the owner's background.",
                    "contribution": "Built the profile publication workflow.",
                    "outcome": "",
                    "technologies": ["FastAPI", "React", "PostgreSQL"],
                    "display_order": 0,
                }
            ],
        }
        create_res = await client.put("/api/v1/profile/draft", json=first_draft, headers=headers)
        assert create_res.status_code == 200
        created_exp_id = create_res.json()["experiences"][0]["id"]
        created_project_id = create_res.json()["projects"][0]["id"]
        assert created_exp_id.startswith("exp_")
        assert created_project_id.startswith("proj_")

        publish_blocked = await client.post("/api/v1/profile/publish", headers=headers)
        assert publish_blocked.status_code == 422
        issue_fields = {issue["field"] for issue in publish_blocked.json()["detail"]["issues"]}
        assert "experiences.0.end" in issue_fields
        assert "projects.0.start" not in issue_fields
        assert "projects.0.end" not in issue_fields

        edited_and_added = {
            "owner_name": "Test Owner",
            "experiences": [
                {
                    "id": created_exp_id,
                    "organization": "Acme Corp",
                    "role": "Senior Engineer",
                    "start_month": 1,
                    "start_year": 2022,
                    "end_month": 6,
                    "end_year": 2024,
                    "is_current": False,
                    "summary": "Built internal tools and automation.",
                    "outcome": "Reduced manual operations for the team.",
                    "display_order": 1,
                },
                {
                    "organization": "Beta Labs",
                    "role": "Platform Lead",
                    "start_month": 7,
                    "start_year": 2024,
                    "is_current": True,
                    "summary": "Leads platform development.",
                    "outcome": "Created a clearer delivery path for product teams.",
                    "display_order": 0,
                },
            ],
            "projects": [
                {
                    "id": created_project_id,
                    "name": "Career assistant",
                    "summary": "Built the canonical profile workflow, including editing, validation, and publication.",
                    "problem": "Visitors needed better answers about the owner's background.",
                    "contribution": "Built a canonical profile publication workflow.",
                    "outcome": "Created a stable profile snapshot for future indexing.",
                    "measurable_impact": "First retrieval contract established.",
                    "technologies": ["FastAPI", "React", "PostgreSQL"],
                    "collaborators": ["Product"],
                    "links": ["https://example.com/profile"],
                    "start_month": 2,
                    "start_year": 2024,
                    "end_month": 6,
                    "end_year": 2024,
                    "featured": True,
                    "visibility": "public",
                    "display_order": 0,
                }
            ],
            "skills": [
                {
                    "name": "Backend systems",
                    "category": "Engineering",
                    "aliases": ["APIs", "Databases"],
                    "context": "Builds durable API contracts.",
                    "evidence": "Published profile API.",
                    "display_order": 0,
                }
            ],
            "education": [
                {
                    "institution": "State University",
                    "credential": "BS",
                    "field": "Computer Science",
                    "start_month": 8,
                    "start_year": 2018,
                    "end_month": 5,
                    "end_year": 2022,
                    "summary": "Studied software systems.",
                    "outcome": "Built a foundation in product engineering.",
                    "display_order": 0,
                }
            ],
            "achievements": [
                {
                    "title": "Launch award",
                    "summary": "Recognized for shipping the first canonical profile flow.",
                    "outcome": "Improved confidence in the product direction.",
                    "month": 6,
                    "year": 2024,
                    "featured": True,
                    "display_order": 0,
                }
            ],
            "personal_topics": [
                {
                    "category": "Interests",
                    "detail": "Enjoys building useful AI products.",
                    "approved": True,
                    "display_order": 0,
                },
                {
                    "category": "Private",
                    "detail": "Do not publish this topic.",
                    "approved": False,
                    "display_order": 1,
                },
            ],
        }
        second_save = await client.put("/api/v1/profile/draft", json=edited_and_added, headers=headers)
        assert second_save.status_code == 200
        reloaded_draft = await client.get("/api/v1/profile", headers=headers)
        assert reloaded_draft.status_code == 200
        draft_experiences = reloaded_draft.json()["experiences"]
        assert [exp["organization"] for exp in draft_experiences] == ["Beta Labs", "Acme Corp"]
        assert reloaded_draft.json()["projects"][0]["id"] == created_project_id
        assert reloaded_draft.json()["skills"][0]["id"].startswith("skill_")
        assert reloaded_draft.json()["education"][0]["id"].startswith("edu_")
        assert reloaded_draft.json()["achievements"][0]["id"].startswith("ach_")
        assert reloaded_draft.json()["personal_topics"][0]["id"].startswith("topic_")

        beta_id = draft_experiences[0]["id"]
        removed_one = {
            "owner_name": "Test Owner",
            "experiences": [
                {
                    **draft_experiences[0],
                    "role": "Principal Platform Lead",
                    "display_order": 0,
                }
            ],
            "projects": reloaded_draft.json()["projects"],
            "skills": reloaded_draft.json()["skills"],
            "education": reloaded_draft.json()["education"],
            "achievements": reloaded_draft.json()["achievements"],
            "personal_topics": reloaded_draft.json()["personal_topics"],
        }
        remove_res = await client.put("/api/v1/profile/draft", json=removed_one, headers=headers)
        assert remove_res.status_code == 200
        assert [exp["id"] for exp in remove_res.json()["experiences"]] == [beta_id]

        published = await client.post("/api/v1/profile/publish", headers=headers)
        assert published.status_code == 200
        published_body = published.json()
        assert published_body["version"] == 1
        assert published_body["publication_status"] == "candidate"
        assert published_body["is_active"] is False
        snapshot = published_body["snapshot"]
        assert snapshot["schema_version"] == "profile.snapshot.v1"
        assert snapshot["owner_id"] == "test_owner"
        assert snapshot["experiences"] == [
            {
                "id": beta_id,
                "type": "experience",
                "organization": "Beta Labs",
                "role": "Principal Platform Lead",
                "start_month": 7,
                "start_year": 2024,
                "end_month": None,
                "end_year": None,
                "is_current": True,
                "summary": "Leads platform development.",
                "outcome": "Created a clearer delivery path for product teams.",
                "display_order": 0,
            }
        ]
        assert snapshot["projects"][0] == {
            "id": created_project_id,
            "type": "project",
            "name": "Career assistant",
            "summary": "Built the canonical profile workflow, including editing, validation, and publication.",
            "problem": "Visitors needed better answers about the owner's background.",
            "contribution": "Built a canonical profile publication workflow.",
            "outcome": "Created a stable profile snapshot for future indexing.",
            "measurable_impact": "First retrieval contract established.",
            "technologies": ["FastAPI", "React", "PostgreSQL"],
            "collaborators": ["Product"],
            "links": ["https://example.com/profile"],
            "start_month": 2,
            "start_year": 2024,
            "end_month": 6,
            "end_year": 2024,
            "is_current": False,
            "featured": True,
            "visibility": "public",
            "display_order": 0,
        }
        assert snapshot["skills"][0]["name"] == "Backend systems"
        assert snapshot["education"][0]["institution"] == "State University"
        assert snapshot["achievements"][0]["title"] == "Launch award"
        assert snapshot["personal_topics"] == [
            {
                "id": reloaded_draft.json()["personal_topics"][0]["id"],
                "type": "personal_topic",
                "category": "Interests",
                "detail": "Enjoys building useful AI products.",
                "approved": True,
                "display_order": 0,
            }
        ]

        duplicate_publish = await client.post("/api/v1/profile/publish", headers=headers)
        assert duplicate_publish.status_code == 200
        assert duplicate_publish.json()["version"] == 1

        not_active_yet = await client.get("/api/v1/profile/published-snapshot", headers=headers)
        assert not_active_yet.status_code == 404

        activated = await client.post("/api/v1/profile/index", headers=headers)
        assert activated.status_code == 200
        assert activated.json()["published_version"] == 1
        assert activated.json()["candidate_version"] is None

        changed_draft_after_publish = {
            "owner_name": "Test Owner",
            "experiences": [
                {
                    **remove_res.json()["experiences"][0],
                    "role": "Changed Draft Role",
                    "outcome": "Changed draft outcome.",
                }
            ],
            "projects": [
                {
                    **remove_res.json()["projects"][0],
                    "outcome": "Changed draft project outcome.",
                }
            ],
            "skills": remove_res.json()["skills"],
            "education": remove_res.json()["education"],
            "achievements": remove_res.json()["achievements"],
            "personal_topics": remove_res.json()["personal_topics"],
        }
        changed = await client.put("/api/v1/profile/draft", json=changed_draft_after_publish, headers=headers)
        assert changed.status_code == 200

        still_published = await client.get("/api/v1/profile/published-snapshot", headers=headers)
        assert still_published.status_code == 200
        assert still_published.json()["snapshot"] == snapshot

        reload_draft = await client.get("/api/v1/profile", headers=headers)
        reload_published = await client.get("/api/v1/profile/published-snapshot", headers=headers)
        assert reload_draft.json()["experiences"][0]["role"] == "Changed Draft Role"
        assert reload_draft.json()["projects"][0]["outcome"] == "Changed draft project outcome."
        assert reload_draft.json()["published_version"] == 1
        assert reload_published.json()["snapshot"]["experiences"][0]["role"] == "Principal Platform Lead"
        assert reload_published.json()["snapshot"]["projects"][0]["outcome"] == "Created a stable profile snapshot for future indexing."
