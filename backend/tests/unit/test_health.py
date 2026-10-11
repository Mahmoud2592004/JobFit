"""Tests for health and readiness endpoints."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture
def app():
    return create_app()


@pytest.mark.asyncio
async def test_health_liveness(app):
    """GET /api/v1/health should return status ok with app metadata."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data
    assert "uptime_seconds" in data
    assert isinstance(data["uptime_seconds"], (int, float))


@pytest.mark.asyncio
async def test_health_readiness(app):
    """GET /api/v1/health/ready should return checks dictionary without leaking secrets."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/health/ready")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("ok", "degraded")
    assert "checks" in data
    assert "supabase" in data["checks"]
    assert "llm" in data["checks"]
    assert data["checks"]["supabase"] in ("configured", "missing")
    assert data["checks"]["llm"] in ("configured", "missing")
