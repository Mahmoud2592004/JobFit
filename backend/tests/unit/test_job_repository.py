"""Unit tests for JobRepository."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import ProviderError
from app.repositories.job_repository import JobRepository
from app.schemas.job import CanonicalJob


def make_canonical_job(source_name="remotive", job_id="123") -> CanonicalJob:
    return CanonicalJob(
        source_name=source_name,
        source_job_id=job_id,
        canonical_url=f"https://example.com/jobs/{job_id}",
        title="Full Stack Engineer",
        employer="Tech Co",
        location="Remote",
        work_arrangement="remote",
        employment_type="full_time",
        seniority="senior",
        description="Write code and test it.",
        salary_min=100000,
        salary_max=140000,
        salary_currency="USD",
        published_at=None,
        attribution="Job listing source",
    )


@pytest.mark.asyncio
async def test_upsert_jobs_empty():
    repo = JobRepository(client=MagicMock())
    res = await repo.upsert_jobs([])
    assert res == []


@pytest.mark.asyncio
async def test_upsert_jobs_success():
    mock_client = MagicMock()
    mock_upsert = MagicMock()
    mock_client.table.return_value.upsert.return_value = mock_upsert
    mock_upsert.execute.return_value.data = [{"id": str(uuid4()), "title": "Full Stack Engineer"}]

    repo = JobRepository(client=mock_client)
    res = await repo.upsert_jobs([make_canonical_job()])

    assert len(res) == 1
    assert res[0]["title"] == "Full Stack Engineer"


@pytest.mark.asyncio
async def test_upsert_jobs_error():
    mock_client = MagicMock()
    mock_client.table.side_effect = Exception("DB connection timeout")

    repo = JobRepository(client=mock_client)
    with pytest.raises(ProviderError):
        await repo.upsert_jobs([make_canonical_job()])


@pytest.mark.asyncio
async def test_get_job_success():
    jid = uuid4()
    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value = (
        mock_query
    )
    mock_query.execute.return_value.data = [{"id": str(jid), "title": "Backend Dev"}]

    repo = JobRepository(client=mock_client)
    res = await repo.get_job(jid)

    assert res is not None
    assert res["id"] == str(jid)


@pytest.mark.asyncio
async def test_get_job_not_found():
    mock_client = MagicMock()
    mock_query = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.limit.return_value = (
        mock_query
    )
    mock_query.execute.return_value.data = []

    repo = JobRepository(client=mock_client)
    res = await repo.get_job(uuid4())

    assert res is None


@pytest.mark.asyncio
async def test_list_jobs_with_filters():
    mock_client = MagicMock()
    mock_builder = MagicMock()
    mock_client.table.return_value.select.return_value.eq.return_value.order.return_value = (
        mock_builder
    )
    mock_builder.eq.return_value = mock_builder
    mock_builder.ilike.return_value = mock_builder
    mock_builder.range.return_value.execute.return_value.data = [{"title": "React Engineer"}]

    repo = JobRepository(client=mock_client)
    res = await repo.list_jobs(query="React", remote_only=True, limit=10, offset=0)

    assert len(res) == 1
    assert res[0]["title"] == "React Engineer"


@pytest.mark.asyncio
async def test_search_runs_lifecycle():
    user_id = uuid4()
    run_id = uuid4()
    mock_client = MagicMock()

    # create_search_run
    mock_client.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": str(run_id), "status": "running"}
    ]

    repo = JobRepository(client=mock_client)
    run = await repo.create_search_run(
        user_id=user_id,
        profile_version_id=None,
        preferences_snapshot={"query": "AI"},
        providers_used=["remotive"],
    )
    assert run["id"] == str(run_id)

    # update_search_run
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = [
        {"id": str(run_id), "status": "completed", "jobs_found": 5}
    ]
    updated = await repo.update_search_run(run_id, {"status": "completed", "jobs_found": 5})
    assert updated["jobs_found"] == 5

    # list_search_runs
    mock_select = mock_client.table.return_value.select.return_value
    mock_select.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = [
        {"id": str(run_id)}
    ]
    runs = await repo.list_search_runs(user_id=user_id)
    assert len(runs) == 1
