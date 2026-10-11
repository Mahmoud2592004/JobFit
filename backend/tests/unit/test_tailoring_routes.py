"""Unit tests for Tailoring API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.tailoring import get_tailored_doc_repo, get_tailoring_service
from app.main import create_app

TEST_USER_ID = str(uuid4())


def sample_doc_record(did: str | None = None, jid: str | None = None) -> dict:
    return {
        "id": did or str(uuid4()),
        "user_id": TEST_USER_ID,
        "job_id": jid or str(uuid4()),
        "profile_version_id": str(uuid4()),
        "status": "approved",
        "structured_content": {
            "headline": "Full Stack Developer",
            "summary": "Proven track record in Python & React.",
            "skills": ["Python", "React"],
            "experience": [],
            "education": [],
            "certifications": [],
            "projects": [],
        },
        "storage_path": "tailored_resumes/123.pdf",
        "download_url": "https://storage.supabase/tailored.pdf",
        "flagged_claims": [],
        "validation_passed": True,
        "validation_version": "v1.0.0",
        "scoring_version": None,
        "template_version": "modern-clean-v1",
        "model_used": "gemini-3.5-flash-lite",
        "generation_latency_ms": 350,
        "error_summary": None,
        "created_at": "2026-10-10T00:00:00Z",
        "updated_at": "2026-10-10T00:00:00Z",
    }


@pytest.fixture
def test_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    mock_repo = MagicMock()
    mock_service = MagicMock()

    doc = sample_doc_record()
    mock_repo.list_documents = AsyncMock(return_value=[doc])
    mock_service.tailor_resume_for_job = AsyncMock(return_value=doc)
    mock_service.get_document_with_url = AsyncMock(return_value=doc)
    mock_service.update_tailored_content = AsyncMock(return_value=doc)
    mock_service.approve_document = AsyncMock(return_value=doc)

    app.dependency_overrides[get_tailored_doc_repo] = lambda: mock_repo
    app.dependency_overrides[get_tailoring_service] = lambda: mock_service

    return app


@pytest.mark.asyncio
async def test_tailor_resume_route(test_app):
    jid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/tailor",
            json={"job_id": str(jid), "template_version": "modern-clean-v1"},
        )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "approved"
    assert data["structured_content"]["headline"] == "Full Stack Developer"


@pytest.mark.asyncio
async def test_list_tailored_documents_route(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/tailored-documents")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["template_version"] == "modern-clean-v1"


@pytest.mark.asyncio
async def test_get_tailored_document_route(test_app):
    did = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/tailored-documents/{did}")

    assert response.status_code == 200
    data = response.json()
    assert data["validation_passed"] is True
    assert "tailored.pdf" in data["download_url"]


@pytest.mark.asyncio
async def test_update_tailored_document_route(test_app):
    did = uuid4()
    new_content = {
        "headline": "Lead Backend Architect",
        "summary": "Deep expertise in microservices and distributed systems.",
        "skills": ["Python", "FastAPI"],
        "experience": [],
        "education": [],
        "certifications": [],
        "projects": [],
    }
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.put(
            f"/api/v1/tailored-documents/{did}",
            json={"structured_content": new_content},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_approve_tailored_document_route(test_app):
    did = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(f"/api/v1/tailored-documents/{did}/approve")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "approved"
