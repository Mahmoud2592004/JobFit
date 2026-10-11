"""Tests for request-id middleware, exception formatting, and error envelopes."""

from __future__ import annotations

import pytest
from fastapi import APIRouter
from httpx import ASGITransport, AsyncClient

from app.core.exceptions import AuthenticationError, NotFoundError
from app.main import create_app

dummy_router = APIRouter(prefix="/test")


@dummy_router.get("/error-not-found")
async def trigger_not_found():
    raise NotFoundError("Candidate resume")


@dummy_router.get("/error-auth")
async def trigger_auth_error():
    raise AuthenticationError()


@dummy_router.get("/error-unhandled")
async def trigger_unhandled():
    raise RuntimeError("Simulated crash")


@dummy_router.get("/error-validation")
async def trigger_validation(count: int):
    return {"count": count}


@pytest.fixture
def app():
    application = create_app()
    application.include_router(dummy_router)
    return application


@pytest.mark.asyncio
async def test_request_id_generated_and_returned(app):
    """If no X-Request-ID is provided, one is generated and returned in header."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert "x-request-id" in response.headers
    assert len(response.headers["x-request-id"]) > 0


@pytest.mark.asyncio
async def test_request_id_propagated(app):
    """If X-Request-ID is provided by client, it is preserved in header and response."""
    custom_id = "test-custom-req-id-12345"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health", headers={"X-Request-ID": custom_id})

    assert response.status_code == 200
    assert response.headers["x-request-id"] == custom_id


@pytest.mark.asyncio
async def test_app_error_response_envelope(app):
    """AppError should be serialized into standard error envelope with request_id."""
    custom_id = "test-req-err-404"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test/error-not-found", headers={"X-Request-ID": custom_id})

    assert response.status_code == 404
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "not_found"
    assert "Candidate resume not found" in data["error"]["message"]
    assert data["error"]["request_id"] == custom_id


@pytest.mark.asyncio
async def test_unhandled_error_response_envelope(app):
    """Unhandled exception must return 500 without leaking internal error details or stack trace."""
    custom_id = "test-req-err-500"
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as client:
        response = await client.get("/test/error-unhandled", headers={"X-Request-ID": custom_id})

    assert response.status_code == 500
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "internal_server_error"
    # Never leak "Simulated crash" or python traceback
    assert "Simulated crash" not in data["error"]["message"]
    assert data["error"]["request_id"] == custom_id


@pytest.mark.asyncio
async def test_request_validation_error_envelope(app):
    """FastAPI validation error must return 422 with standard error envelope."""
    custom_id = "test-req-err-422"
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/test/error-validation?count=invalid", headers={"X-Request-ID": custom_id}
        )

    assert response.status_code == 422
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "validation_error"
    assert "details" in data["error"]
    assert data["error"]["request_id"] == custom_id
