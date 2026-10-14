"""
LLM Provider protocol interface.

Decouples the business logic from specific AI models.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMAdapter(Protocol):
    """Protocol for provider-independent structured LLM extraction."""

    async def extract_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float | None = None,
    ) -> T:
        """
        Send a prompt to the LLM and return a strictly validated Pydantic model.

        Raises:
            ProviderError: if LLM call fails, rate-limits, or fails schema validation.
        """
        ...
