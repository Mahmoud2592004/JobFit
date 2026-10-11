"""Tests for ProfileExtractionService and evidence grounding."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.providers.llm.mock_llm import MockLLMAdapter
from app.schemas.profile import ContactInfo, EmploymentEntry, ExtractedProfile
from app.services.profile_extraction_service import ProfileExtractionService
from tests.fixtures.resumes.samples import SAMPLE_RESUME_MLE


def test_find_evidence_source_text():
    # Explicit substring match
    raw = "Senior Software Engineer with 5 years in Python and Docker."
    text, conf = ProfileExtractionService.find_evidence_source_text(raw, "Python")
    assert conf == "explicit"
    assert text == raw

    # Inferred match
    text_inf, conf_inf = ProfileExtractionService.find_evidence_source_text(raw, "Rust")
    assert conf_inf == "inferred"

    # Empty claim
    _, conf_none = ProfileExtractionService.find_evidence_source_text(raw, "")
    assert conf_none == "uncertain"


@pytest.mark.asyncio
async def test_extract_and_persist_profile():
    canned = ExtractedProfile(
        contact=ContactInfo(
            name="John Doe",
            email="john@example.com",
            phone="+12345678",
            location="San Francisco, CA",
        ),
        summary="Senior ML Engineer",
        skills=["Python", "PyTorch", "Docker"],
        employment_history=[
            EmploymentEntry(
                company="Apex AI",
                title="Senior ML Engineer",
                start_date="2022-03",
                end_date="Present",
            )
        ],
        target_roles=["ML Engineer"],
        seniority_level="senior",
        years_experience=4.0,
    )

    mock_llm = MockLLMAdapter(canned_response=canned)
    mock_repo = MagicMock()
    user_id = uuid4()
    pvid = uuid4()

    mock_repo.create_profile_version = AsyncMock(
        return_value={"id": str(pvid), "version_number": 1, "is_confirmed": False}
    )
    mock_repo.add_profile_evidence = AsyncMock(return_value={"id": str(uuid4())})
    mock_repo.get_profile = AsyncMock(return_value=None)
    mock_repo.upsert_profile = AsyncMock(return_value={"display_name": "John Doe"})

    service = ProfileExtractionService(llm=mock_llm, profile_repo=mock_repo)
    res = await service.extract_and_persist_profile(user_id, SAMPLE_RESUME_MLE)

    assert res["id"] == str(pvid)
    mock_repo.create_profile_version.assert_awaited_once()
    assert mock_repo.add_profile_evidence.await_count >= 3
    mock_repo.upsert_profile.assert_awaited_once()
