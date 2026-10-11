"""Unit tests for Applications API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.applications import get_application_repo
from app.main import create_app

TEST_USER_ID = str(uuid4())


def sample_application_record(aid: str | None = None, jid: str | None = None) -> dict:
    return {
        "id": aid or str(uuid4()),
        "user_id": TEST_USER_ID,
        "job_id": jid or str(uuid4()),
        "tailored_document_id": None,
        "status": "saved",
        "notes": "Looking forward to this role",
        "applied_at": None,
        "follow_up_date": None,
        "offer_amount": None,
        "offer_currency": None,
        "last_activity_at": "2026-10-10T00:00:00Z",
        "created_at": "2026-10-10T00:00:00Z",
        "updated_at": "2026-10-10T00:00:00Z",
        "job": None,
    }


def sample_event_record(eid: str | None = None, aid: str | None = None) -> dict:
    return {
        "id": eid or str(uuid4()),
        "application_id": aid or str(uuid4()),
        "user_id": TEST_USER_ID,
        "from_status": "saved",
        "to_status": "applied",
        "note": "Status transitioned to 'applied'",
        "occurred_at": "2026-10-10T00:00:00Z",
    }


@pytest.fixture
def test_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    mock_repo = MagicMock()
    app.dependency_overrides[get_application_repo] = lambda: mock_repo
    return app, mock_repo


@pytest.mark.asyncio
async def test_create_application_endpoint(test_app):
    app, mock_repo = test_app
    app_record = sample_application_record()
    mock_repo.create_application = AsyncMock(return_value=app_record)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/applications",
            json={
                "job_id": app_record["job_id"],
                "status": "saved",
                "notes": "Initial interest",
            },
        )

    assert res.status_code == 201
    data = res.json()
    assert data["id"] == app_record["id"]
    assert data["status"] == "saved"


@pytest.mark.asyncio
async def test_list_applications_endpoint(test_app):
    app, mock_repo = test_app
    app_record = sample_application_record()
    mock_repo.list_applications = AsyncMock(return_value=[app_record])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/applications?status=saved&limit=10&offset=0")

    assert res.status_code == 200
    data = res.json()
    assert len(data) == 1
    assert data[0]["id"] == app_record["id"]


@pytest.mark.asyncio
async def test_get_application_endpoint_success(test_app):
    app, mock_repo = test_app
    app_record = sample_application_record()
    mock_repo.get_application = AsyncMock(return_value=app_record)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/applications/{app_record['id']}")

    assert res.status_code == 200
    data = res.json()
    assert data["id"] == app_record["id"]


@pytest.mark.asyncio
async def test_get_application_endpoint_not_found(test_app):
    app, mock_repo = test_app
    mock_repo.get_application = AsyncMock(return_value=None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/applications/{uuid4()}")

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_update_application_endpoint_success(test_app):
    app, mock_repo = test_app
    current = sample_application_record()
    updated = {**current, "status": "applied"}
    mock_repo.get_application = AsyncMock(return_value=current)
    mock_repo.update_application = AsyncMock(return_value=updated)
    mock_repo.add_application_event = AsyncMock(return_value=sample_event_record())

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.patch(
            f"/api/v1/applications/{current['id']}",
            json={"status": "applied", "notes": "Submitted application"},
        )

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "applied"
    mock_repo.add_application_event.assert_called_once()


@pytest.mark.asyncio
async def test_update_application_endpoint_not_found(test_app):
    app, mock_repo = test_app
    mock_repo.get_application = AsyncMock(return_value=None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.patch(
            f"/api/v1/applications/{uuid4()}",
            json={"status": "interviewing"},
        )

    assert res.status_code == 404


@pytest.mark.asyncio
async def test_add_and_list_events_endpoints(test_app):
    app, mock_repo = test_app
    app_record = sample_application_record()
    event_record = sample_event_record(aid=app_record["id"])

    mock_repo.get_application = AsyncMock(return_value=app_record)
    mock_repo.add_application_event = AsyncMock(return_value=event_record)
    mock_repo.list_application_events = AsyncMock(return_value=[event_record])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Add event
        res_post = await client.post(
            f"/api/v1/applications/{app_record['id']}/events",
            json={"event_type": "status_change", "note": "Applied"},
        )
        assert res_post.status_code == 201

        # List events
        res_get = await client.get(f"/api/v1/applications/{app_record['id']}/events")
        assert res_get.status_code == 200
        events = res_get.json()
        assert len(events) == 1
        assert events[0]["to_status"] == "applied"
