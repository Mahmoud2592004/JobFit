"""Tests for profile and preferences API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.profile import get_preferences_repo, get_profile_repo
from app.main import create_app

TEST_USER_ID = str(uuid4())


@pytest.fixture
def test_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    mock_profile_repo = MagicMock()
    mock_profile_repo.get_profile = AsyncMock(
        return_value={"id": str(uuid4()), "user_id": TEST_USER_ID, "display_name": "Alice"}
    )
    mock_profile_repo.get_active_profile_version = AsyncMock(
        return_value={"id": str(uuid4()), "version_number": 1, "is_confirmed": True}
    )
    mock_profile_repo.upsert_profile = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "user_id": TEST_USER_ID,
            "display_name": "Alice Updated",
            "created_at": "2026-10-10T00:00:00Z",
            "updated_at": "2026-10-10T00:00:00Z",
        }
    )
    mock_profile_repo.confirm_profile_version = AsyncMock(
        return_value={"id": str(uuid4()), "is_confirmed": True}
    )
    mock_profile_repo.update_active_years_experience = AsyncMock(
        return_value={"id": str(uuid4()), "years_experience": 5.0}
    )
    mock_profile_repo.get_profile_evidence = AsyncMock(return_value=[])

    # Table mock for list/get versions
    mock_table = MagicMock()
    mock_profile_repo.client.table.return_value = mock_table
    mock_select = MagicMock()
    mock_table.select.return_value = mock_select
    mock_eq1 = MagicMock()
    mock_select.eq.return_value = mock_eq1
    mock_eq2 = MagicMock()
    mock_eq1.eq.return_value = mock_eq2
    mock_single = MagicMock()
    mock_eq2.maybe_single.return_value = mock_single

    # Single version mock
    mock_single.execute.return_value = MagicMock(
        data={
            "id": str(uuid4()),
            "version_number": 1,
            "is_confirmed": True,
            "content": {},
            "skills": ["Python"],
            "target_roles": ["Engineer"],
            "created_at": "2026-10-10T00:00:00Z",
        }
    )

    mock_profile_repo.cast_single.side_effect = lambda data: (
        data if isinstance(data, dict) else None
    )
    mock_profile_repo.cast_records.side_effect = lambda data: data if isinstance(data, list) else []

    # Preferences repo mock
    mock_prefs_repo = MagicMock()
    mock_prefs_repo.get_preferences = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "user_id": TEST_USER_ID,
            "target_roles": ["Software Engineer"],
            "updated_at": "2026-10-10T00:00:00Z",
        }
    )
    mock_prefs_repo.upsert_preferences = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "user_id": TEST_USER_ID,
            "target_roles": ["ML Engineer"],
            "updated_at": "2026-10-10T00:00:00Z",
        }
    )

    app.dependency_overrides[get_profile_repo] = lambda: mock_profile_repo
    app.dependency_overrides[get_preferences_repo] = lambda: mock_prefs_repo

    return app


@pytest.mark.asyncio
async def test_get_user_profile(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/profile")

    assert response.status_code == 200
    data = response.json()
    assert "profile" in data
    assert data["profile"]["display_name"] == "Alice"
    assert "active_version" in data


@pytest.mark.asyncio
async def test_update_user_profile(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.patch("/api/v1/profile", json={"display_name": "Alice Updated"})

    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Alice Updated"


@pytest.mark.asyncio
async def test_update_user_profile_years_experience(test_app):
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.patch(
            "/api/v1/profile",
            json={"display_name": "Alice Updated", "years_experience": 5.0},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["years_experience"] == 5.0


@pytest.mark.asyncio
async def test_get_profile_version_detail(test_app):
    vid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/profile/versions/{vid}")

    assert response.status_code == 200
    data = response.json()
    assert data["skills"] == ["Python"]
    assert "evidence" in data


@pytest.mark.asyncio
async def test_confirm_profile_version(test_app):
    vid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/profile/versions/{vid}/confirm")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "confirmed"


@pytest.mark.asyncio
async def test_get_search_preferences(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/profile/preferences")

    assert response.status_code == 200
    data = response.json()
    assert data["target_roles"] == ["Software Engineer"]


@pytest.mark.asyncio
async def test_update_search_preferences(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.put(
            "/api/v1/profile/preferences", json={"target_roles": ["ML Engineer"]}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["target_roles"] == ["ML Engineer"]
