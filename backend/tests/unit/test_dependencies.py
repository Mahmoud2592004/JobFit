"""Tests for API dependencies (auth and pagination)."""

from __future__ import annotations

import pytest
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.api.dependencies import PaginationParams, get_current_user
from app.core.config import Settings
from app.core.exceptions import AuthenticationError, InvalidTokenError


@pytest.mark.asyncio
async def test_get_current_user_no_credentials():
    with pytest.raises(AuthenticationError):
        await get_current_user(None)


@pytest.mark.asyncio
async def test_get_current_user_valid(monkeypatch):
    secret = "test-secret-key-32-bytes-long-123456"
    test_settings = Settings(environment="development", supabase_jwt_secret=secret)
    monkeypatch.setattr("app.core.security.get_settings", lambda: test_settings)

    token = jwt.encode({"sub": "usr_999"}, secret, algorithm="HS256")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    user_id = await get_current_user(credentials)
    assert user_id == "usr_999"


@pytest.mark.asyncio
async def test_get_current_user_invalid(monkeypatch):
    secret = "test-secret-key-32-bytes-long-123456"
    test_settings = Settings(environment="development", supabase_jwt_secret=secret)
    monkeypatch.setattr("app.core.security.get_settings", lambda: test_settings)

    token = jwt.encode({"sub": "usr_999"}, "wrong-key", algorithm="HS256")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    with pytest.raises(InvalidTokenError):
        await get_current_user(credentials)


def test_pagination_params_defaults():
    params = PaginationParams()
    assert params.page == 1
    assert params.page_size == 20
    assert params.offset == 0
    assert params.limit == 20


def test_pagination_params_custom():
    params = PaginationParams(page=3, page_size=15)
    assert params.page == 3
    assert params.page_size == 15
    assert params.offset == 30
    assert params.limit == 15
