"""
LLM providers package and factory.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.providers.llm.base import LLMAdapter
from app.providers.llm.gemini import GeminiAdapter
from app.providers.llm.mock_llm import MockLLMAdapter


def get_llm_adapter() -> LLMAdapter:
    """Return configured LLM adapter instance."""
    settings = get_settings()

    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return GeminiAdapter()

    # Fallback for testing / dev without keys
    return MockLLMAdapter()


__all__ = [
    "GeminiAdapter",
    "LLMAdapter",
    "MockLLMAdapter",
    "get_llm_adapter",
]
