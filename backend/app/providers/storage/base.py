"""
Storage provider interface.

Defines the contract for object storage operations.
Implementations must guarantee private access (no public URLs).
"""

from __future__ import annotations

from typing import Protocol


class StorageProvider(Protocol):
    """Protocol for private document storage operations."""

    async def upload_file(
        self,
        bucket: str,
        path: str,
        content: bytes,
        content_type: str,
    ) -> str:
        """
        Upload a file to the specified private bucket.

        Returns the stored file path.
        """
        ...

    async def download_file(self, bucket: str, path: str) -> bytes:
        """Download file contents as raw bytes."""
        ...

    async def create_signed_url(
        self,
        bucket: str,
        path: str,
        expires_in: int = 3600,
    ) -> str:
        """
        Generate a time-limited signed URL for private downloading.

        Default expiry is 3600 seconds (1 hour).
        """
        ...

    async def delete_file(self, bucket: str, path: str) -> bool:
        """Delete a file from the specified bucket."""
        ...
