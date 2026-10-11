"""Unit tests for DocumentRenderer."""

from __future__ import annotations

from app.schemas.tailoring import TailoredExperienceEntry, TailoredResumeContent
from app.services.document_renderer import DocumentRenderer


def sample_content():
    return TailoredResumeContent(
        headline="Senior Backend Engineer",
        summary="Specialized in building low-latency REST APIs.",
        skills=["Python", "FastAPI", "PostgreSQL"],
        experience=[
            TailoredExperienceEntry(
                company="TechCorp",
                title="Software Engineer",
                start_date="2022-01",
                end_date="Present",
                location="San Francisco, CA",
                bullet_points=["Built microservices.", "Optimized SQL queries."],
            )
        ],
        education=[{"institution": "Stanford University", "degree": "B.S. Computer Science"}],
    )


def test_render_html():
    content = sample_content()
    contact = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1-555-0199",
        "location": "San Francisco, CA",
    }

    html_str = DocumentRenderer.render_html(content, contact)
    assert "Jane Doe" in html_str
    assert "Senior Backend Engineer" in html_str
    assert "Specialized in building low-latency" in html_str
    assert "TechCorp" in html_str
    assert "Stanford University" in html_str
    assert "FastAPI" in html_str


def test_render_pdf_or_fallback():
    content = sample_content()
    doc_bytes, content_type = DocumentRenderer.render_pdf(content, {"name": "Jane Doe"})

    assert isinstance(doc_bytes, bytes)
    assert len(doc_bytes) > 0
    assert "pdf" in content_type or "html" in content_type
