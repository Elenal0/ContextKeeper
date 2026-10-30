"""Action Items service — CRUD, close, reassign, history."""
from __future__ import annotations

import warnings
from datetime import datetime, timezone

import structlog
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import (
    ActionItem,
    Availability,
    ItemEventType,
    ItemHistory,
    ItemStatus,
    Person,
    Priority,
    ResolutionType,
)
from app.schemas.items import ActionItemCreate, ActionItemUpdate

logger = structlog.get_logger("services.items")


# ── History helper ────────────────────────────────────────────────────────────

def _append_history(
    db: Session,
    item_id: int,
    event_type: ItemEventType,
    actor_id: int | None,
    old_val: str,
    new_val: str,
    note: str = "",
) -> ItemHistory:
    history = ItemHistory(
        item_id=item_id,
        event_type=event_type,
        actor_id=actor_id,
        old_value=old_val,
        new_value=new_val,
        note=note,
        timestamp=datetime.now(timezone.utc),
    )
    db.add(history)
    return history


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_items(
    db: Session,
    owner_id: int | None = None,
    status: str | None = None,
    priority: str | None = None,
    meeting_id: int | None = None,
    skip: int = 0,
    limit: int = 50,
) -> list[ActionItem]:
    q = db.query(ActionItem)
    if owner_id is not None:
        q = q.filter(ActionItem.owner_id == owner_id)
    if status:
        q = q.filter(ActionItem.status == status)
    if priority:
        q = q.filter(ActionItem.priority == priority)
    if meeting_id is not None:
        q = q.filter(ActionItem.current_meeting_id == meeting_id)
    return q.order_by(ActionItem.due_date.asc().nulls_last()).offset(skip).limit(limit).all()


def get_item(db: Session, item_id: int) -> ActionItem:
    item = db.query(ActionItem).filter(ActionItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail=f"Action item {item_id} not found")
    return item


def create_item(db: Session, data: ActionItemCreate) -> ActionItem:
    item = ActionItem(
        title=data.title,
        description=data.description,
        owner_id=data.owner_id,
        due_date=data.due_date,
        priority=data.priority,
        source_meeting_id=data.source_meeting_id,
        current_meeting_id=data.current_meeting_id,
        status=ItemStatus.open,
        version=1,
    )
    db.add(item)
    db.flush()  # get ID

    _append_history(
        db, item.id, ItemEventType.created, data.actor_id,
        old_val="", new_val=data.title, note="Item created",
    )

    db.commit()
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, data: ActionItemUpdate) -> ActionItem:
    item = get_item(db, item_id)

    # Optimistic concurrency
    if data.version != item.version:
        raise HTTPException(
            status_code=409,
            detail=f"Version conflict: expected {item.version}, got {data.version}",
        )

    updates = data.model_dump(exclude_unset=True, exclude={"version", "actor_id"})

    # Track changes per field for history
    field_to_event: dict[str, ItemEventType] = {
        "status": ItemEventType.status_changed,
        "owner_id": ItemEventType.reassigned,
        "due_date": ItemEventType.due_date_changed,
        "priority": ItemEventType.priority_changed,
    }

    actor_id = data.actor_id

    for field, new_value in updates.items():
        old_value = getattr(item, field, None)
        if old_value != new_value:
            event_type = field_to_event.get(field, ItemEventType.edited)
            _append_history(
                db, item_id, event_type, actor_id,
                old_val=str(old_value) if old_value is not None else "",
                new_val=str(new_value) if new_value is not None else "",
                note=f"{field} changed",
            )
        setattr(item, field, new_value)

    item.version = item.version + 1
    db.commit()
    db.refresh(item)
    return item


def close_item(
    db: Session,
    item_id: int,
    outcome: str,
    resolution_type: ResolutionType,
    actor_id: int | None = None,
) -> ActionItem:
    if not outcome or not outcome.strip():
        raise HTTPException(status_code=400, detail="An outcome must be provided to close an action item")

    item = get_item(db, item_id)

    if item.status in (ItemStatus.done, ItemStatus.cancelled):
        raise HTTPException(
            status_code=409,
            detail=f"Item is already {item.status}; cannot close again",
        )

    old_status = item.status
    item.status = ItemStatus.done
    item.outcome = outcome
    item.resolution_type = resolution_type
    item.closed_at = datetime.now(timezone.utc)
    item.version = item.version + 1

    _append_history(
        db, item_id, ItemEventType.outcome_recorded, actor_id,
        old_val=old_status, new_val=ItemStatus.done,
        note=f"Closed: {resolution_type}. Outcome: {outcome[:200]}",
    )

    db.commit()
    db.refresh(item)
    return item


def reassign_item(
    db: Session,
    item_id: int,
    new_owner_id: int,
    actor_id: int | None,
    note: str = "",
) -> ActionItem:
    item = get_item(db, item_id)

    # Check new owner exists
    new_owner = db.query(Person).filter(Person.id == new_owner_id).first()
    if not new_owner:
        raise HTTPException(status_code=404, detail=f"Person {new_owner_id} not found")

    # Warn if new owner on leave
    if new_owner.availability == Availability.on_leave:
        logger.warning(
            "items.reassign_to_on_leave",
            item_id=item_id,
            new_owner_id=new_owner_id,
        )
        # We don't block it, just warn

    old_owner_id = item.owner_id
    item.owner_id = new_owner_id
    item.version = item.version + 1

    _append_history(
        db, item_id, ItemEventType.reassigned, actor_id,
        old_val=str(old_owner_id) if old_owner_id else "",
        new_val=str(new_owner_id),
        note=note or f"Reassigned to {new_owner.name}",
    )

    db.commit()
    db.refresh(item)
    return item


def get_item_history(db: Session, item_id: int) -> list[ItemHistory]:
    get_item(db, item_id)  # 404 guard
    return (
        db.query(ItemHistory)
        .filter(ItemHistory.item_id == item_id)
        .order_by(ItemHistory.timestamp.asc())
        .all()
    )
