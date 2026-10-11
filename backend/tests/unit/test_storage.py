"""Tests for Supabase Storage provider and path security."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.exceptions import ProviderError, ValidationError
from app.providers.storage.supabase_storage import SupabaseStorageProvider


def test_build_user_scoped_path():
    """Scoped path must namespace by user ID and sanitize characters."""
    user_id = "user-123-abc"
    filename = "My Resume (2026) #final!.pdf"
    scoped = SupabaseStorageProvider.build_user_scoped_path(user_id, filename)
    assert scoped == "user-123-abc/My_Resume__2026___final_.pdf"
    assert scoped.startswith(f"{user_id}/")


def test_disallowed_bucket():
    """Attempting to access an unpermitted bucket must raise ValidationError."""
    provider = SupabaseStorageProvider(client=MagicMock())
    with pytest.raises(ValidationError) as exc:
        provider._validate_bucket("malicious-bucket")
    assert "not permitted" in str(exc.value)


@pytest.mark.parametrize(
    "bad_path",
    [
        "../secrets.txt",
        "user1/../../etc/passwd",
        "user1\\resume.pdf",
        "/leading/slash.pdf",
        "double//slash.pdf",
        "",
    ],
)
def test_path_traversal_rejected(bad_path):
    """Paths containing directory traversal or forbidden characters must fail."""
    provider = SupabaseStorageProvider(client=MagicMock())
    with pytest.raises(ValidationError):
        provider._validate_path(bad_path)


@pytest.mark.asyncio
async def test_upload_file_success():
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket
    mock_bucket.upload.return_value = {"Key": "resumes/user1/resume.pdf"}

    provider = SupabaseStorageProvider(client=mock_client)
    path = await provider.upload_file(
        bucket="resumes",
        path="user1/resume.pdf",
        content=b"%PDF-1.4 test resume",
        content_type="application/pdf",
    )

    assert path == "user1/resume.pdf"
    mock_client.storage.from_.assert_called_with("resumes")
    mock_bucket.upload.assert_called_once()


@pytest.mark.asyncio
async def test_download_file_success():
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket
    mock_bucket.download.return_value = b"%PDF-1.4 file content"

    provider = SupabaseStorageProvider(client=mock_client)
    content = await provider.download_file("resumes", "user1/resume.pdf")

    assert content == b"%PDF-1.4 file content"
    mock_client.storage.from_.assert_called_with("resumes")
    mock_bucket.download.assert_called_with("user1/resume.pdf")


@pytest.mark.asyncio
async def test_create_signed_url_success():
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket
    mock_bucket.create_signed_url.return_value = {
        "signedURL": "https://storage.supabase.co/signed?token=xyz"
    }

    provider = SupabaseStorageProvider(client=mock_client)
    url = await provider.create_signed_url("resumes", "user1/resume.pdf", expires_in=1800)

    assert url == "https://storage.supabase.co/signed?token=xyz"
    mock_bucket.create_signed_url.assert_called_with(path="user1/resume.pdf", expires_in=1800)


@pytest.mark.asyncio
async def test_delete_file_success():
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket

    provider = SupabaseStorageProvider(client=mock_client)
    res = await provider.delete_file("resumes", "user1/resume.pdf")

    assert res is True
    mock_bucket.remove.assert_called_with(["user1/resume.pdf"])


@pytest.mark.asyncio
async def test_storage_operation_failure_raises_provider_error():
    mock_client = MagicMock()
    mock_bucket = MagicMock()
    mock_client.storage.from_.return_value = mock_bucket
    mock_bucket.upload.side_effect = RuntimeError("Storage service down")

    provider = SupabaseStorageProvider(client=mock_client)
    with pytest.raises(ProviderError):
        await provider.upload_file("resumes", "user1/resume.pdf", b"data")
