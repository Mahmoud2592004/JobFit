"""Unit tests for Jobs and Search Runs API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.jobs import (
    get_ai_job_filter_service,
    get_job_discovery_service,
    get_job_repository,
)
from app.main import create_app

TEST_USER_ID = str(uuid4())


def sample_job_record(jid: str | None = None) -> dict:
    return {
        "id": jid or str(uuid4()),
        "source_name": "remotive",
        "source_job_id": "1001",
        "canonical_url": "https://remotive.com/jobs/1001",
        "title": "Staff Backend Engineer",
        "employer": "TechCorp",
        "location": "Remote",
        "work_arrangement": "remote",
        "employment_type": "full_time",
        "seniority": "senior",
        "description": "Design and build microservices.",
        "salary_min": 150000,
        "salary_max": 180000,
        "salary_currency": "USD",
        "published_at": "2026-10-01T12:00:00Z",
        "retrieved_at": "2026-10-10T00:00:00Z",
        "is_expired": False,
        "attribution": "Powered by Remotive",
    }


@pytest.fixture
def test_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    mock_repo = MagicMock()
    sample_job = sample_job_record()
    mock_repo.get_job = AsyncMock(return_value=sample_job)
    mock_repo.list_jobs = AsyncMock(return_value=[sample_job])
    mock_repo.list_search_runs = AsyncMock(
        return_value=[
            {
                "id": str(uuid4()),
                "user_id": TEST_USER_ID,
                "profile_version_id": None,
                "preferences_snapshot": {"query": "Backend"},
                "status": "completed",
                "providers_used": ["remotive"],
                "jobs_found": 1,
                "matches_created": 0,
                "error_summary": None,
                "retry_count": 0,
                "started_at": "2026-10-10T00:00:00Z",
                "completed_at": "2026-10-10T00:01:00Z",
                "created_at": "2026-10-10T00:00:00Z",
            }
        ]
    )

    mock_discovery = MagicMock()
    mock_discovery.discover_jobs = AsyncMock(
        return_value={
            "search_run_id": str(uuid4()),
            "jobs_count": 1,
            "cached": False,
            "jobs": [sample_job],
        }
    )

    app.dependency_overrides[get_job_repository] = lambda: mock_repo
    app.dependency_overrides[get_job_discovery_service] = lambda: mock_discovery

    return app


@pytest.mark.asyncio
async def test_search_jobs_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/jobs/search",
            json={"query": "Backend Engineer", "remote_only": True},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["jobs_count"] == 1
    assert data["cached"] is False
    assert len(data["jobs"]) == 1
    assert data["jobs"][0]["title"] == "Staff Backend Engineer"


@pytest.mark.asyncio
async def test_search_jobs_with_linkedin_filters(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/jobs/search",
            json={
                "query": "Backend Engineer",
                "remote_only": True,
                "location": "United States",
                "date_posted": "pastWeek",
                "under_10_applicants": True,
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["jobs_count"] == 1


@pytest.mark.asyncio
async def test_search_jobs_validation_error(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        # query too short (min 2 chars)
        response = await client.post("/api/v1/jobs/search", json={"query": "a"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_jobs_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/jobs?query=Backend&remote_only=true")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["employer"] == "TechCorp"


@pytest.mark.asyncio
async def test_get_job_endpoint_success(test_app):
    jid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/jobs/{jid}")

    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Staff Backend Engineer"


@pytest.mark.asyncio
async def test_get_job_endpoint_not_found(test_app):
    mock_repo = MagicMock()
    mock_repo.get_job = AsyncMock(return_value=None)
    test_app.dependency_overrides[get_job_repository] = lambda: mock_repo

    jid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/jobs/{jid}")

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_list_search_runs_endpoint(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/search-runs")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["status"] == "completed"


@pytest.mark.asyncio
async def test_ai_filter_jobs_endpoint(test_app):
    mock_ai_service = MagicMock()
    mock_ai_service.filter_jobs_for_candidate = AsyncMock(
        return_value={
            "candidate_summary": {"years_experience": 5.0, "seniority_level": "senior"},
            "total_evaluated": 1,
            "valid_count": 1,
            "results": [
                {
                    "job": sample_job_record(),
                    "evaluation": {
                        "job_id": str(uuid4()),
                        "is_valid_match": True,
                        "fit_level": "Strong Fit",
                        "ai_score": 92,
                        "experience_fit_analysis": "5 years satisfies senior requirements.",
                        "preference_fit_analysis": "Remote aligns with preference.",
                        "recruiter_rationale": "High compatibility.",
                    },
                }
            ],
        }
    )
    test_app.dependency_overrides[get_ai_job_filter_service] = lambda: mock_ai_service

    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/v1/jobs/ai-filter",
            json={"query": "Backend", "min_fit": "valid_only", "limit": 10},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["total_evaluated"] == 1
    assert data["valid_count"] == 1
    assert data["results"][0]["evaluation"]["fit_level"] == "Strong Fit"
