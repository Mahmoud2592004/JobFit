"""Tests for resumes API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.resumes import (
    get_extraction_service,
    get_profile_repo,
    get_storage_provider,
)
from app.main import create_app
from tests.fixtures.resumes.samples import MINIMAL_VALID_PDF, SAMPLE_RESUME_MLE

TEST_USER_ID = str(uuid4())


@pytest.fixture
def test_app():
    app = create_app()

    # Override current user dependency to bypass JWT requirement in unit tests
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    # Mock repositories and services
    mock_repo = MagicMock()
    mock_repo.create_resume_version = AsyncMock(
        return_value={"id": str(uuid4()), "version_number": 1}
    )
    mock_repo.update_resume_extraction = AsyncMock(return_value={})
    version_data = {
        "id": str(uuid4()),
        "user_id": TEST_USER_ID,
        "version_number": 1,
        "source_type": "pdf",
        "extraction_status": "completed",
        "created_at": "2026-10-10T00:00:00Z",
    }
    mock_repo.get_resume_versions = AsyncMock(return_value=[version_data])
    mock_repo.get_resume_version = AsyncMock(return_value=version_data)

    mock_storage = MagicMock()
    mock_storage.upload_file = AsyncMock(return_value="path/to/file.pdf")

    mock_extract = MagicMock()
    mock_extract.extract_and_persist_profile = AsyncMock(return_value={"id": str(uuid4())})

    app.dependency_overrides[get_profile_repo] = lambda: mock_repo
    app.dependency_overrides[get_storage_provider] = lambda: mock_storage
    app.dependency_overrides[get_extraction_service] = lambda: mock_extract

    return app


@pytest.mark.asyncio
async def test_upload_resume_pdf_success(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        files = {"file": ("resume.pdf", MINIMAL_VALID_PDF, "application/pdf")}
        response = await client.post("/api/v1/resumes/upload", files=files)

    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "pdf"
    assert data["status"] == "completed"
    assert "resume_version_id" in data


@pytest.mark.asyncio
async def test_upload_resume_unsupported_file(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        files = {"file": ("malicious.exe", b"MZ\x90\x00", "application/octet-stream")}
        response = await client.post("/api/v1/resumes/upload", files=files)

    assert response.status_code == 422
    data = response.json()
    assert data["error"]["code"] == "unsupported_file_type"


@pytest.mark.asyncio
async def test_paste_resume_success(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/v1/resumes/paste", json={"text": SAMPLE_RESUME_MLE})

    assert response.status_code == 201
    data = response.json()
    assert data["source_type"] == "text"
    assert data["status"] == "completed"


@pytest.mark.asyncio
async def test_paste_resume_too_short(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/api/v1/resumes/paste", json={"text": "Short"})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_resume_versions(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/api/v1/resumes")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1


@pytest.mark.asyncio
async def test_get_resume_version_success(test_app):
    vid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/resumes/{vid}")

    assert response.status_code == 200
    data = response.json()
    assert data["source_type"] == "pdf"


@pytest.mark.asyncio
async def test_get_resume_version_not_found(test_app):
    # Override mock to return None
    mock_repo = MagicMock()
    mock_repo.get_resume_version = AsyncMock(return_value=None)
    test_app.dependency_overrides[get_profile_repo] = lambda: mock_repo

    vid = uuid4()
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/resumes/{vid}")

    assert response.status_code == 404
    data = response.json()
    assert data["error"]["code"] == "not_found"
