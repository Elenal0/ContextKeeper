"""Anthropic AI provider using anthropic SDK."""
from __future__ import annotations

import asyncio
from typing import Any

from app.ai.base import AIProvider, AIRateLimitError, AITimeoutError, AIUpstreamError


class AnthropicProvider(AIProvider):
    """Anthropic Claude AI provider."""

    def __init__(self, api_key: str, model: str | None = None) -> None:
        self._api_key = api_key
        self._model_name = model or self.default_model
        self._client: Any = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic  # type: ignore[import]

                self._client = anthropic.AsyncAnthropic(api_key=self._api_key)
            except ImportError as exc:
                raise RuntimeError(
                    "anthropic package not installed. Run: pip install anthropic"
                ) from exc
        return self._client

    @property
    def name(self) -> str:
        return "anthropic"

    @property
    def default_model(self) -> str:
        return "claude-3-haiku-20240307"

    async def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> tuple[str, dict[str, int]]:
        try:
            import anthropic  # type: ignore[import]
        except ImportError as exc:
            raise RuntimeError("anthropic package not installed") from exc

        client = self._get_client()

        try:
            response = await asyncio.wait_for(
                client.messages.create(
                    model=self._model_name,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}],
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError as exc:
            raise AITimeoutError(f"Anthropic request timed out after {timeout}s") from exc
        except anthropic.RateLimitError as exc:
            raise AIRateLimitError(f"Anthropic rate limit: {exc}") from exc
        except anthropic.APIStatusError as exc:
            status = exc.status_code
            if status == 429:
                raise AIRateLimitError(f"Anthropic rate limit: {exc}") from exc
            if status >= 500:
                raise AIUpstreamError(f"Anthropic upstream error ({status}): {exc}") from exc
            raise
        except Exception as exc:
            msg = str(exc).lower()
            if "timeout" in msg:
                raise AITimeoutError(f"Anthropic timeout: {exc}") from exc
            raise

        text = ""
        if response.content:
            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text

        usage = response.usage
        prompt_tokens = getattr(usage, "input_tokens", 0) or 0
        completion_tokens = getattr(usage, "output_tokens", 0) or 0

        return text, {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens}
