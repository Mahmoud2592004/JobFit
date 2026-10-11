"""
Main v1 API router — aggregates all route groups.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes.applications import router as applications_router
from app.api.v1.routes.auth import router as auth_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.jobs import router as jobs_router
from app.api.v1.routes.jobs import search_runs_router
from app.api.v1.routes.matches import router as matches_router
from app.api.v1.routes.profile import router as profile_router
from app.api.v1.routes.resumes import router as resumes_router
from app.api.v1.routes.tailoring import router as tailored_documents_router
from app.api.v1.routes.tailoring import tailor_action_router
from app.api.v1.routes.tasks import router as tasks_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(resumes_router)
api_router.include_router(profile_router)
api_router.include_router(jobs_router)
api_router.include_router(search_runs_router)
api_router.include_router(matches_router)
api_router.include_router(tailored_documents_router)
api_router.include_router(tailor_action_router)
api_router.include_router(applications_router)
api_router.include_router(tasks_router)
