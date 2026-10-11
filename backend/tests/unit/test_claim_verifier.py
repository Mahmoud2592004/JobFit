"""Unit tests for ClaimVerifier."""

from __future__ import annotations

from app.schemas.tailoring import TailoredExperienceEntry, TailoredResumeContent
from app.services.claim_verifier import ClaimVerifier


def make_profile():
    return {
        "skills": ["Python", "FastAPI", "Docker", "PostgreSQL"],
        "employment_history": [
            {
                "company": "Apex AI",
                "title": "Backend Engineer",
                "start_date": "2021-01",
                "end_date": "Present",
            }
        ],
    }


def test_claim_verification_all_grounded():
    profile = make_profile()
    tailored = TailoredResumeContent(
        headline="Backend Engineer",
        summary="Experienced Python engineer specializing in FastAPI and Docker.",
        skills=["Python", "FastAPI", "Docker"],
        experience=[
            TailoredExperienceEntry(
                company="Apex AI",
                title="Backend Engineer",
                bullet_points=["Built microservices with FastAPI and Docker."],
            )
        ],
    )

    passed, flagged = ClaimVerifier.verify_tailored_content(tailored, profile)
    assert passed is True
    assert len(flagged) == 0


def test_claim_verification_invented_skill():
    profile = make_profile()
    tailored = TailoredResumeContent(
        headline="Backend Engineer",
        summary="Python expert.",
        skills=["Python", "Rust", "Kubernetes"],  # Rust and Kubernetes are not in profile
        experience=[
            TailoredExperienceEntry(
                company="Apex AI",
                title="Backend Engineer",
                bullet_points=["Wrote Python services."],
            )
        ],
    )

    passed, flagged = ClaimVerifier.verify_tailored_content(tailored, profile)
    assert passed is False
    assert len(flagged) == 2
    assert all(f.severity == "error" for f in flagged)
    claims = {f.claim for f in flagged}
    assert "Rust" in claims
    assert "Kubernetes" in claims


def test_claim_verification_invented_company():
    profile = make_profile()
    tailored = TailoredResumeContent(
        headline="Backend Engineer",
        summary="Python expert.",
        skills=["Python"],
        experience=[
            TailoredExperienceEntry(
                company="Google Inc",  # Not in candidate profile!
                title="Software Engineer",
                bullet_points=["Designed search engine."],
            )
        ],
    )

    passed, flagged = ClaimVerifier.verify_tailored_content(tailored, profile)
    assert passed is False
    assert any(f.field_path == "experience[0].company" and f.severity == "error" for f in flagged)
