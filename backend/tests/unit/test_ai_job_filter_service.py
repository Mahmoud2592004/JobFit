"""Unit tests for AIJobFilterService with Gemini LLM reasoning."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.providers.llm.mock_llm import MockLLMAdapter
from app.schemas.job import (
    JobAIEvaluation,
    JobAIEvaluationBatch,
)
from app.services.ai_job_filter_service import AIJobFilterService


@pytest.fixture
def sample_jobs():
    return [
        {
            "id": str(uuid4()),
            "source_name": "remotive",
            "source_job_id": "101",
            "canonical_url": "https://remotive.com/101",
            "title": "Senior Python Backend Engineer",
            "employer": "CloudScale",
            "location": "Worldwide",
            "work_arrangement": "remote",
            "employment_type": "full_time",
            "seniority": "senior",
            "description": "Requires 5+ years experience with Python, FastAPI, and Docker.",
            "salary_min": 140000,
            "salary_max": 170000,
            "salary_currency": "USD",
            "published_at": "2026-10-01T00:00:00Z",
            "retrieved_at": "2026-10-10T00:00:00Z",
            "is_expired": False,
            "attribution": "Powered by Remotive",
        },
        {
            "id": str(uuid4()),
            "source_name": "arbeitnow",
            "source_job_id": "102",
            "canonical_url": "https://arbeitnow.com/102",
            "title": "Junior Web Designer",
            "employer": "LocalAgency",
            "location": "Berlin, Germany",
            "work_arrangement": "onsite",
            "employment_type": "part_time",
            "seniority": "junior",
            "description": "Onsite entry role in Berlin. Requires HTML and Figma.",
            "salary_min": 35000,
            "salary_max": 45000,
            "salary_currency": "EUR",
            "published_at": "2026-10-02T00:00:00Z",
            "retrieved_at": "2026-10-10T00:00:00Z",
            "is_expired": False,
            "attribution": "Powered by Arbeitnow",
        },
    ]


@pytest.mark.asyncio
async def test_ai_job_filter_service_fallback(sample_jobs):
    mock_job_repo = MagicMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=sample_jobs)

    mock_profile_repo = MagicMock()
    mock_profile_repo.get_profile = AsyncMock(return_value={"display_name": "Alice"})
    mock_profile_repo.get_active_profile_version = AsyncMock(
        return_value={
            "years_experience": 5.5,
            "seniority_level": "senior",
            "skills": ["Python", "FastAPI", "Docker"],
            "target_roles": ["Senior Python Engineer"],
        }
    )

    mock_prefs_repo = MagicMock()
    mock_prefs_repo.get_preferences = AsyncMock(
        return_value={
            "work_arrangements": ["remote"],
            "locations": ["Worldwide"],
        }
    )

    service = AIJobFilterService(
        job_repo=mock_job_repo,
        profile_repo=mock_profile_repo,
        preferences_repo=mock_prefs_repo,
        llm_adapter=MockLLMAdapter(),
    )

    response = await service.filter_jobs_for_candidate(
        user_id=uuid4(),
        query="Python",
        min_fit="all",
        limit=10,
    )

    assert response.total_evaluated == 2
    assert response.candidate_summary["years_experience"] == 5.5
    assert len(response.results) == 2

    # Senior Python remote job should score higher than onsite junior designer
    first = response.results[0]
    second = response.results[1]
    assert first.job.title == "Senior Python Backend Engineer"
    assert first.evaluation.fit_level in ("Strong Fit", "Potential Fit")
    assert first.evaluation.is_valid_match is True

    assert second.job.title == "Junior Web Designer"
    assert second.evaluation.fit_level == "Not a Fit"


@pytest.mark.asyncio
async def test_ai_job_filter_service_with_structured_llm(sample_jobs):
    mock_job_repo = MagicMock()
    mock_job_repo.list_jobs = AsyncMock(return_value=sample_jobs)

    mock_profile_repo = MagicMock()
    mock_profile_repo.get_profile = AsyncMock(return_value={"display_name": "Bob"})
    mock_profile_repo.get_active_profile_version = AsyncMock(
        return_value={
            "years_experience": 6.0,
            "seniority_level": "senior",
            "skills": ["Python"],
            "target_roles": ["Senior Engineer"],
        }
    )

    mock_prefs_repo = MagicMock()
    mock_prefs_repo.get_preferences = AsyncMock(return_value={"work_arrangements": ["remote"]})

    llm_mock_batch = JobAIEvaluationBatch(
        evaluations=[
            JobAIEvaluation(
                job_id=str(sample_jobs[0]["id"]),
                is_valid_match=True,
                fit_level="Strong Fit",
                ai_score=94,
                experience_fit_analysis="6 years satisfies senior requirements.",
                preference_fit_analysis="100% Remote matches preferences.",
                recruiter_rationale="Ideal match for candidate's Python background.",
            ),
            JobAIEvaluation(
                job_id=str(sample_jobs[1]["id"]),
                is_valid_match=False,
                fit_level="Not a Fit",
                ai_score=30,
                experience_fit_analysis="Role is junior entry-level.",
                preference_fit_analysis="Onsite role conflicts with remote preference.",
                recruiter_rationale="Disqualified: onsite role and seniority mismatch.",
            ),
        ]
    )

    mock_llm = MagicMock()
    mock_llm.extract_structured = AsyncMock(return_value=llm_mock_batch)

    service = AIJobFilterService(
        job_repo=mock_job_repo,
        profile_repo=mock_profile_repo,
        preferences_repo=mock_prefs_repo,
        llm_adapter=mock_llm,
    )

    res = await service.filter_jobs_for_candidate(
        user_id=uuid4(),
        min_fit="valid_only",
        limit=5,
    )

    assert res.total_evaluated == 2
    assert res.valid_count == 1
    assert len(res.results) == 1
    assert res.results[0].job.title == "Senior Python Backend Engineer"
    assert res.results[0].evaluation.ai_score == 94
