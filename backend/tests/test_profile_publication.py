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
        }
        create_res = await client.put("/api/v1/profile/draft", json=first_draft, headers=headers)
        assert create_res.status_code == 200
        created_exp_id = create_res.json()["experiences"][0]["id"]
        assert created_exp_id.startswith("exp_")

        publish_blocked = await client.post("/api/v1/profile/publish", headers=headers)
        assert publish_blocked.status_code == 422
        issue_fields = {issue["field"] for issue in publish_blocked.json()["detail"]["issues"]}
        assert "experiences.0.end" in issue_fields
        assert "experiences.0.outcome" in issue_fields

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
        }
        second_save = await client.put("/api/v1/profile/draft", json=edited_and_added, headers=headers)
        assert second_save.status_code == 200
        reloaded_draft = await client.get("/api/v1/profile", headers=headers)
        assert reloaded_draft.status_code == 200
        draft_experiences = reloaded_draft.json()["experiences"]
        assert [exp["organization"] for exp in draft_experiences] == ["Beta Labs", "Acme Corp"]

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
        }
        remove_res = await client.put("/api/v1/profile/draft", json=removed_one, headers=headers)
        assert remove_res.status_code == 200
        assert [exp["id"] for exp in remove_res.json()["experiences"]] == [beta_id]

        published = await client.post("/api/v1/profile/publish", headers=headers)
        assert published.status_code == 200
        published_body = published.json()
        assert published_body["version"] == 1
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

        changed_draft_after_publish = {
            "owner_name": "Test Owner",
            "experiences": [
                {
                    **remove_res.json()["experiences"][0],
                    "role": "Changed Draft Role",
                    "outcome": "Changed draft outcome.",
                }
            ],
        }
        changed = await client.put("/api/v1/profile/draft", json=changed_draft_after_publish, headers=headers)
        assert changed.status_code == 200

        still_published = await client.get("/api/v1/profile/published-snapshot", headers=headers)
        assert still_published.status_code == 200
        assert still_published.json()["snapshot"] == snapshot

        reload_draft = await client.get("/api/v1/profile", headers=headers)
        reload_published = await client.get("/api/v1/profile/published-snapshot", headers=headers)
        assert reload_draft.json()["experiences"][0]["role"] == "Changed Draft Role"
        assert reload_draft.json()["published_version"] == 1
        assert reload_published.json()["snapshot"]["experiences"][0]["role"] == "Principal Platform Lead"
