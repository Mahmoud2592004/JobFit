"""Tests for domain models."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from app.domain.models import (
    ProfileEvidence,
    ProfileVersion,
    ResumeVersion,
    SearchPreferences,
    Task,
    UserProfile,
)


def test_user_profile_model():
    uid = uuid4()
    profile = UserProfile(
        id=uuid4(),
        user_id=uid,
        display_name="Jane Doe",
        contact_email="jane@example.com",
        contact_phone="+123456789",
        location="Remote",
        linkedin_url="https://linkedin.com/in/janedoe",
        portfolio_url="https://janedoe.dev",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    assert profile.display_name == "Jane Doe"
    assert profile.user_id == uid


def test_resume_version_model():
    uid = uuid4()
    res = ResumeVersion(
        id=uuid4(),
        user_id=uid,
        version_number=1,
        source_type="pdf",
        storage_path=f"{uid}/resume.pdf",
        raw_text="Extracted text",
        file_size_bytes=1024,
        original_filename="resume.pdf",
        extraction_status="completed",
        created_at=datetime.now(timezone.utc),
    )
    assert res.version_number == 1
    assert res.extraction_status == "completed"


def test_profile_version_model():
    uid = uuid4()
    pv = ProfileVersion(
        id=uuid4(),
        user_id=uid,
        version_number=1,
        is_confirmed=True,
        content={"summary": "Experienced engineer"},
        seniority_level="mid",
        target_roles=["ML Engineer"],
        skills=["Python", "PyTorch"],
        years_experience=Decimal("3.5"),
        created_at=datetime.now(timezone.utc),
    )
    assert pv.is_confirmed is True
    assert pv.skills == ["Python", "PyTorch"]
    assert pv.years_experience == Decimal("3.5")


def test_profile_evidence_model():
    uid = uuid4()
    pvid = uuid4()
    ev = ProfileEvidence(
        id=uuid4(),
        profile_version_id=pvid,
        user_id=uid,
        claim_type="skill",
        claim_value="Python",
        confidence="explicit",
        source_text="Proficient in Python",
        source_location="Page 1",
        created_at=datetime.now(timezone.utc),
    )
    assert ev.claim_value == "Python"
    assert ev.confidence == "explicit"


def test_search_preferences_model():
    uid = uuid4()
    sp = SearchPreferences(
        id=uuid4(),
        user_id=uid,
        target_roles=["Backend Engineer"],
        locations=["Remote", "Berlin"],
        work_arrangements=["remote"],
        seniority_levels=["mid", "senior"],
        min_salary=100000,
        salary_currency="USD",
        excluded_employers=["SpamCorp"],
        keywords_include=["FastAPI"],
        keywords_exclude=["Legacy"],
        updated_at=datetime.now(timezone.utc),
    )
    assert sp.min_salary == 100000
    assert sp.target_roles == ["Backend Engineer"]


def test_task_model():
    uid = uuid4()
    task = Task(
        id=uuid4(),
        user_id=uid,
        task_type="search_run",
        payload={"query": "python"},
        status="running",
        retry_count=1,
        max_retries=3,
        created_at=datetime.now(timezone.utc),
    )
    assert task.status == "running"
    assert task.retry_count == 1
