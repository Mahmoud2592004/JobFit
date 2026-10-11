"""
Supabase Storage provider implementation.

Enforces:
- Private buckets only (signed URLs with expiration).
- Scoped storage paths per user (prevents path traversal and cross-user overwriting).
- Only configured buckets are permitted.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import structlog

from app.core.config import get_settings
from app.core.exceptions import ProviderError, ValidationError

if TYPE_CHECKING:
    from supabase import Client

log = structlog.get_logger(__name__)

# Disallow path traversal, backslashes, double slashes
_SAFE_PATH_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+(/[a-zA-Z0-9_.-]+)+$")


class SupabaseStorageProvider:
    """Storage provider backed by Supabase Storage."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client
        self._settings = get_settings()
        self._allowed_buckets = frozenset(
            {
                self._settings.storage_resume_bucket,
                self._settings.storage_documents_bucket,
            }
        )

    @property
    def client(self) -> Client:
        if self._client is None:
            from app.core.database import get_supabase_client

            self._client = get_supabase_client()
        if (
            self._settings.supabase_service_role_key
            and hasattr(self._client, "storage")
            and hasattr(self._client.storage, "_headers")
        ):
            self._client.storage._headers["Authorization"] = (
                f"Bearer {self._settings.supabase_service_role_key}"
            )
            self._client.storage._headers["apikey"] = (
                self._settings.supabase_service_role_key
            )
        return self._client

    def _validate_bucket(self, bucket: str) -> None:
        if bucket not in self._allowed_buckets:
            raise ValidationError(f"Storage bucket '{bucket}' is not permitted.")

    def _validate_path(self, path: str) -> None:
        if not path or ".." in path or "\\" in path or not _SAFE_PATH_PATTERN.match(path):
            raise ValidationError(f"Invalid or unsafe storage path: '{path}'")

    @staticmethod
    def build_user_scoped_path(user_id: str, filename: str) -> str:
        """Create a sanitized storage path scoped to a user ID."""
        clean_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", filename)
        return f"{user_id}/{clean_name}"

    async def upload_file(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload raw file bytes to Supabase Storage."""
        self._validate_bucket(bucket)
        self._validate_path(path)

        try:
            # supabase.storage.from_(bucket).upload(path, content, file_options)
            self.client.storage.from_(bucket).upload(
                path=path,
                file=content,
                file_options={"content-type": content_type, "upsert": "true"},
            )
            log.info("storage_upload_success", bucket=bucket, path=path)
            return path
        except Exception as exc:
            log.error("storage_upload_failed", bucket=bucket, path=path, error=str(exc))
            raise ProviderError(provider="Supabase Storage", detail=str(exc)) from exc

    async def download_file(self, bucket: str, path: str) -> bytes:
        """Download raw file bytes from Supabase Storage."""
        self._validate_bucket(bucket)
        self._validate_path(path)

        try:
            data: bytes = self.client.storage.from_(bucket).download(path)
            log.info("storage_download_success", bucket=bucket, path=path)
            return data
        except Exception as exc:
            log.error("storage_download_failed", bucket=bucket, path=path, error=str(exc))
            raise ProviderError(provider="Supabase Storage", detail=str(exc)) from exc

    async def create_signed_url(
        self,
        bucket: str,
        path: str,
        expires_in: int = 3600,
    ) -> str:
        """Generate a secure signed download URL for private files."""
        self._validate_bucket(bucket)
        self._validate_path(path)

        # Cap signed URL expiry at 24 hours (86400 seconds)
        capped_expires_in = min(expires_in, 86400)

        try:
            res = self.client.storage.from_(bucket).create_signed_url(
                path=path,
                expires_in=capped_expires_in,
            )
            url = ""
            if isinstance(res, dict):
                url = str(res.get("signedURL") or res.get("signedUrl") or "")
            if not url:
                raise ProviderError(
                    provider="Supabase Storage",
                    detail="Failed to retrieve signed URL from response.",
                )
            log.info("storage_signed_url_created", bucket=bucket, path=path)
            return url
        except Exception as exc:
            log.error("storage_signed_url_failed", bucket=bucket, path=path, error=str(exc))
            raise ProviderError(provider="Supabase Storage", detail=str(exc)) from exc

    async def delete_file(self, bucket: str, path: str) -> bool:
        """Delete a file from Supabase Storage."""
        self._validate_bucket(bucket)
        self._validate_path(path)

        try:
            self.client.storage.from_(bucket).remove([path])
            log.info("storage_file_deleted", bucket=bucket, path=path)
            return True
        except Exception as exc:
            log.error("storage_delete_failed", bucket=bucket, path=path, error=str(exc))
            raise ProviderError(provider="Supabase Storage", detail=str(exc)) from exc
