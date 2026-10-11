"""Unit tests for JobDiscoveryService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.schemas.job import CanonicalJob
from app.services.job_discovery_service import JobDiscoveryService, _dedup_key


def make_job(
    employer: str,
    title: str,
    source: str = "remotive",
    job_id: str = "1",
) -> CanonicalJob:
    return CanonicalJob(
        source_name=source,
        source_job_id=job_id,
        canonical_url=f"https://example.com/{job_id}",
        title=title,
        employer=employer,
        location="Remote",
        work_arrangement="remote",
        employment_type="full_time",
        seniority="mid",
        description="Write Python.",
        attribution="Job feed",
    )


def test_dedup_key():
    job1 = make_job("Google Inc.", "Senior Software Engineer")
    job2 = make_job("google-inc", "senior software engineer")
    assert _dedup_key(job1) == _dedup_key(job2)


@pytest.mark.asyncio
async def test_discover_jobs_deduplication():
    # Two providers returning overlapping jobs
    job_a1 = make_job("Stripe", "Backend Engineer", source="remotive", job_id="101")
    job_a2 = make_job("Stripe", "Backend Engineer", source="arbeitnow", job_id="slug-stripe")
    job_b = make_job("Shopify", "Data Engineer", source="remotive", job_id="102")

    mock_provider_1 = MagicMock()
    mock_provider_1.name = "remotive"
    mock_provider_1.fetch_jobs = AsyncMock(return_value=[job_a1, job_b])

    mock_provider_2 = MagicMock()
    mock_provider_2.name = "arbeitnow"
    mock_provider_2.fetch_jobs = AsyncMock(return_value=[job_a2])

    mock_repo = MagicMock()
    run_id = str(uuid4())
    mock_repo.create_search_run = AsyncMock(return_value={"id": run_id})
    mock_repo.update_search_run = AsyncMock(return_value={})

    # Upsert receives deduplicated list (length 2 instead of 3)
    async def fake_upsert(jobs):
        return [{"id": str(uuid4()), "title": j.title, "employer": j.employer} for j in jobs]

    mock_repo.upsert_jobs = AsyncMock(side_effect=fake_upsert)

    service = JobDiscoveryService(
        job_repo=mock_repo,
        providers=[mock_provider_1, mock_provider_2],
    )

    result = await service.discover_jobs(
        user_id=uuid4(),
        query="Engineer",
        remote_only=True,
    )

    assert result["search_run_id"] == run_id
    assert result["jobs_count"] == 2
    assert result["cached"] is False
    mock_repo.upsert_jobs.assert_called_once()
    saved_arg = mock_repo.upsert_jobs.call_args[0][0]
    assert len(saved_arg) == 2


@pytest.mark.asyncio
async def test_discover_jobs_partial_provider_failure():
    job_a = make_job("Apple", "iOS Engineer", source="remotive", job_id="201")

    mock_provider_1 = MagicMock()
    mock_provider_1.name = "remotive"
    mock_provider_1.fetch_jobs = AsyncMock(return_value=[job_a])

    # Provider 2 throws exception
    mock_provider_2 = MagicMock()
    mock_provider_2.name = "arbeitnow"
    mock_provider_2.fetch_jobs = AsyncMock(side_effect=RuntimeError("Provider API down"))

    mock_repo = MagicMock()
    run_id = str(uuid4())
    mock_repo.create_search_run = AsyncMock(return_value={"id": run_id})
    mock_repo.update_search_run = AsyncMock(return_value={})
    mock_repo.upsert_jobs = AsyncMock(return_value=[{"id": str(uuid4()), "title": "iOS Engineer"}])

    service = JobDiscoveryService(
        job_repo=mock_repo,
        providers=[mock_provider_1, mock_provider_2],
    )

    result = await service.discover_jobs(user_id=uuid4(), query="iOS")
    assert result["jobs_count"] == 1
    assert result["cached"] is False


@pytest.mark.asyncio
async def test_discover_jobs_fallback_on_catastrophic_error():
    mock_provider = MagicMock()
    mock_provider.name = "remotive"
    mock_provider.fetch_jobs = AsyncMock(return_value=[])

    mock_repo = MagicMock()
    run_id = str(uuid4())
    mock_repo.create_search_run = AsyncMock(return_value={"id": run_id})
    mock_repo.update_search_run = AsyncMock(return_value={})
    mock_repo.upsert_jobs = AsyncMock(side_effect=Exception("Database down"))
    mock_repo.list_jobs = AsyncMock(return_value=[{"id": str(uuid4()), "title": "Cached Job"}])

    service = JobDiscoveryService(
        job_repo=mock_repo,
        providers=[mock_provider],
    )

    result = await service.discover_jobs(user_id=uuid4(), query="Python")
    assert result["cached"] is True
    assert result["jobs_count"] == 1
    assert result["jobs"][0]["title"] == "Cached Job"


@pytest.mark.asyncio
async def test_job_discovery_service_default_provider_and_preferences():
    mock_repo = MagicMock()
    mock_prefs_repo = MagicMock()
    user_id = str(uuid4())
    mock_prefs_repo.get_preferences = AsyncMock(
        return_value={
            "target_roles": ["Staff Engineer"],
            "years_experience": 10.0,
            "work_arrangements": ["remote"],
        }
    )

    # Initialize with default providers
    service = JobDiscoveryService(
        job_repo=mock_repo,
        preferences_repo=mock_prefs_repo,
    )
    assert len(service.providers) == 1
    assert service.providers[0].name == "linkedin_apify"

    # Mock the provider's fetch_jobs
    mock_provider = MagicMock()
    mock_provider.name = "linkedin_apify"
    mock_provider.fetch_jobs = AsyncMock(return_value=[])
    service.providers = [mock_provider]

    mock_repo.create_search_run = AsyncMock(return_value={"id": str(uuid4())})
    mock_repo.update_search_run = AsyncMock(return_value={})
    mock_repo.upsert_jobs = AsyncMock(return_value=[])

    await service.discover_jobs(user_id=user_id, query="Python")

    mock_prefs_repo.get_preferences.assert_called_once_with(user_id)
    mock_provider.fetch_jobs.assert_called_once()
    call_kwargs = mock_provider.fetch_jobs.call_args.kwargs
    assert call_kwargs["preferences"]["target_roles"] == ["Staff Engineer"]
