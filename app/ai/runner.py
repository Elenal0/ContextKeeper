"""
AI Runner — the central engine for all AI calls.

Features:
- Provider factory
- Prompt template loading
- Exponential backoff retry on 429/5xx
- JSON extraction (strip code fences)
- One JSON repair retry on parse failure
- AIRun DB record creation
- Structured logging
"""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from pathlib import Path
from string import Template
from typing import Any

import structlog
from sqlalchemy.orm import Session

from app.ai.base import AIError, AIJSONError, AIProvider, AIRateLimitError, AITimeoutError, AIUpstreamError
from app.config import settings
from app.db.models import AIRun, AIRunStatus
from app.logging_config import get_logger

logger = get_logger("ai.runner")

# Path to prompt templates
PROMPTS_DIR = Path(__file__).parent / "prompts"

_provider_instance: AIProvider | None = None


def get_provider() -> AIProvider:
    """Factory: return the configured AI provider (cached singleton)."""
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    provider_name = settings.effective_ai_provider()

    if provider_name == "gemini":
        from app.ai.providers.gemini import GeminiProvider
        _provider_instance = GeminiProvider()
    elif provider_name == "anthropic":
        from app.ai.providers.anthropic import AnthropicProvider
        _provider_instance = AnthropicProvider()
    elif provider_name == "openai":
        from app.ai.providers.openai import OpenAIProvider
        _provider_instance = OpenAIProvider()
    else:
        from app.ai.providers.mock import MockProvider
        _provider_instance = MockProvider()

    logger.info("ai_provider_selected", provider=provider_name)
    return _provider_instance


def reset_provider() -> None:
    """Reset the cached provider (useful for tests)."""
    global _provider_instance
    _provider_instance = None


def load_prompt(name: str, version: str) -> str:
    """
    Load a prompt template from app/ai/prompts/{name}_{version}.md.
    Returns the raw template string.
    """
    path = PROMPTS_DIR / f"{name}_{version}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt template not found: {path}")
    return path.read_text(encoding="utf-8")


def fill_prompt(template_str: str, variables: dict[str, str]) -> str:
    """Fill a prompt template using $var or ${var} substitution."""
    # Use safe_substitute so missing vars become empty strings gracefully
    t = Template(template_str)
    return t.safe_substitute(variables)


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` or ``` ... ``` wrappers from AI output."""
    # Try to find JSON block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text.strip()


def _parse_json(text: str) -> dict[str, Any]:
    """Parse JSON from AI response text."""
    cleaned = _strip_code_fences(text)
    return json.loads(cleaned)


async def run_ai(
    feature: str,
    prompt_name: str,
    prompt_version: str,
    variables: dict[str, str],
    db: Session,
    *,
    max_tokens: int = 4096,
) -> tuple[dict[str, Any], AIRun | None]:
    """
    Execute an AI call with full reliability stack.

    Returns:
        (result_dict, ai_run_record)
        On failure: ({"_fallback": True, "_error": str}, ai_run_record_or_None)
    """
    from app.logging_config import request_id_var

    run_id = str(uuid.uuid4())
    request_id = request_id_var.get()
    provider = get_provider()
    model = settings.AI_MODEL or provider.default_model
    start_time = time.monotonic()
    attempt_count = 0
    last_error: Exception | None = None
    status = AIRunStatus.error
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    error_type = ""

    # Load and fill prompt
    try:
        template_str = load_prompt(prompt_name, prompt_version)
        prompt = fill_prompt(template_str, variables)
    except FileNotFoundError as e:
        logger.error("prompt_not_found", feature=feature, prompt_name=prompt_name, error=str(e))
        return ({"_fallback": True, "_error": str(e)}, None)

    # Truncate if needed
    if len(prompt) > settings.AI_MAX_INPUT_CHARS:
        prompt = prompt[: settings.AI_MAX_INPUT_CHARS] + "\n[INPUT TRUNCATED]"
        logger.warning("ai_input_truncated", feature=feature, original_len=len(prompt))

    response_text = ""
    result: dict[str, Any] = {}

    # Retry loop
    for attempt in range(1, settings.AI_MAX_RETRIES + 1):
        attempt_count = attempt
        try:
            response_text, token_info = await asyncio.wait_for(
                provider.complete(
                    prompt,
                    temperature=settings.AI_TEMPERATURE,
                    max_tokens=max_tokens,
                    timeout=float(settings.AI_TIMEOUT_SECONDS),
                ),
                timeout=float(settings.AI_TIMEOUT_SECONDS) + 5,
            )
            prompt_tokens = token_info.get("prompt_tokens")
            completion_tokens = token_info.get("completion_tokens")

            # Try to parse JSON
            try:
                result = _parse_json(response_text)
                status = AIRunStatus.success if attempt == 1 else AIRunStatus.retry
                last_error = None
                break
            except (json.JSONDecodeError, ValueError) as json_err:
                # One JSON repair attempt
                logger.warning("ai_json_parse_failed", feature=feature, attempt=attempt, error=str(json_err))
                repair_prompt = (
                    f"The following JSON is malformed. Fix it and return ONLY valid JSON, no other text.\n"
                    f"Error: {json_err}\n"
                    f"Malformed JSON:\n{response_text[:2000]}"
                )
                try:
                    repair_text, repair_tokens = await asyncio.wait_for(
                        provider.complete(
                            repair_prompt,
                            temperature=0.0,
                            max_tokens=max_tokens,
                            timeout=float(settings.AI_TIMEOUT_SECONDS),
                        ),
                        timeout=float(settings.AI_TIMEOUT_SECONDS) + 5,
                    )
                    result = _parse_json(repair_text)
                    status = AIRunStatus.retry
                    last_error = None
                    break
                except Exception as repair_err:
                    last_error = repair_err
                    error_type = type(repair_err).__name__

        except AIRateLimitError as e:
            last_error = e
            error_type = "AIRateLimitError"
            status = AIRunStatus.retry
            wait_secs = 2 ** attempt
            logger.warning("ai_rate_limit", feature=feature, attempt=attempt, wait_secs=wait_secs)
            await asyncio.sleep(wait_secs)

        except (AIUpstreamError, AITimeoutError) as e:
            last_error = e
            error_type = type(e).__name__
            status = AIRunStatus.retry
            wait_secs = 2 ** attempt
            logger.warning("ai_upstream_error", feature=feature, attempt=attempt, error=str(e), wait_secs=wait_secs)
            await asyncio.sleep(wait_secs)

        except Exception as e:
            last_error = e
            error_type = type(e).__name__
            logger.error("ai_unexpected_error", feature=feature, attempt=attempt, error=str(e))
            break

    latency_ms = int((time.monotonic() - start_time) * 1000)

    # If we still have an error, go to fallback
    if last_error is not None or not result:
        status = AIRunStatus.fallback
        error_type = error_type or type(last_error).__name__ if last_error else "unknown"
        logger.warning(
            "ai_fallback",
            feature=feature,
            error_type=error_type,
            latency_ms=latency_ms,
            attempts=attempt_count,
        )
        result = {"_fallback": True, "_error": str(last_error) if last_error else "No result"}

    # Log the AI call
    logger.info(
        "ai_call_complete",
        feature=feature,
        provider=provider.name,
        model=model,
        prompt_version=f"{prompt_name}_{prompt_version}",
        latency_ms=latency_ms,
        status=status,
        attempt_count=attempt_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        error_type=error_type,
    )

    # Save AIRun to DB
    ai_run = AIRun(
        id=run_id,
        feature=feature,
        provider=provider.name,
        model=model,
        prompt_version=f"{prompt_name}_{prompt_version}",
        latency_ms=latency_ms,
        status=status,
        attempt_count=attempt_count,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        error_type=error_type,
        request_id=request_id,
    )
    try:
        db.add(ai_run)
        db.commit()
        db.refresh(ai_run)
    except Exception as db_err:
        logger.error("ai_run_save_failed", error=str(db_err))
        db.rollback()

    result["_ai_run_id"] = run_id
    return (result, ai_run)
