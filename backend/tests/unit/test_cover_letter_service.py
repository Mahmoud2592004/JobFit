"""Unit tests for CoverLetterService."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
import pytest

from app.providers.llm.mock_llm import MockLLMAdapter
from app.schemas.tailoring import CoverLetterContent
from app.services.cover_letter_service import CoverLetterService, _COVER_LETTER_SYSTEM_PROMPT


def make_sample_profile():
    return {
        "name": "Alex Mercer",
        "skills": ["Python", "FastAPI", "PostgreSQL", "Docker", "Distributed Systems"],
        "employment_history": [
            {
                "company": "CloudScale Inc",
                "title": "Senior Backend Engineer",
                "start_date": "2021-03",
                "end_date": "Present",
                "achievements": [
                    "Engineered distributed payment processing gateway processing 25k TPS.",
                    "Reduced p99 API latency by 42% via connection pooling and async architecture.",
                ],
            }
        ],
        "projects": [
            {
                "name": "EventStreamer",
                "description": "High-throughput real-time Kafka event pipeline",
                "technologies": ["Python", "Kafka", "Redis"],
                "achievements": ["Zero message loss under 100k msg/sec load tests"],
            }
        ],
    }


def make_sample_job():
    return {
        "title": "Staff Platform Engineer",
        "employer": "Stripe",
        "description": "Design mission-critical infrastructure for global financial transactions.",
        "requirements": ["Distributed systems", "High-throughput APIs", "Python", "Observability"],
    }


@pytest.mark.asyncio
async def test_cover_letter_service_prompt_requirements():
    """Verify that CoverLetterService prompt contains search-first, personalization, and natural voice directives."""
    job = make_sample_job()
    profile = make_sample_profile()

    canned = CoverLetterContent(
        recipient="Stripe Engineering Team",
        company_name="Stripe",
        salutation="Dear Stripe Engineering Team,",
        opening_hook="Stripe's work scaling reliable financial plumbing has always resonated with how I build systems.",
        body_paragraphs=[
            "At CloudScale Inc, I architected our distributed payment gateway processing 25k TPS with zero transaction loss.",
            "I'm eager to bring this rigor to Stripe's platform engineering challenges.",
        ],
        call_to_action="I'd love the opportunity to discuss how my distributed systems experience can support Stripe's team.",
        signoff="Best regards,",
        candidate_name="Alex Mercer",
        full_text="Dear Stripe Engineering Team,\n\nStripe's work scaling reliable financial plumbing has always resonated with how I build systems.\n\nAt CloudScale Inc, I architected our distributed payment gateway processing 25k TPS with zero transaction loss.\n\nI'm eager to bring this rigor to Stripe's platform engineering challenges.\n\nI'd love the opportunity to discuss how my distributed systems experience can support Stripe's team.\n\nBest regards,\nAlex Mercer",
        company_research_summary="Global financial infrastructure leader focused on developer ergonomics and reliability.",
    )

    mock_llm = MockLLMAdapter(canned_response=canned)
    service = CoverLetterService(llm=mock_llm)

    # Disable network calls in test
    with patch.object(service, "_fetch_company_search_context", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = "- Stripe builds economic infrastructure for the internet."
        result = await service.generate_cover_letter(
            job=job,
            candidate_profile=profile,
            target_role_notes="Focus on low-latency systems",
            tone="natural_conversational",
        )

    # Check that extract_structured was called
    assert mock_llm.last_prompt is not None
    prompt = mock_llm.last_prompt

    # 1. Verify prompt contains search first directive
    assert "SEARCH & RESEARCH FIRST" in prompt or "search and research first" in prompt.lower()
    assert "Stripe" in prompt

    # 2. Verify prompt contains personalized and natural as much as possible instructions
    assert "DEEPLY PERSONALIZED AND NATURAL AS MUCH AS POSSIBLE" in prompt
    assert "natural_conversational" in prompt
    assert "Ban all robotic clichés" in prompt or "robotic" in prompt

    # 3. Verify system prompt includes search first and natural voice directives
    assert "SEARCH & RESEARCH THE COMPANY FIRST" in _COVER_LETTER_SYSTEM_PROMPT
    assert "DEEPLY PERSONALIZED & NATURAL HUMAN VOICE" in _COVER_LETTER_SYSTEM_PROMPT
    assert "ZERO HALLUCINATION" in _COVER_LETTER_SYSTEM_PROMPT

    # 4. Verify result object
    assert result.company_name == "Stripe"
    assert result.candidate_name == "Alex Mercer"
    assert "Stripe" in result.salutation
    assert len(result.body_paragraphs) == 2
    assert "Alex Mercer" in result.full_text


@pytest.mark.asyncio
async def test_cover_letter_service_auto_assembles_full_text():
    """Verify that full_text is automatically assembled if missing or too short."""
    job = make_sample_job()
    profile = make_sample_profile()

    canned = CoverLetterContent(
        recipient="Hiring Team",
        company_name="Stripe",
        salutation="Dear Stripe Engineering Team,",
        opening_hook="I have long admired Stripe's commitment to developer ergonomics.",
        body_paragraphs=["Here is my experience at CloudScale."],
        call_to_action="Let's talk soon.",
        signoff="Warmly,",
        candidate_name="",
        full_text="",  # Intentionally empty to test auto-assembly
    )

    mock_llm = MockLLMAdapter(canned_response=canned)
    service = CoverLetterService(llm=mock_llm)

    with patch.object(service, "_fetch_company_search_context", new_callable=AsyncMock) as mock_search:
        mock_search.return_value = ""
        result = await service.generate_cover_letter(
            job=job,
            candidate_profile=profile,
        )

    assert result.candidate_name == "Alex Mercer"
    assert result.company_name == "Stripe"
    assert "Dear Stripe Engineering Team," in result.full_text
    assert "Here is my experience at CloudScale." in result.full_text
    assert "Warmly," in result.full_text
    assert "Alex Mercer" in result.full_text
