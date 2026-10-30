"""Reassignment suggestion AI task."""
from __future__ import annotations

import json
from typing import Any

from app.ai.runner import run_ai
from app.schemas.ai import ReassignSuggestion


async def suggest_reassignment(
    item_title: str,
    item_description: str,
    candidates: list[Any],  # list of Person ORM objects
    db,
) -> ReassignSuggestion:
    """Suggest the best candidate for reassignment of an action item."""
    if not candidates:
        raise ValueError("No candidates provided for reassignment suggestion")

    # Serialize candidates for the prompt
    candidates_data = [
        {
            "id": p.id,
            "name": p.name,
            "role": p.role,
            "availability": p.availability if isinstance(p.availability, str) else p.availability.value,
        }
        for p in candidates
    ]
    candidates_str = json.dumps(candidates_data, indent=2)

    result, ai_run = await run_ai(
        feature="reassign",
        prompt_name="reassign",
        prompt_version="v1",
        variables={
            "item_title": item_title,
            "item_description": item_description or "",
            "candidates": candidates_str,
        },
        db=db,
    )

    run_id = ai_run.id if ai_run else ""
    fallback = result.get("_fallback", False)

    if fallback:
        # Pick first available candidate as fallback
        first = candidates[0]
        return ReassignSuggestion(
            suggested_person_id=first.id,
            suggested_person_name=first.name,
            reason="Fallback: first available candidate (AI unavailable)",
            confidence=0.3,
            ai_run_id=run_id,
            fallback_used=True,
        )

    suggested_id = result.get("suggested_person_id")
    # Find the matching person name
    person_name = ""
    for p in candidates:
        if p.id == suggested_id:
            person_name = p.name
            break

    if not person_name:
        # Suggested ID not in candidates, fallback to first
        first = candidates[0]
        return ReassignSuggestion(
            suggested_person_id=first.id,
            suggested_person_name=first.name,
            reason="AI suggested an invalid ID; falling back to first candidate",
            confidence=0.3,
            ai_run_id=run_id,
            fallback_used=True,
        )

    return ReassignSuggestion(
        suggested_person_id=suggested_id,
        suggested_person_name=person_name,
        reason=result.get("reason", ""),
        confidence=float(result.get("confidence", 0.5)),
        ai_run_id=run_id,
        fallback_used=False,
    )
