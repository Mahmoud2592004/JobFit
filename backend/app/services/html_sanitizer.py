"""
Lightweight, resilient HTML sanitization and plain-text converter for job descriptions.
"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._pieces: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self._pieces.append(data)

    def handle_starttag(self, tag: str, _attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "h6"}:
            self._pieces.append("\n")
        elif tag == "li":
            self._pieces.append("\n• ")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li"}:
            self._pieces.append("\n")

    def get_text(self) -> str:
        raw = "".join(self._pieces)
        unescaped = html.unescape(raw)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in unescaped.splitlines()]
        cleaned = "\n".join(lines)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned.strip()


def strip_html_to_text(html_content: str | None) -> str:
    """
    Safely extract plain text from an HTML snippet or return sanitized text if already plain.
    """
    if not html_content:
        return ""
    if "<" not in html_content and ">" not in html_content:
        return html_content.strip()

    parser = _HTMLTextExtractor()
    try:
        parser.feed(html_content)
        parser.close()
        return parser.get_text()
    except Exception:
        # Fallback to simple regex strip
        clean = re.sub(r"<[^>]+>", " ", html_content)
        return html.unescape(clean).strip()
