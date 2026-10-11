"""Tests for JWT and security utilities."""

from __future__ import annotations

import pytest
from jose import jwt

from app.core.config import Settings
from app.core.exceptions import AuthenticationError, InvalidTokenError
from app.core.security import extract_user_id, parse_bearer_token, verify_supabase_token


def test_parse_bearer_token_success():
    token = parse_bearer_token("Bearer valid_token_123")
    assert token == "valid_token_123"


def test_parse_bearer_token_missing():
    with pytest.raises(AuthenticationError):
        parse_bearer_token(None)


def test_parse_bearer_token_invalid_format():
    with pytest.raises(AuthenticationError):
        parse_bearer_token("Token valid_token_123")

    with pytest.raises(AuthenticationError):
        parse_bearer_token("Bearer")


def test_extract_user_id_success():
    user_id = extract_user_id({"sub": "user_abc_123", "role": "authenticated"})
    assert user_id == "user_abc_123"


def test_extract_user_id_missing_sub():
    with pytest.raises(InvalidTokenError):
        extract_user_id({"role": "authenticated"})


def test_verify_supabase_token_development(monkeypatch):
    """In development without jwt_secret, any well-formed JWT with sub is accepted."""
    test_settings = Settings(environment="development", supabase_jwt_secret="")
    monkeypatch.setattr("app.core.security.get_settings", lambda: test_settings)

    token = jwt.encode({"sub": "dev_user_456"}, "any-secret", algorithm="HS256")
    payload = verify_supabase_token(token)
    assert payload.get("sub") == "dev_user_456"


def test_verify_supabase_token_with_secret(monkeypatch):
    """When jwt_secret is configured, token must be signed with that secret."""
    secret = "test-secret-key-32-bytes-long-123456"
    test_settings = Settings(environment="development", supabase_jwt_secret=secret)
    monkeypatch.setattr("app.core.security.get_settings", lambda: test_settings)

    # Valid token
    valid_token = jwt.encode({"sub": "user_789"}, secret, algorithm="HS256")
    payload = verify_supabase_token(valid_token)
    assert payload.get("sub") == "user_789"

    # Token signed with wrong secret
    invalid_token = jwt.encode({"sub": "user_789"}, "wrong-secret", algorithm="HS256")
    with pytest.raises(InvalidTokenError):
        verify_supabase_token(invalid_token)
