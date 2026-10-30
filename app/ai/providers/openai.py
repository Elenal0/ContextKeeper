"""OpenAI AI provider using openai SDK."""
from __future__ import annotations

import asyncio
from typing import Any

from app.ai.base import AIProvider, AIRateLimitError, AITimeoutError, AIUpstreamError


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider."""

    def __init__(self, api_key: str, model: str | None = None, base_url: str | None = None) -> None:
        self._api_key = api_key
        self._model_name = model or self.default_model
        self._base_url = base_url
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import openai  # type: ignore[import]

                kwargs: dict[str, Any] = {"api_key": self._api_key}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = openai.AsyncOpenAI(**kwargs)
            except ImportError as exc:
                raise RuntimeError(
                    "openai package not installed. Run: pip install openai"
                ) from exc
        return self._client

    @property
    def name(self) -> str:
        return "openai"

    @property
    def default_model(self) -> str:
        return "gpt-4o-mini"

    async def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> tuple[str, dict[str, int]]:
        try:
            import openai  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("openai package not installed") from exc

        client = self._get_client()

        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self._model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                    max_tokens=max_tokens,
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise AITimeoutError(f"OpenAI request timed out after {timeout}s") from exc
        except openai.RateLimitError as exc:
            raise AIRateLimitError(f"OpenAI rate limit: {exc}") from exc
        except openai.APIStatusError as exc:
            status = exc.status_code
            if status == 429:
                raise AIRateLimitError(f"OpenAI rate limit: {exc}") from exc
            if status >= 500:
                raise AIUpstreamError(f"OpenAI upstream error ({status}): {exc}") from exc
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "timeout" in msg:
                raise AITimeoutError(f"OpenAI timeout: {exc}") from exc
            raise

        text = ""
        choice = response.choices[0] if response.choices else None
        if choice and choice.message and choice.message.content:
            text = choice.message.content

        usage = response.usage
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0

        return text, {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
