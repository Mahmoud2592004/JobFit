"""Unit tests for MatchingService and deterministic scoring v1.0.0."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.services.matching_service import MatchingService, _tokenize


def test_tokenize():
    tokens = _tokenize("Senior Python & FastAPI Developer (Remote)!")
    assert "senior" in tokens
    assert "python" in tokens
    assert "fastapi" in tokens
    assert "developer" in tokens
    assert "remote" in tokens


def test_evaluate_match_score_strong_fit():
    service = MatchingService(
        match_repo=MagicMock(),
        job_repo=MagicMock(),
        profile_repo=MagicMock(),
    )

    profile_data = {
        "skills": ["Python", "FastAPI", "Docker", "PostgreSQL", "AWS"],
        "years_experience": 6.0,
        "seniority_level": "senior",
        "target_roles": ["Senior Backend Engineer", "Python Developer"],
    }

    job_data = {
        "title": "Senior Backend Engineer",
        "description": "We need a Senior Python engineer skilled in FastAPI, Docker, and AWS.",
        "location": "Remote",
        "work_arrangement": "remote",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "is_expired": False,
    }

    score, breakdown, evidence, missing, uncertain, freshness = service.evaluate_match_score(
        profile_data, job_data
    )

    assert score >= 85.0
    assert breakdown.skills_score >= 80.0
    assert breakdown.experience_score >= 90.0
    assert breakdown.role_score >= 90.0
    assert breakdown.work_arrangement_score == 100.0
    assert len(evidence) >= 3
    assert freshness is None


def test_evaluate_match_score_junior_applying_to_senior():
    service = MatchingService(
        match_repo=MagicMock(),
        job_repo=MagicMock(),
        profile_repo=MagicMock(),
    )

    profile_data = {
        "skills": ["HTML", "CSS"],
        "years_experience": 1.0,
        "seniority_level": "junior",
        "target_roles": ["Junior Web Developer"],
    }

    job_data = {
        "title": "Staff Principal Engineer",
        "description": "Requires deep expertise in Kubernetes, Kafka, Go, and Terraform.",
        "location": "New York, NY",
        "work_arrangement": "onsite",
        "published_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
        "is_expired": False,
    }

    score, breakdown, evidence, missing, uncertain, freshness = service.evaluate_match_score(
        profile_data, job_data
    )

    assert score < 60.0
    assert breakdown.experience_score <= 50.0
    assert len(missing) >= 1
    assert freshness is not None
    assert "days ago" in freshness


@pytest.mark.asyncio
async def test_match_job_for_user_success():
    mock_job_repo = MagicMock()
    mock_profile_repo = MagicMock()
    mock_match_repo = MagicMock()

    jid = uuid4()
    uid = uuid4()
    pvid = uuid4()

    mock_job_repo.get_job = AsyncMock(
        return_value={
            "id": str(jid),
            "title": "Python Engineer",
            "description": "Python, FastAPI",
            "work_arrangement": "remote",
        }
    )
    mock_profile_repo.get_active_profile_version = AsyncMock(
        return_value={
            "id": str(pvid),
            "profile_data": {
                "skills": ["Python", "FastAPI"],
                "years_experience": 3.0,
                "target_roles": ["Python Engineer"],
            },
        }
    )
    mock_match_repo.upsert_match = AsyncMock(
        return_value={
            "id": str(uuid4()),
            "overall_score": 92.5,
            "job_id": str(jid),
            "user_id": str(uid),
        }
    )

    service = MatchingService(
        match_repo=mock_match_repo,
        job_repo=mock_job_repo,
        profile_repo=mock_profile_repo,
    )

    res = await service.match_job_for_user(user_id=uid, job_id=jid)
    assert res["overall_score"] == 92.5
    assert "job" in res
    mock_match_repo.upsert_match.assert_called_once()


@pytest.mark.asyncio
async def test_match_job_for_user_not_found():
    mock_job_repo = MagicMock()
    mock_job_repo.get_job = AsyncMock(return_value=None)

    service = MatchingService(
        match_repo=MagicMock(),
        job_repo=mock_job_repo,
        profile_repo=MagicMock(),
    )

    with pytest.raises(NotFoundError):
        await service.match_job_for_user(user_id=uuid4(), job_id=uuid4())


@pytest.mark.asyncio
async def test_batch_match_jobs():
    mock_job_repo = MagicMock()
    mock_profile_repo = MagicMock()
    mock_match_repo = MagicMock()

    jid1 = uuid4()
    jid2 = uuid4()
    uid = uuid4()

    async def fake_get(j):
        if str(j) == str(jid1):
            return {"id": str(j), "title": "Dev", "description": "Python"}
        return None

    mock_job_repo.get_job = AsyncMock(side_effect=fake_get)
    mock_profile_repo.get_active_profile_version = AsyncMock(return_value=None)
    mock_match_repo.upsert_match = AsyncMock(
        return_value={"id": str(uuid4()), "overall_score": 75.0}
    )

    service = MatchingService(
        match_repo=mock_match_repo,
        job_repo=mock_job_repo,
        profile_repo=mock_profile_repo,
    )

    matches = await service.batch_match_jobs(user_id=uid, job_ids=[jid1, jid2])
    # jid1 succeeds, jid2 fails gracefully and is skipped
    assert len(matches) == 1


def test_evaluate_match_score_explicit_years_gap():
    service = MatchingService(
        match_repo=MagicMock(),
        job_repo=MagicMock(),
        profile_repo=MagicMock(),
    )

    profile_data = {
        "skills": ["Python", "Machine Learning"],
        "years_experience": 1.5,
        "seniority_level": "mid",
        "target_roles": ["ML Engineer"],
    }

    job_data = {
        "title": "ML Engineer - Remote Work | REF#303222",
        "description": "Requirements: - 3+ years of experience in machine learning engineering, data science, or related fields.",
        "location": "Remote",
        "work_arrangement": "remote",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "is_expired": False,
    }

    score, breakdown, evidence, missing, uncertain, freshness = service.evaluate_match_score(
        profile_data, job_data
    )

    assert breakdown.experience_score <= 40.0
    assert any("3+ years" in m for m in missing)
    assert not any("fits role baseline" in e for e in evidence)

