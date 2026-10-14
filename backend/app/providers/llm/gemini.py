"""
Gemini LLM Adapter using Google Generative AI SDK.

Supports structured JSON outputs validated against Pydantic models.
Implements retry logic with exponential backoff on transient errors.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, TypeVar

import structlog
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.exceptions import LLMError, ProviderError
from app.providers.llm.base import LLMAdapter

log = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class GeminiAdapter(LLMAdapter):
    """LLM Adapter for Google Gemini models."""

    def __init__(self, api_key: str | None = None, model_name: str | None = None) -> None:
        settings = get_settings()
        self.api_key = api_key or settings.gemini_api_key
        self.model_name = model_name or settings.llm_model

        if not self.api_key:
            raise ProviderError(
                provider="Gemini",
                detail="GEMINI_API_KEY is not configured.",
            )

        import google.generativeai as genai  # type: ignore[import-untyped]

        genai.configure(api_key=self.api_key)  # type: ignore[reportPrivateImportUsage]
        self._genai: Any = genai

    async def extract_structured(
        self,
        prompt: str,
        response_model: type[T],
        system_instruction: str | None = None,
        temperature: float | None = None,
    ) -> T:
        """Generate structured data adhering to response_model."""
        max_retries = 3
        delay = 1.0

        schema_json = json.dumps(response_model.model_json_schema())
        schema_desc = (
            f"You must output ONLY a valid JSON object strictly conforming to this JSON Schema:\n"
            f"{schema_json}"
        )
        instruction = (
            f"{system_instruction}\n\n{schema_desc}" if system_instruction else schema_desc
        )

        eff_temperature = 0.1 if temperature is None else temperature

        for attempt in range(1, max_retries + 1):
            try:
                model = self._genai.GenerativeModel(
                    model_name=self.model_name,
                    system_instruction=instruction,
                    generation_config={
                        "response_mime_type": "application/json",
                        "temperature": eff_temperature,
                    },
                )

                response = await model.generate_content_async(prompt)
                raw_text = response.text or ""

                # Strip possible markdown code blocks if returned
                cleaned_json = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.MULTILINE)
                cleaned_json = re.sub(r"\s*```$", "", cleaned_json, flags=re.MULTILINE)

                return response_model.model_validate_json(cleaned_json)

            except Exception as exc:
                err_msg = str(exc)
                is_transient = (
                    "429" in err_msg or "503" in err_msg or "ResourceExhausted" in err_msg
                )

                if is_transient and attempt < max_retries:
                    log.warning(
                        "gemini_transient_error_retry",
                        attempt=attempt,
                        delay=delay,
                        error=err_msg,
                    )
                    await asyncio.sleep(delay)
                    delay *= 2
                    continue

                log.error("gemini_call_failed", attempt=attempt, error=err_msg)
                raise LLMError(detail=f"Gemini generation error: {err_msg}") from exc

        raise LLMError(detail="Max retries exceeded for Gemini AI service.")
