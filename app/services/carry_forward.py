"""Carry-forward service — moving open items across meetings while preserving full history."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import ActionItem, ItemEventType, ItemHistory, ItemStatus, Meeting, MeetingStatus
from app.logging_config import get_audit_logger, get_logger
from app.services.items import _append_history

logger = get_logger("services.carry_forward")
audit = get_audit_logger()


def carry_forward_items(
    db: Session,
    item_ids: list[int],
    target_meeting_id: int,
    actor_id: int | None = None,
) -> list[ActionItem]:
    """
    Carry forward open action items from their current meeting to a target meeting.
    Rejects closed items (done/cancelled) with a clear error.
    Appends an append-only item_history event for each item.
    Increments carry_forward_count.
    """
    target_meeting = db.query(Meeting).filter(Meeting.id == target_meeting_id).first()
    if not target_meeting:
        raise HTTPException(status_code=404, detail=f"Target meeting {target_meeting_id} not found")

    if target_meeting.status == MeetingStatus.archived:
        raise HTTPException(status_code=400, detail="Cannot carry forward items to an archived meeting")

    updated_items: list[ActionItem] = []

    for item_id in item_ids:
        item = db.query(ActionItem).filter(ActionItem.id == item_id).first()
        if not item:
            raise HTTPException(status_code=404, detail=f"Action item {item_id} not found")

        if item.status in (ItemStatus.done, ItemStatus.cancelled):
            raise HTTPException(
                status_code=400,
                detail=f"Cannot carry forward closed item '{item.title}' (status: {item.status})",
            )

        old_meeting_id = item.current_meeting_id
        if old_meeting_id == target_meeting_id:
            continue  # Already in target meeting

        item.current_meeting_id = target_meeting_id
        item.carry_forward_count += 1
        item.version += 1

        _append_history(
            db=db,
            item_id=item.id,
            event_type=ItemEventType.carried_forward,
            actor_id=actor_id,
            old_val=str(old_meeting_id) if old_meeting_id else "None",
            new_val=str(target_meeting_id),
            note=f"Carried forward to meeting #{target_meeting_id} ({target_meeting.title})",
        )

        audit.info(
            "item.carried_forward",
            item_id=item.id,
            from_meeting_id=old_meeting_id,
            to_meeting_id=target_meeting_id,
            carry_count=item.carry_forward_count,
        )
        updated_items.append(item)

    db.commit()
    for item in updated_items:
        db.refresh(item)

    return updated_items

