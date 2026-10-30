"""Recap AI task."""
from __future__ import annotations

from app.ai.fallback import (
    extract_action_items_heuristic,
    extract_decisions_heuristic,
    extract_summary_heuristic,
)
from app.ai.runner import run_ai
from app.schemas.ai import ExtractedActionItem, RecapDraft


async def generate_recap(
    meeting_title: str,
    participants_str: str,
    raw_input: str,
    db,
) -> RecapDraft:
    """Generate a meeting recap draft using AI or heuristic fallback."""
    result, ai_run = await run_ai(
        feature="recap",
        prompt_name="recap",
        prompt_version="v1",
        variables={
            "meeting_title": meeting_title,
            "participants": participants_str,
            "raw_input": raw_input,
        },
        db=db,
    )

    run_id = ai_run.id if ai_run else ""

    if result.get("_fallback"):
        items = extract_action_items_heuristic(raw_input)
        decisions = extract_decisions_heuristic(raw_input)
        summary = extract_summary_heuristic(raw_input)
        return RecapDraft(
            summary=summary,
            decisions=decisions,
            action_items=[ExtractedActionItem(**i) for i in items],
            open_questions=[],
            risks=[],
            ai_run_id=run_id,
            fallback_used=True,
            fallback_reason=result.get("_error", "AI unavailable"),
        )

    # Safely construct ExtractedActionItem from AI result
    raw_items = result.get("action_items", [])
    action_items: list[ExtractedActionItem] = []
    for item in raw_items:
        if isinstance(item, dict):
            try:
                action_items.append(ExtractedActionItem(**item))
            except Exception:
                pass  # skip malformed items

    return RecapDraft(
        summary=result.get("summary", ""),
        decisions=result.get("decisions", []),
        action_items=action_items,
        open_questions=result.get("open_questions", []),
        risks=result.get("risks", []),
        ai_run_id=run_id,
        fallback_used=False,
    )
