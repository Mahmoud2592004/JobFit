"""
Strict Claim Verification Engine (v1.0.0).
Prevents hallucinations by cross-checking AI-generated resume content
against verified candidate profile facts and evidence.
"""

from __future__ import annotations

import re
from typing import Any

import structlog

from app.schemas.tailoring import FlaggedClaim, TailoredResumeContent

log = structlog.get_logger(__name__)

VALIDATION_VERSION = "v1.0.0"


def _normalize_name(name: str) -> str:
    """Normalize string for fuzzy comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


class ClaimVerifier:
    """Cross-references tailored resume content against source candidate facts."""

    @staticmethod
    def verify_tailored_content(
        tailored: TailoredResumeContent,
        verified_profile: dict[str, Any],
    ) -> tuple[bool, list[FlaggedClaim]]:
        """
        Verify that all claims, skills, and companies in the tailored resume
        are grounded in the candidate's verified profile.
        Returns (validation_passed, flagged_claims).
        """
        flagged: list[FlaggedClaim] = []

        # 1. Verified skills set
        verified_skills_raw = verified_profile.get("skills", [])
        verified_skills_set = {_normalize_name(str(s)) for s in verified_skills_raw}

        # 2. Verified companies and titles
        emp_history = verified_profile.get("employment_history", [])
        verified_companies = {_normalize_name(str(e.get("company", ""))) for e in emp_history}
        verified_titles = {_normalize_name(str(e.get("title", ""))) for e in emp_history}

        # ── Check 1: Skills ground-truth ──────────────────────────────────────
        for skill in tailored.skills:
            norm_skill = _normalize_name(skill)
            if norm_skill not in verified_skills_set:
                flagged.append(
                    FlaggedClaim(
                        claim=skill,
                        field_path=f"skills.{skill}",
                        reason=(
                            f"Skill '{skill}' was not found in candidate's verified profile. "
                            "Do not add skills without candidate confirmation."
                        ),
                        severity="error",
                    )
                )

        # ── Check 2: Companies ground-truth ───────────────────────────────────
        for idx, entry in enumerate(tailored.experience):
            norm_company = _normalize_name(entry.company)
            if norm_company not in verified_companies:
                flagged.append(
                    FlaggedClaim(
                        claim=entry.company,
                        field_path=f"experience[{idx}].company",
                        reason=(
                            f"Company '{entry.company}' does not match any employer "
                            "in candidate employment history."
                        ),
                        severity="error",
                    )
                )

            # Check title reasonableness
            norm_title = _normalize_name(entry.title)
            if norm_title not in verified_titles:
                flagged.append(
                    FlaggedClaim(
                        claim=entry.title,
                        field_path=f"experience[{idx}].title",
                        reason=(
                            f"Job title '{entry.title}' differs from candidate's documented title."
                        ),
                        severity="warning",
                    )
                )

        # Validation passes only if zero errors or warnings exist
        has_errors = any(f.severity == "error" for f in flagged)
        validation_passed = len(flagged) == 0 and not has_errors

        log.info(
            "claim_verification_completed",
            flagged_count=len(flagged),
            passed=validation_passed,
        )

        return validation_passed, flagged
