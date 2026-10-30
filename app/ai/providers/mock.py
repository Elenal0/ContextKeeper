"""Mock AI provider for testing and development."""
from __future__ import annotations

import asyncio
import json
import os
from app.ai.base import AIProvider, AIRateLimitError, AITimeoutError, AIUpstreamError


_MOCK_RECAP = {
    "summary": "Team discussed project status, upcoming deadlines, and resource allocation.",
    "decisions": [
        "Use PostgreSQL for production database",
        "Ship MVP by end of quarter",
    ],
    "action_items": [
        {
            "title": "Finalize API design",
            "description": "Complete the REST API design document",
            "owner": None,
            "due_date": None,
            "priority": "high",
            "confidence": 0.85,
            "source_quote": "We need to finalize the API design",
        },
        {
            "title": "Set up CI/CD pipeline",
            "description": "Configure automated testing and deployment",
            "owner": None,
            "due_date": None,
            "priority": "medium",
            "confidence": 0.9,
            "source_quote": "CI/CD pipeline needs to be set up",
        },
    ],
    "open_questions": ["What is the budget for infrastructure?"],
    "risks": ["Timeline is tight", "Key person dependency on backend"],
}

_MOCK_CATCHUP = {
    "what_to_know": "The team decided to proceed with PostgreSQL and targeting MVP by end of quarter. Several action items were assigned.",
    "expected_of_you": ["Review and approve the API design document", "Provide feedback on CI/CD tooling"],
    "overdue_items": [],
}

_MOCK_KB_LINK = {
    "links": [
        {"kb_doc_id": 1, "relevance_score": 0.87, "reason": "Document covers related API patterns"},
        {"kb_doc_id": 2, "relevance_score": 0.65, "reason": "Contains relevant architecture decisions"},
    ]
}

_MOCK_NUDGE = {
    "message": "Hi! Just a friendly reminder that your action item is due soon. Please update the status when you get a chance. Thanks!"
}

_MOCK_REASSIGN = {
    "suggested_person_id": 1,
    "reason": "Best match based on skills and current workload",
    "confidence": 0.78,
}


class MockProvider(AIProvider):
    """Deterministic mock AI provider for development and testing."""

    @property
    def name(self) -> str:
        return "mock"

    @property
    def default_model(self) -> str:
        return "mock-v1"

    async def complete(
        self,
        prompt: str,
        *,
        temperature: float = 0.2,
        max_tokens: int = 4096,
        timeout: float = 60.0,
    ) -> tuple[str, dict[str, int]]:
        # Check env-based failure modes
        fail_mode = os.environ.get("MOCK_AI_FAIL", "").lower()
        if fail_mode == "timeout":
            raise AITimeoutError("Mock timeout triggered by MOCK_AI_FAIL=timeout")
        if fail_mode == "rate_limit":
            raise AIRateLimitError("Mock rate limit triggered by MOCK_AI_FAIL=rate_limit")
        if fail_mode == "upstream":
            raise AIUpstreamError("Mock upstream error triggered by MOCK_AI_FAIL=upstream")
        if fail_mode == "json_error":
            await asyncio.sleep(0.05)
            return "this is not valid json {{{", {"prompt_tokens": 10, "completion_tokens": 5}

        # Simulate network delay
        await asyncio.sleep(0.05)

        prompt_lower = prompt.lower()
        if "recap" in prompt_lower or "summary" in prompt_lower:
            response = _MOCK_RECAP
        elif "catch" in prompt_lower or "brief" in prompt_lower:
            response = _MOCK_CATCHUP
        elif "link" in prompt_lower or "relevant" in prompt_lower:
            response = _MOCK_KB_LINK
        elif "nudge" in prompt_lower or "message" in prompt_lower:
            response = _MOCK_NUDGE
        elif "reassign" in prompt_lower or "suggest" in prompt_lower:
            response = _MOCK_REASSIGN
        else:
            response = {"result": "Mock response", "status": "ok"}

        text = json.dumps(response)
        token_counts = {"prompt_tokens": len(prompt) // 4, "completion_tokens": len(text) // 4}
        return text, token_counts
