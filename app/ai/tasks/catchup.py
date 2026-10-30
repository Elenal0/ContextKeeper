"""Catch-up brief AI task."""
from __future__ import annotations

from app.ai.runner import run_ai
from app.schemas.ai import CatchupBrief


async def generate_catchup(
    person_name: str,
    person_role: str,
    meeting_title: str,
    meeting_id: int,
    summary: str,
    decisions: str,
    action_items_str: str,
    owned_items_str: str,
    db,
) -> CatchupBrief:
    """Generate a personalised catch-up brief for a person missing a meeting."""
    result, ai_run = await run_ai(
        feature="catchup",
        prompt_name="catchup",
        prompt_version="v1",
        variables={
            "person_name": person_name,
            "person_role": person_role,
            "meeting_title": meeting_title,
            "summary": summary,
            "decisions": decisions,
            "action_items": action_items_str,
            "owned_items": owned_items_str,
        },
        db=db,
    )

    run_id = ai_run.id if ai_run else ""
    fallback = result.get("_fallback", False)

    if fallback:
        return CatchupBrief(
            person_name=person_name,
            meeting_title=meeting_title,
            what_to_know=summary or "No summary available.",
            expected_of_you=[],
            overdue_items=[],
            source_meeting_id=meeting_id,
            ai_generated=True,
            ai_run_id=run_id,
            fallback_used=True,
        )

    return CatchupBrief(
        person_name=person_name,
        meeting_title=meeting_title,
        what_to_know=result.get("what_to_know", summary),
        expected_of_you=result.get("expected_of_you", []),
        overdue_items=result.get("overdue_items", []),
        source_meeting_id=meeting_id,
        ai_generated=True,
        ai_run_id=run_id,
        fallback_used=False,
    )
