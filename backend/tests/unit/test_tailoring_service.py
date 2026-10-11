"""Unit tests for TailoringService."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.core.exceptions import NotFoundError
from app.providers.llm.mock_llm import MockLLMAdapter
from app.schemas.tailoring import TailoredExperienceEntry, TailoredResumeContent
from app.services.tailoring_service import TailoringService


def make_profile():
    return {
        "skills": ["Python", "FastAPI", "Docker"],
        "employment_history": [
            {
                "company": "Apex AI",
                "title": "Backend Engineer",
                "start_date": "2021-01",
                "end_date": "Present",
            }
        ],
    }


def make_job(jid: str):
    return {
        "id": jid,
        "title": "Senior Python Developer",
        "employer": "TechCorp",
        "description": "Develop APIs using Python and FastAPI.",
    }


@pytest.mark.asyncio
async def test_tailor_resume_grounded_success():
    jid = uuid4()
    uid = uuid4()
    pvid = uuid4()
    doc_id = uuid4()

    canned = TailoredResumeContent(
        headline="Senior Python Developer",
        summary="Specialist in Python and FastAPI.",
        skills=["Python", "FastAPI"],
        experience=[
            TailoredExperienceEntry(
                company="Apex AI",
                title="Backend Engineer",
                bullet_points=["Built FastAPI microservices."],
            )
        ],
    )

    mock_llm = MockLLMAdapter(canned_response=canned)
    mock_tailored_repo = MagicMock()
    mock_profile_repo = MagicMock()
    mock_job_repo = MagicMock()
    mock_storage = MagicMock()

    mock_job_repo.get_job = AsyncMock(return_value=make_job(str(jid)))
    mock_profile_repo.get_active_profile_version = AsyncMock(
        return_value={"id": str(pvid), "profile_data": make_profile()}
    )
    mock_profile_repo.get_profile = AsyncMock(return_value={"display_name": "Test User"})

    mock_tailored_repo.create_document = AsyncMock(
        return_value={"id": str(doc_id), "status": "generating"}
    )
    mock_tailored_repo.update_document = AsyncMock(
        side_effect=lambda doc_id, user_id, updates: {"id": str(doc_id), **updates}
    )

    mock_storage.upload_file = AsyncMock(return_value=f"path/{doc_id}.pdf")
    mock_storage.create_signed_url = AsyncMock(return_value="https://storage.supabase/signed.pdf")

    service = TailoringService(
        llm=mock_llm,
        tailored_repo=mock_tailored_repo,
        profile_repo=mock_profile_repo,
        job_repo=mock_job_repo,
        storage=mock_storage,
    )

    res = await service.tailor_resume_for_job(user_id=uid, job_id=jid)

    assert res["status"] == "approved"
    assert res["validation_passed"] is True
    assert len(res["flagged_claims"]) == 0
    assert "signed.pdf" in res["download_url"]
    mock_storage.upload_file.assert_called_once()


@pytest.mark.asyncio
async def test_tailor_resume_unverified_skill_requires_review():
    jid = uuid4()
    uid = uuid4()
    pvid = uuid4()
    doc_id = uuid4()

    # Model hallucinations a skill (Golang)
    canned = TailoredResumeContent(
        headline="Senior Python Developer",
        summary="Specialist in Python.",
        skills=["Python", "Golang"],
        experience=[
            TailoredExperienceEntry(
                company="Apex AI",
                title="Backend Engineer",
                bullet_points=["Built microservices."],
            )
        ],
    )

    mock_llm = MockLLMAdapter(canned_response=canned)
    mock_tailored_repo = MagicMock()
    mock_profile_repo = MagicMock()
    mock_job_repo = MagicMock()
    mock_storage = MagicMock()

    mock_job_repo.get_job = AsyncMock(return_value=make_job(str(jid)))
    mock_profile_repo.get_active_profile_version = AsyncMock(
        return_value={"id": str(pvid), "profile_data": make_profile()}
    )
    mock_profile_repo.get_profile = AsyncMock(return_value=None)
    mock_tailored_repo.create_document = AsyncMock(
        return_value={"id": str(doc_id), "status": "generating"}
    )
    mock_tailored_repo.update_document = AsyncMock(
        side_effect=lambda doc_id, user_id, updates: {"id": str(doc_id), **updates}
    )
    mock_storage.upload_file = AsyncMock(return_value="path.pdf")
    mock_storage.create_signed_url = AsyncMock(return_value="https://signed.pdf")

    service = TailoringService(
        llm=mock_llm,
        tailored_repo=mock_tailored_repo,
        profile_repo=mock_profile_repo,
        job_repo=mock_job_repo,
        storage=mock_storage,
    )

    res = await service.tailor_resume_for_job(user_id=uid, job_id=jid)

    assert res["status"] == "review_required"
    assert res["validation_passed"] is False
    assert len(res["flagged_claims"]) == 1
    assert res["flagged_claims"][0]["claim"] == "Golang"


@pytest.mark.asyncio
async def test_tailor_resume_job_not_found():
    mock_job_repo = MagicMock()
    mock_job_repo.get_job = AsyncMock(return_value=None)

    service = TailoringService(
        llm=MagicMock(),
        tailored_repo=MagicMock(),
        profile_repo=MagicMock(),
        job_repo=mock_job_repo,
        storage=MagicMock(),
    )

    with pytest.raises(NotFoundError):
        await service.tailor_resume_for_job(user_id=uuid4(), job_id=uuid4())


@pytest.mark.asyncio
async def test_approve_and_download_document():
    uid = uuid4()
    did = uuid4()

    mock_tailored_repo = MagicMock()
    mock_storage = MagicMock()

    mock_tailored_repo.get_document = AsyncMock(
        return_value={"id": str(did), "storage_path": "path.pdf", "status": "review_required"}
    )
    mock_tailored_repo.update_document = AsyncMock(
        return_value={"id": str(did), "storage_path": "path.pdf", "status": "approved"}
    )
    mock_storage.create_signed_url = AsyncMock(return_value="https://signed-url.pdf")

    service = TailoringService(
        llm=MagicMock(),
        tailored_repo=mock_tailored_repo,
        profile_repo=MagicMock(),
        job_repo=MagicMock(),
        storage=mock_storage,
    )

    approved = await service.approve_document(user_id=uid, doc_id=did)
    assert approved["status"] == "approved"
    assert approved["download_url"] == "https://signed-url.pdf"

    fetched = await service.get_document_with_url(user_id=uid, doc_id=did)
    assert fetched["download_url"] == "https://signed-url.pdf"
