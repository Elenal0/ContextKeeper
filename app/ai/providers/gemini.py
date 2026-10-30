"""Gemini AI provider using google-generativeai SDK."""
from __future__ import annotations

import asyncio
from typing import Any

from app.ai.base import AIProvider, AIRateLimitError, AITimeoutError, AIUpstreamError


class GeminiProvider(AIProvider):
    """Google Gemini AI provider."""

    def __init__(self, api_key: str, model: str | None = None) -> None:
        self._api_key = api_key
        self._model_name = model or self.default_model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import google.generativeai as genai  # type: ignore[import]

                genai.configure(api_key=self._api_key)
                self._client = genai.GenerativeModel(self._model_name)
            except ImportError as exc:
                raise RuntimeError(
                    "google-generativeai package not installed. "
                    "Run: pip install google-generativeai"
                ) from exc
        return self._client

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def default_model(self) -> str:
        return "gemini-1.5-flash"

    async def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> tuple[str, dict[str, int]]:
        import google.generativeai as genai  # type: ignore[import]
        from google.api_core.exceptions import (  # type: ignore[import]
            ResourceExhausted,
            ServiceUnavailable,
            InternalServerError,
            DeadlineExceeded,
        )

        client = self._get_client()
        generation_config = genai.types.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        try:
            response = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: client.generate_content(
                        prompt,
                        generation_config=generation_config,
                    ),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise AITimeoutError(f"Gemini request timed out after {timeout}s") from exc
        except ResourceExhausted as exc:
            raise AIRateLimitError(f"Gemini rate limit: {exc}") from exc
        except (ServiceUnavailable, InternalServerError) as exc:
            raise AIUpstreamError(f"Gemini upstream error: {exc}") from exc
        except Exception as exc:
            # Catch other google API errors that might be 5xx
            msg = str(exc).lower()
            if "quota" in msg or "429" in msg:
                raise AIRateLimitError(f"Gemini rate limit: {exc}") from exc
            if any(code in msg for code in ("500", "502", "503", "504")):
                raise AIUpstreamError(f"Gemini upstream error: {exc}") from exc
            raise

        text = response.text or ""
        # Extract token usage if available
        usage = response.usage_metadata if hasattr(response, "usage_metadata") else None
        if usage:
            prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
            completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
        else:
            prompt_tokens = len(prompt) // 4
            completion_tokens = len(text) // 4

        return text, {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
