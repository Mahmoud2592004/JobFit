"""Unit tests for Tasks API routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.api.v1.routes.tasks import get_task_repo
from app.main import create_app

TEST_USER_ID = str(uuid4())


def sample_task_record(tid: str | None = None) -> dict:
    return {
        "id": tid or str(uuid4()),
        "user_id": TEST_USER_ID,
        "task_type": "tailor_resume",
        "payload": {"job_id": str(uuid4())},
        "status": "pending",
        "retry_count": 0,
        "max_retries": 3,
        "error_summary": None,
        "worker_id": None,
        "claimed_by": None,
        "claimed_at": None,
        "started_at": None,
        "completed_at": None,
        "created_at": "2026-10-10T00:00:00Z",
        "run_after": None,
        "result": {},
    }


@pytest.fixture
def test_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID

    mock_repo = MagicMock()
    app.dependency_overrides[get_task_repo] = lambda: mock_repo
    return app, mock_repo


@pytest.mark.asyncio
async def test_enqueue_task_endpoint(test_app):
    app, mock_repo = test_app
    task_record = sample_task_record()
    mock_repo.enqueue_task = AsyncMock(return_value=task_record)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/tasks",
            json={
                "task_type": "tailor_resume",
                "payload": {"job_id": str(uuid4())},
                "max_retries": 3,
            },
        )

    assert res.status_code == 202
    data = res.json()
    assert data["id"] == task_record["id"]
    assert data["task_type"] == "tailor_resume"
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task_endpoint_success(test_app):
    app, mock_repo = test_app
    task_record = sample_task_record()
    mock_repo.get_task = AsyncMock(return_value=task_record)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/tasks/{task_record['id']}")

    assert res.status_code == 200
    data = res.json()
    assert data["id"] == task_record["id"]
    assert data["status"] == "pending"


@pytest.mark.asyncio
async def test_get_task_endpoint_not_found(test_app):
    app, mock_repo = test_app
    mock_repo.get_task = AsyncMock(return_value=None)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get(f"/api/v1/tasks/{uuid4()}")

    assert res.status_code == 404
