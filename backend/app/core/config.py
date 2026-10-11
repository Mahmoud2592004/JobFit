"""
Centralized, validated application configuration.

Settings are loaded from environment variables (and an optional .env file).
The application fails at startup if any mandatory production setting is
missing or invalid — no silent defaults in production.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All application configuration, validated at startup."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ───────────────────────────────────────────────────────────────────
    app_version: str = "0.1.0"
    environment: Literal["development", "staging", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = ""  # Validated below — required in production
    allowed_origins: list[str] | str = ["http://localhost:3000", "http://localhost:5173"]

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""  # ⚠️ SERVER-SIDE ONLY — never expose
    supabase_jwt_secret: str = ""

    # ── LLM ───────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    llm_model: str = "gemini-3.5-flash-lite"  # per user requirement
    llm_provider: Literal["gemini", "groq"] = "gemini"
    groq_api_key: str = ""

    # ── File upload ───────────────────────────────────────────────────────────
    max_upload_size_mb: int = 10
    max_parse_seconds: int = 30

    # ── Task queue ────────────────────────────────────────────────────────────
    task_poll_interval_seconds: int = 5
    task_max_retries: int = 3
    task_claim_timeout_seconds: int = 300  # stale task recovery threshold

    # ── Storage ───────────────────────────────────────────────────────────────
    signed_url_expiry_seconds: int = 3600  # 1 hour
    storage_resume_bucket: str = "resumes"
    storage_documents_bucket: str = "tailored-documents"

    # ── Fabrication validator thresholds ──────────────────────────────────────
    fab_bullet_ratio: float = 0.65
    fab_letter_ratio: float = 0.55
    fab_skill_ratio: float = 0.85

    # ── Job Aggregator / Apify ────────────────────────────────────────────────
    apify_api_token: str = ""
    apify_actor_id: str = "curious_coder~linkedin-jobs-scraper"
    apify_timeout_seconds: int = 120

    # ── Observability ─────────────────────────────────────────────────────────
    opik_api_key: str = ""  # Optional; tracing disabled if empty
    enable_llm_tracing: bool = False  # Must be explicitly enabled

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_origins(cls, v: object) -> list[str]:
        """Accept comma-separated string or list."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v  # type: ignore[return-value]

    @field_validator("max_upload_size_mb")
    @classmethod
    def validate_max_upload(cls, v: int) -> int:
        if v < 1 or v > 50:
            raise ValueError("max_upload_size_mb must be between 1 and 50")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        """Fail startup when mandatory production settings are missing."""
        if self.environment == "production":
            required = {
                "secret_key": self.secret_key,
                "supabase_url": self.supabase_url,
                "supabase_service_role_key": self.supabase_service_role_key,
                "supabase_jwt_secret": self.supabase_jwt_secret,
            }
            missing = [k for k, v in required.items() if not v]
            if missing:
                raise ValueError(f"Missing required production settings: {', '.join(missing)}")

            if self.llm_provider == "gemini" and not self.gemini_api_key:
                raise ValueError("GEMINI_API_KEY is required when LLM_PROVIDER=gemini")
            if self.llm_provider == "groq" and not self.groq_api_key:
                raise ValueError("GROQ_API_KEY is required when LLM_PROVIDER=groq")

        # Generate a development-only secret key if not provided
        if not self.secret_key:
            self.secret_key = secrets.token_urlsafe(32)

        return self

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def supabase_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def llm_configured(self) -> bool:
        if self.llm_provider == "gemini":
            return bool(self.gemini_api_key)
        if self.llm_provider == "groq":
            return bool(self.groq_api_key)
        return False


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached, validated settings instance."""
    return Settings()
