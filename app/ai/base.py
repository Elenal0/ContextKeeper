"""AI Provider abstract base class."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class AIProvider(ABC):
    """Abstract interface for all AI providers."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def default_model(self) -> str: ...

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> tuple[str, dict[str, int]]:
        """
        Call the AI model.
        Returns (response_text, {"prompt_tokens": int, "completion_tokens": int}).
        Raises: AIRateLimitError, AIUpstreamError, AITimeoutError
        """
        ...


class AIError(Exception):
    """Base AI error."""


class AIRateLimitError(AIError):
    """429 rate limit."""


class AIUpstreamError(AIError):
    """5xx upstream error."""


class AITimeoutError(AIError):
    """Timeout."""


class AIJSONError(AIError):
    """Could not parse or repair JSON from model."""

