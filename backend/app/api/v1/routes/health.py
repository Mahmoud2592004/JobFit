"""Health check endpoints — no auth required."""

from __future__ import annotations

import time

import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])

_start_time = time.time()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    uptime_seconds: float


class ReadinessResponse(BaseModel):
    status: str
    checks: dict[str, str]


@router.get(
    "",
    response_model=HealthResponse,
    summary="Liveness check",
    description="Returns 200 if the application is running. No auth required.",
)
async def liveness() -> HealthResponse:
    """Liveness probe — confirms the process is alive."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        environment=settings.environment,
        uptime_seconds=round(time.time() - _start_time, 1),
    )


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Readiness check",
    description="Returns 200 if all dependencies are reachable. No auth required.",
)
async def readiness() -> ReadinessResponse:
    """
    Readiness probe — confirms external dependencies are configured.

    Intentionally does NOT reveal specific configuration values.
    Returns 'configured' or 'missing' per dependency.
    """
    settings = get_settings()
    checks: dict[str, str] = {
        "supabase": "configured" if settings.supabase_configured else "missing",
        "llm": "configured" if settings.llm_configured else "missing",
    }
    overall = "ok" if all(v == "configured" for v in checks.values()) else "degraded"

    log.info("readiness_check", status=overall, checks=checks)
    return ReadinessResponse(status=overall, checks=checks)
