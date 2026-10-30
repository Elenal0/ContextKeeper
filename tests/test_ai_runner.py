"""Tests for AI Runner, fallback heuristics, and failure handling."""
import os
import pytest

from app.ai.fallback import (
    extract_action_items_heuristic,
    extract_decisions_heuristic,
    extract_summary_heuristic,
)
from app.ai.runner import get_provider, reset_provider, run_ai
from app.db.models import AIRunStatus


@pytest.mark.asyncio
async def test_ai_runner_mock_success(db_session):
    reset_provider()
    res, ai_run = await run_ai(
        feature="recap",
        prompt_name="recap",
        prompt_version="v1",
        variables={
            "meeting_title": "Sprint 22 Sync",
            "participants": "Sarah, Alex",
            "raw_input": "Sarah: Alex please migrate staging db. Alex: Sure, by Wednesday.",
        },
        db=db_session,
    )
    assert not res.get("_fallback")
    assert "summary" in res
    assert ai_run is not None
    assert ai_run.status == AIRunStatus.success
    assert ai_run.latency_ms >= 0


@pytest.mark.asyncio
async def test_ai_runner_timeout_falls_back_gracefully(db_session):
    reset_provider()
    os.environ["MOCK_AI_FAIL"] = "timeout"
    try:
        res, ai_run = await run_ai(
            feature="recap",
            prompt_name="recap",
            prompt_version="v1",
            variables={
                "meeting_title": "Timeout Meeting",
                "participants": "Sarah",
                "raw_input": "TODO: Fix database lock by Friday",
            },
            db=db_session,
        )
        assert res.get("_fallback") is True
        assert ai_run.status == AIRunStatus.fallback
    finally:
        os.environ.pop("MOCK_AI_FAIL", None)
        reset_provider()


def test_heuristic_fallback_extraction():
    raw_text = """
    We held our sprint sync today.
    DECIDED: Switch all logging to JSON format.
    TODO: @sarah to configure structlog by Friday
    - Review PR #104 by tomorrow
    - Deploy staging database
    """
    items = extract_action_items_heuristic(raw_text)
    decisions = extract_decisions_heuristic(raw_text)
    summary = extract_summary_heuristic(raw_text)

    assert len(items) >= 2
    assert any("structlog" in i["title"].lower() for i in items)
    assert len(decisions) >= 1
    assert "JSON format" in decisions[0]
    assert len(summary) > 0

