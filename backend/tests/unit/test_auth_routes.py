"""Unit tests for Auth API routes."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import get_current_user
from app.main import create_app

TEST_USER_ID = str(uuid4())


@pytest.fixture
def test_app():
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: TEST_USER_ID
    return app


@pytest.mark.asyncio
async def test_auth_session_success(test_app):
    mock_client = MagicMock()
    mock_auth_res = MagicMock()
    mock_auth_res.session.access_token = "valid-test-token"
    mock_auth_res.user.id = str(uuid4())
    mock_auth_res.user.email = "developer@jobfit.io"
    mock_auth_res.user.user_metadata = {"name": "Developer"}
    mock_client.auth.sign_in_with_password.return_value = mock_auth_res

    with patch("app.core.database.get_supabase_client", return_value=mock_client):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/session",
                json={
                    "email": "developer@jobfit.io",
                    "password": "password123",
                    "name": "Developer",
                },
            )

    assert res.status_code == 200
    data = res.json()
    assert data["access_token"] == "valid-test-token"
    assert data["email"] == "developer@jobfit.io"


@pytest.mark.asyncio
async def test_auth_session_invalid_credentials(test_app):
    mock_client = MagicMock()
    mock_client.auth.sign_in_with_password.side_effect = Exception("Invalid login credentials")

    with patch("app.core.database.get_supabase_client", return_value=mock_client):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/session",
                json={"email": "developer@jobfit.io", "password": "wrong_password"},
            )

    assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_signup_success(test_app):
    mock_client = MagicMock()
    mock_auth_res = MagicMock()
    mock_auth_res.session.access_token = "new-user-token"
    mock_auth_res.user.id = str(uuid4())
    mock_auth_res.user.email = "newuser@jobfit.io"
    mock_auth_res.user.user_metadata = {"name": "New User"}
    mock_client.auth.admin.create_user.return_value = MagicMock()
    mock_client.auth.sign_in_with_password.return_value = mock_auth_res

    with patch("app.core.database.get_supabase_client", return_value=mock_client):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/signup",
                json={"email": "newuser@jobfit.io", "password": "password123", "name": "New User"},
            )

    assert res.status_code == 201
    data = res.json()
    assert data["access_token"] == "new-user-token"
    assert data["email"] == "newuser@jobfit.io"


@pytest.mark.asyncio
async def test_auth_signup_duplicate_email(test_app):
    mock_client = MagicMock()
    mock_client.auth.admin.create_user.side_effect = Exception(
        "A user with this email address has already been registered"
    )

    with patch("app.core.database.get_supabase_client", return_value=mock_client):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/signup",
                json={
                    "email": "existing@jobfit.io",
                    "password": "password123",
                    "name": "Existing User",
                },
            )

    assert res.status_code == 409
    data = res.json()
    assert data["error"]["code"] == "conflict"
    assert "already exists" in data["error"]["message"].lower()


@pytest.mark.asyncio
async def test_auth_me_endpoint(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/auth/me")

    assert res.status_code == 200
    data = res.json()
    assert data["user_id"] == TEST_USER_ID


@pytest.mark.asyncio
async def test_auth_refresh_success(test_app):
    mock_client = MagicMock()
    mock_auth_res = MagicMock()
    mock_auth_res.session.access_token = "refreshed-token"
    mock_auth_res.session.refresh_token = "new-refresh-token"
    mock_auth_res.user.id = str(uuid4())
    mock_auth_res.user.email = "refreshed@jobfit.io"
    mock_auth_res.user.user_metadata = {"name": "Refreshed User"}
    mock_client.auth.refresh_session.return_value = mock_auth_res

    with patch("app.core.database.get_supabase_client", return_value=mock_client):
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "valid-old-refresh"},
            )

    assert res.status_code == 200
    data = res.json()
    assert data["access_token"] == "refreshed-token"
    assert data["refresh_token"] == "new-refresh-token"
    assert "sb_access_token" in res.cookies


@pytest.mark.asyncio
async def test_auth_logout(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/auth/logout")

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}
