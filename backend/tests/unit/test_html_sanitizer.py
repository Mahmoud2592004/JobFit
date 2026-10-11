"""Unit tests for HTML sanitizer utility."""

from __future__ import annotations

from app.services.html_sanitizer import strip_html_to_text


def test_strip_html_none_or_empty():
    assert strip_html_to_text(None) == ""
    assert strip_html_to_text("") == ""
    assert strip_html_to_text("   ") == ""


def test_strip_html_plain_text():
    text = "Simple plain text without tags"
    assert strip_html_to_text(text) == text


def test_strip_html_with_tags_and_entities():
    html_doc = """
    <h1>Software Engineer</h1>
    <p>We are hiring a <strong>Python</strong> &amp; <em>FastAPI</em> developer.</p>
    <ul>
        <li>3+ years experience</li>
        <li>Remote work</li>
    </ul>
    """
    cleaned = strip_html_to_text(html_doc)
    assert "Software Engineer" in cleaned
    assert "Python & FastAPI" in cleaned
    assert "• 3+ years experience" in cleaned
    assert "<h1>" not in cleaned
    assert "<li>" not in cleaned
