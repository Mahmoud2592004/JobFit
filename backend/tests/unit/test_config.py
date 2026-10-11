"""Tests for Settings validation and loading."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings():
    """Default settings in development mode should have valid defaults."""
    settings = Settings(environment="development")
    assert settings.environment == "development"
    assert settings.llm_model == "gemini-3.5-flash-lite"
    assert settings.llm_provider == "gemini"
    assert settings.max_upload_size_mb == 10
    assert settings.max_upload_size_bytes == 10 * 1024 * 1024
    assert not settings.is_production
    assert isinstance(settings.allowed_origins, list)
    assert len(settings.secret_key) > 0  # auto-generated development secret


def test_allowed_origins_parsing():
    """Origins can be provided as a comma-separated string."""
    settings = Settings(
        environment="development",
        allowed_origins="https://example.com, https://app.example.com",  # type: ignore[reportArgumentType]
    )
    assert settings.allowed_origins == [
        "https://example.com",
        "https://app.example.com",
    ]


def test_max_upload_size_validation():
    """max_upload_size_mb must be within 1 and 50."""
    with pytest.raises(ValidationError):
        Settings(max_upload_size_mb=0)

    with pytest.raises(ValidationError):
        Settings(max_upload_size_mb=100)

    valid = Settings(max_upload_size_mb=25)
    assert valid.max_upload_size_mb == 25


def test_production_settings_validation_missing_secrets():
    """In production mode, missing required secrets must raise validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            secret_key="",
            supabase_url="",
            supabase_service_role_key="",
            supabase_jwt_secret="",
        )
    assert "Missing required production settings" in str(exc_info.value)


def test_production_settings_validation_gemini_key():
    """In production with gemini provider, GEMINI_API_KEY must be provided."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            secret_key="a" * 32,
            supabase_url="https://xyz.supabase.co",
            supabase_service_role_key="service-key",
            supabase_jwt_secret="jwt-secret",
            llm_provider="gemini",
            gemini_api_key="",
        )
    assert "GEMINI_API_KEY is required" in str(exc_info.value)


def test_production_settings_validation_groq_key():
    """In production with groq provider, GROQ_API_KEY must be provided."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            environment="production",
            secret_key="a" * 32,
            supabase_url="https://xyz.supabase.co",
            supabase_service_role_key="service-key",
            supabase_jwt_secret="jwt-secret",
            llm_provider="groq",
            groq_api_key="",
        )
    assert "GROQ_API_KEY is required" in str(exc_info.value)
