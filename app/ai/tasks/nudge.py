"""Nudge AI task."""
from __future__ import annotations

from datetime import datetime, timezone

from app.ai.runner import run_ai
from app.schemas.ai import NudgeResponse


async def generate_nudge(
    item_id: int,
    item_title: str,
    owner_name: str,
    due_date: datetime | None,
    tone: str,
    db,
) -> NudgeResponse:
    """Generate a nudge message for an action item owner."""
    now = datetime.now(timezone.utc)
    if due_date:
        # Make due_date timezone-aware if needed
        if due_date.tzinfo is None:
            due_date_aware = due_date.replace(tzinfo=timezone.utc)
        else:
            due_date_aware = due_date
        overdue_days = max(0, (now - due_date_aware).days)
        due_date_str = due_date.strftime("%Y-%m-%d")
    else:
        overdue_days = 0
        due_date_str = "not set"

    result, ai_run = await run_ai(
        feature="nudge",
        prompt_name="nudge",
        prompt_version="v1",
        variables={
            "item_title": item_title,
            "owner_name": owner_name,
            "due_date": due_date_str,
            "tone": tone,
            "overdue_days": overdue_days,
        },
        db=db,
    )

    run_id = ai_run.id if ai_run else ""
    fallback = result.get("_fallback", False)

    if fallback:
        msg = (
            f"Hi {owner_name}, this is a reminder about: {item_title}."
            + (f" It is {overdue_days} day(s) overdue." if overdue_days > 0 else f" Due: {due_date_str}.")
            + " Please update the status when you can. Thanks!"
        )
        return NudgeResponse(
            item_id=item_id,
            message=msg,
            tone=tone,
            ai_generated=True,
            ai_run_id=run_id,
            fallback_used=True,
        )

    return NudgeResponse(
        item_id=item_id,
        message=result.get("message", ""),
        tone=tone,
        ai_generated=True,
        ai_run_id=run_id,
        fallback_used=False,
    )
