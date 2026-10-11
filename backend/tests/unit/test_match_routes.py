"""Unit tests for Matches API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.matches import get_match_repository, get_matching_service
from app.main import create_app

TEST_USER_ID = str(uuid4())


def sample_match_record(mid: str | None = None, jid: str | None = None) -> dict:
    return {
        "id": mid or str(uuid4()),
        "user_id": TEST_USER_ID,
        "job_id": jid or str(uuid4()),
        "search_run_id": None,
        "profile_version_id": None,
        "overall_score": 87.5,
        "scoring_version": "v1.0.0",
        "score_breakdown": {
            "skills_score": 90.0,
            "experience_score": 85.0,
            "role_score": 90.0,
            "work_arrangement_score": 80.0,
        },
        "matching_evidence": ["Strong skill match: Python, Docker"],
        "missing_requirements": ["Kubernetes"],
        "uncertain_factors": [],
        "freshness_warning": None,
        "evaluated_at": "2026-10-10T00:00:00Z",
        "is_saved": False,
        "saved_at": None,
        "job": None,
    }


@pytest.fixture
def test_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    mock_repo = MagicMock()
    mock_service = MagicMock()

    record = sample_match_record()
    mock_repo.get_match = AsyncMock(return_value=record)
    mock_repo.list_matches = AsyncMock(return_value=[record])

    async def fake_saved(user_id, match_id, is_saved):
        return {**record, "id": str(match_id), "is_saved": is_saved}

    mock_repo.set_saved_status = AsyncMock(side_effect=fake_saved)

    mock_service.batch_match_jobs = AsyncMock(return_value=[record])
    mock_service.match_job_for_user = AsyncMock(return_value=record)

    app.dependency_overrides[get_match_repository] = lambda: mock_repo
    app.dependency_overrides[get_matching_service] = lambda: mock_service

    return app


@pytest.mark.asyncio
async def test_evaluate_batch_matches_endpoint(test_app):
    jid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/matches/batch",
            json={"job_ids": [str(jid)]},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["evaluated_count"] == 1
    assert len(data["matches"]) == 1
    assert data["matches"][0]["overall_score"] == 87.5


@pytest.mark.asyncio
async def test_evaluate_single_match_endpoint(test_app):
    jid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/matches/evaluate/{jid}")

    assert response.status_code == 200
    data = response.json()
    assert data["overall_score"] == 87.5


@pytest.mark.asyncio
async def test_list_matches_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/matches?min_score=80.0&is_saved=false")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["overall_score"] == 87.5


@pytest.mark.asyncio
async def test_get_match_endpoint_success(test_app):
    mid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/matches/{mid}")

    assert response.status_code == 200
    data = response.json()
    assert data["scoring_version"] == "v1.0.0"


@pytest.mark.asyncio
async def test_get_match_endpoint_not_found(test_app):
    mock_repo = MagicMock()
    mock_repo.get_match = AsyncMock(return_value=None)
    test_app.dependency_overrides[get_match_repository] = lambda: mock_repo

    mid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/matches/{mid}")

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_save_and_unsave_match_endpoint(test_app):
    mid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # Save bookmark
        save_resp = await client.post(f"/api/v1/matches/{mid}/save")
        assert save_resp.status_code == 200
        assert save_resp.json()["is_saved"] is True

        # Unsave bookmark
        unsave_resp = await client.delete(f"/api/v1/matches/{mid}/save")
        assert unsave_resp.status_code == 200
        assert unsave_resp.json()["is_saved"] is False
