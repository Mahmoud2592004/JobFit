"""
Mock LLM Adapter for unit testing and CI test runs.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from app.providers.llm.base import LLMAdapter

T = TypeVar("T", bound=BaseModel)


class MockLLMAdapter(LLMAdapter):
    """Mock LLM adapter returning preconfigured or synthetic structured models."""

    def __init__(self, canned_response: BaseModel | dict[str, Any] | None = None) -> None:
        self.canned_response = canned_response

    async def extract_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
    ) -> T:
        _ = (prompt, system_instruction)
        if self.canned_response is not None:
            if isinstance(self.canned_response, response_model):
                return self.canned_response
            if isinstance(self.canned_response, dict):
                return response_model.model_validate(self.canned_response)

        # Default fallback: construct default instance of response_model
        return response_model.model_validate({})
