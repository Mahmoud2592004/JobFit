"""Tests for database client initialization and BaseRepository helpers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.database import get_supabase_client
from app.core.exceptions import ProviderError
from app.repositories.base import BaseRepository


def test_get_supabase_client_unconfigured(monkeypatch):
    """When Supabase URL or key are missing, ProviderError must be raised."""
    test_settings = Settings(
        environment="development",
        supabase_url="",
        supabase_service_role_key="",
    )
    monkeypatch.setattr("app.core.database.get_settings", lambda: test_settings)
    get_supabase_client.cache_clear()

    with pytest.raises(ProviderError) as exc_info:
        get_supabase_client()

    assert "Supabase URL and Service Role Key must be configured" in str(exc_info.value)


def test_get_supabase_client_success(monkeypatch):
    """When configured, get_supabase_client creates and returns client."""
    test_settings = Settings(
        environment="development",
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="service-role-test-key",
    )
    monkeypatch.setattr("app.core.database.get_settings", lambda: test_settings)
    monkeypatch.setattr("supabase.create_client", lambda url, key: "mock_client")
    get_supabase_client.cache_clear()

    client = get_supabase_client()
    assert client == "mock_client"


def test_get_supabase_client_init_error(monkeypatch):
    """When create_client throws, ProviderError is raised."""
    test_settings = Settings(
        environment="development",
        supabase_url="https://test.supabase.co",
        supabase_service_role_key="service-role-test-key",
    )
    monkeypatch.setattr("app.core.database.get_settings", lambda: test_settings)

    def fail_init(url, key):
        raise RuntimeError("Network init error")

    monkeypatch.setattr("supabase.create_client", fail_init)
    get_supabase_client.cache_clear()

    with pytest.raises(ProviderError) as exc:
        get_supabase_client()
    assert "Network init error" in str(exc.value)


def test_base_repository_ensure_uuid_str():
    u = uuid4()
    assert BaseRepository.ensure_uuid_str(u) == str(u)
    assert BaseRepository.ensure_uuid_str("str-id-123") == "str-id-123"
    assert BaseRepository.cast_records(None) == []
    assert BaseRepository.cast_records([{"k": "v"}]) == [{"k": "v"}]
    assert BaseRepository.cast_single(None) is None
    assert BaseRepository.cast_single({"k": "v"}) == {"k": "v"}
